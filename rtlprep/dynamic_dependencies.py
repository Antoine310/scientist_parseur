"""Bounded candidates for a single runtime element index in a direct assignment.

Coordinates are declaration-relative, never flattened. Each alternative is
conditional on the numeric selector value, not proof that value is reachable.
Unknown/out-of-range read and write behavior is intentionally not modeled.
"""
from collections import Counter
from .array_dependencies import (Unsupported, layout, layouts, decompose,
    index_value, lane_order, MAX_DIMENSIONS)
from .constant_indices import evaluate
from .bitwise_dependencies import expression
from .packed_coordinates import constant_chain
from .symbols import SignalResolver

MAX_ROWS=2000
MAX_EDGES=16384
MAX_WIDTH=1024
MAX_CHOICES=128
MAX_INDEX_WIDTH=32
MAX_NODES=256
MAX_ROW_PAIRS=8192
BUDGET_REASONS=frozenset(("choice_budget_exceeded","row_pair_budget",
    "edge_budget_exceeded","lane_budget_exceeded","expression_traversal_budget",
    "concat_operand_budget"))

def has_dynamic(expr,constants):
    """Only selection chains at the assignment roots are in scope."""
    for _ in range(MAX_DIMENSIONS+3):
        if not isinstance(expr,dict):
            return False
        if expr.get("kind")=="ElementSelect":
            if evaluate(expr.get("selector"),constants) is None:
                return True
        elif expr.get("kind")!="RangeSelect":
            return False
        expr=expr.get("value")
    return False

def selector_domain(expr,dim,resolve,declared,constants):
    if not isinstance(expr,dict):
        raise Unsupported("malformed_selector")
    typ=layout(expr.get("type"))
    # Plain unsigned packed vectors/scalars only. No signedness guessing
    # for aliases, enums, integer casts or unsupported selector layouts.
    if typ is None or typ[2] or len(typ[1])>1:
        raise Unsupported("unproven_selector_type")
    n=abs(typ[1][0][0]-typ[1][0][1])+1 if typ[1] else 1
    if not 1<=n<=MAX_INDEX_WIDTH:
        raise Unsupported("unsupported_selector_width")
    lanes=expression(expr,resolve,declared,constants,set(),[MAX_NODES])
    if len(lanes)!=n:
        raise Unsupported("selector_width_mismatch")
    leaves=set().union(*lanes)
    if not leaves:
        raise Unsupported("selector_not_runtime_proven")
    lo,hi=min(dim),max(dim)
    maximum=(1<<n)-1
    last=min(hi,maximum)
    if last<lo:
        raise Unsupported("no_in_range_selector_values")
    if last-lo+1>MAX_CHOICES:
        raise Unsupported("choice_budget_exceeded")
    return {"selector_type":expr["type"],"selector_width":n,
            "declared_bounds":list(dim),"indices":list(range(lo,last+1)),
            "numeric_out_of_range_possible":lo>0 or maximum>hi,
            "unknown_selector_possible":typ[0]=="logic",
            "selector_sources":[{"source":s,"source_unpacked_indices":[],
                "source_packed_indices":list(p),"source_bit":b}
                for s,p,b in sorted(leaves)]}

def plan(expr,resolve,declared,constants):
    """Validate every selection result and produce coordinate templates."""
    base,chain=decompose(expr)
    signal=resolve(base)
    typ=layout(base.get("type"))
    if signal is None or typ is None or declared.get(signal)!=typ:
        raise Unsupported("unproven_declared_layout")
    state,packed,unpacked=typ
    u,p=[],[]
    bits=None
    dynamic=None
    for sel in chain:
        kind=sel["kind"]
        if unpacked:
            dim=unpacked[0]
            dest=u
            unpacked=unpacked[1:]
            category="unpacked"
        elif packed:
            dim=packed[0]
            dest=p
            packed=packed[1:]
            category="packed" if packed else "bit"
        else:
            raise Unsupported("extra_scalar_selection")
        if kind=="ElementSelect":
            selector=sel.get("selector")
            v=evaluate(selector,constants)
            if v is None:
                if dynamic is not None:
                    raise Unsupported("multiple_dynamic_selectors")
                dynamic=selector_domain(selector,dim,resolve,declared,constants)
                dynamic.update(dimension_kind=category,dimension_ordinal=len(dest) if category!="bit" else len(p))
            else:
                v=index_value(selector,constants,dim)
            if category=="bit":
                bits=[v]
            else:
                dest.append(v)
        elif kind=="RangeSelect" and category=="bit" and sel.get("selectionKind")=="Simple":
            left=index_value(sel.get("left"),constants,dim)
            right=index_value(sel.get("right"),constants,dim)
            if left!=right and (left>right)!=(dim[0]>dim[1]):
                raise Unsupported("range_direction_mismatch")
            packed=((left,right),)
            bits=lane_order(left,right)
        else:
            raise Unsupported("unsupported_selection_form")
        if layout(sel.get("type"))!=(state,packed,unpacked):
            raise Unsupported("selection_type_mismatch")
    if unpacked or len(packed)>1:
        raise Unsupported("aggregate_selection_not_supported")
    if bits is None:
        bits=lane_order(*packed[0]) if packed else [0]
    end=layout(expr.get("type"))
    if end!=(state,packed,unpacked):
        raise Unsupported("selection_result_type_mismatch")
    n=abs(packed[0][0]-packed[0][1])+1 if packed else 1
    if n!=len(bits) or not 1<=n<=MAX_WIDTH:
        raise Unsupported("selection_result_width_mismatch")
    return {"signal":signal,"state":state,"unpacked":u,"packed":p,
            "bits":bits,"dynamic":dynamic}

def positions(template,value,prefix):
    def subst(xs):
        return [value if x is None else x for x in xs]
    return [{prefix:template["signal"],prefix+"_unpacked_indices":subst(template["unpacked"]),
             prefix+"_packed_indices":subst(template["packed"]),prefix+"_bit":b}
            for b in subst(template["bits"])]

def expand(node,resolve,declared,constants):
    if (node.get("kind")!="Assignment" or type(node.get("isNonBlocking")) is not bool
            or node.get("op") is not None or node.get("timingControl") is not None):
        raise Unsupported("not_plain_assignment")
    lhs,rhs=node.get("left"),node.get("right")
    dst=plan(lhs,resolve,declared,constants)
    if layout(node.get("type"))!=layout(lhs.get("type")):
        raise Unsupported("assignment_type_mismatch")
    src=None
    constant=False
    if isinstance(rhs,dict) and rhs.get("kind") in ("Conversion","IntegerLiteral","UnbasedUnsizedIntegerLiteral"):
        try:
            n=constant_chain(rhs)
        except Unsupported:
            pass
        else:
            if n!=len(dst["bits"]):
                raise Unsupported("literal_assignment_width_mismatch")
            constant=True
    if not constant:
        src=plan(rhs,resolve,declared,constants)
        if src["state"]!=dst["state"] or len(src["bits"])!=len(dst["bits"]):
            raise Unsupported("assignment_width_or_state_mismatch")
    if dst["dynamic"] and src is not None and src["dynamic"]:
        raise Unsupported("multiple_dynamic_selectors")
    domain=dst["dynamic"] or (src["dynamic"] if src is not None else None)
    if domain is None:
        raise Unsupported("no_runtime_selector")
    role="write" if dst["dynamic"] else "read"
    sources=domain["selector_sources"]
    if len(domain["indices"])*len(dst["bits"])*(1+len(sources))>MAX_ROW_PAIRS:
        raise Unsupported("row_pair_budget")
    edges=[]
    alternatives=[]
    for aid,value in enumerate(domain["indices"]):
        target=positions(dst,value,"target")
        source=positions(src,value,"source") if src is not None else []
        fixed=target if constant else []
        for s,d in zip(source,target):
            edges.append({**s,**d,"relation":"index_data_candidate","alternative_id":aid})
        for d in target:
            for s in sources:
                edges.append({**s,**d,"relation":"index_control_candidate","alternative_id":aid})
        alternatives.append({"alternative_id":aid,"selector_value":value,"constant_target_positions":fixed})
    return edges,{**domain,"role":role},alternatives

def build_dynamic_dependencies(ast,index,captured,flat,*,enabled=True):
    items,edges=[],[]
    fixed_count=0
    truncated=bool(enabled and flat["counts"]["truncated"])
    if enabled:
        resolver=SignalResolver(ast,index)
        declared=layouts(index)
        for ordinal,access,node,owner,constants,context_partial in captured:
            if flat["items"][ordinal]["coverage"]!="partial":
                continue
            if not any(has_dynamic(node.get(k),constants) for k in ("left","right")):
                continue
            if len(items)>=MAX_ROWS:
                truncated=True
                break
            row={"flat_assignment_id":ordinal,"target":access["target"],
                 "source_location":access.get("source"),"coverage":"partial","edge_count":0,
                 "assignment_kind":access.get("assignment_kind","continuous"),
                 "procedure_kind":access.get("procedure_kind"),"nonblocking":access.get("nonblocking"),
                 "guards":access.get("guards",[]),"events":access.get("events",[]),
                 "timing_scope":access.get("timing_scope")}
            items.append(row)
            try:
                if context_partial:
                    raise Unsupported("unsupported_procedural_context")
                local,domain,alternatives=expand(node,lambda e:resolver.resolve(owner,e),declared,constants)
                fixed=[p for a in alternatives for p in a["constant_target_positions"]]
                if any(e["target"]!=row["target"] for e in [*local,*fixed]):
                    raise Unsupported("assignment_target_identity_mismatch")
                if len(edges)+fixed_count+len(local)+len(fixed)>MAX_EDGES:
                    raise Unsupported("edge_budget_exceeded")
            except Unsupported as exc:
                row["reason"]=str(exc)
                if str(exc) in BUDGET_REASONS:
                    truncated=True
                continue
            row.update(coverage="dynamic_index_candidates",edge_count=len(local),
                       selector=domain,alternatives=alternatives)
            edges.extend({**e,"assignment_id":len(items)-1} for e in local)
            fixed_count+=len(fixed)
    status=Counter(r["coverage"] for r in items)
    return {"schema_version":1,"scope":"captured_flat_partial_single_runtime_element_selection",
            "items":items,"edges":edges,"counts":{"captured":len(items),
                "supported":status["dynamic_index_candidates"],"partial":status["partial"],
                "edges":len(edges),"truncated":truncated},
            "caveat":"In-range coordinate candidates conditional on numeric index, not reachability, "
                     "functional influence, exact values, or final-write semantics. Unknown and "
                     "out-of-range behavior not modeled. Constant positions are alternative-local."}

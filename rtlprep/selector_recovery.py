"""Recover fixed selectors previously refused as runtime/unproven types.

Only selectors newly proven by bounded lexical Power evaluation are
rewritten in a private copy. Delegate semantic expansion to PR71/72/73;
never trust a folded tag or claim dynamic alternatives for these indices.
"""
from collections import Counter
from .array_dependencies import Unsupported, layout, layouts
from .constant_indices import evaluate, MAX_POWER_EXPONENT, MAX_VALUE
from .packed_coordinates import selected, constant_chain
from .bitwise_dependencies import expand as expand_bitwise, has_operator
from .mux_dependencies import expand as expand_mux, root_mux
from .symbols import SignalResolver

MAX_ROWS=2000
MAX_EDGES=16384
MAX_DEPTH=24
MAX_NODES=512
MAX_PROOFS=64
BUDGET_REASONS=frozenset(("selector_scan_budget","selector_proof_budget",
    "edge_budget_exceeded","row_pair_budget","mux_row_pair_budget","mux_node_budget",
    "mux_depth_budget","mux_branch_budget","expression_traversal_budget","concat_operand_budget",
    "lane_budget_exceeded"))

def normalize(node,constants):
    proofs=[]
    budget=[MAX_NODES]
    def walk(n,path,depth):
        budget[0]-=1
        if budget[0]<0 or depth>MAX_DEPTH:
            raise Unsupported("selector_scan_budget")
        if not isinstance(n,dict):
            return n
        kind=n.get("kind")
        fields={
            "Assignment":("left","right"),
            "ElementSelect":("value",),
            "RangeSelect":("value",),
            "BinaryOp":("left","right"),
            "UnaryOp":("operand",),
            "Conversion":("operand",),
            "SignedConversion":("operand",),
            "Replication":("concat",),
            "ConditionalOp":("left","right"),
        }.get(kind,())
        result=dict(n)
        for field in fields:
            result[field]=walk(n.get(field),path+[field],depth+1)
        if kind=="Concatenation":
            parts=n.get("operands")
            if isinstance(parts,list):
                if len(parts)>MAX_NODES:
                    raise Unsupported("selector_scan_budget")
                result["operands"]=[walk(x,path+["operands",i],depth+1) for i,x in enumerate(parts)]
        if kind=="ConditionalOp":
            conds=n.get("conditions")
            if isinstance(conds,list):
                if len(conds)>MAX_NODES:
                    raise Unsupported("selector_scan_budget")
                result["conditions"]=[{**c,"expr":walk(c.get("expr"),path+["conditions",i,"expr"],depth+1)}
                    if isinstance(c,dict) and "expr" in c else c for i,c in enumerate(conds)]
        selectors=("selector",) if kind=="ElementSelect" else (
            ("left","right") if kind=="RangeSelect" and n.get("selectionKind")=="Simple" else ())
        for field in selectors:
            expr=n.get(field)
            if evaluate(expr,constants) is not None:
                continue
            value=evaluate(expr,constants,allow_power=True)
            if value is None:
                continue
            if len(proofs)>=MAX_PROOFS:
                raise Unsupported("selector_proof_budget")
            # The legacy evaluator rejects this expression, and the only
            # opt-in difference is Power. Preserve original integral type.
            literal={"kind":"IntegerLiteral","type":expr["type"],"value":str(value)}
            if evaluate(literal,constants)!=value:
                raise Unsupported("selector_literal_validation_failed")
            result[field]=literal
            proofs.append({"ast_path":path+[field],"type":expr["type"],
                           "index":value,"evidence":"bounded_lexical_power"})
        return result
    rewritten=walk(node,[],0)
    if not proofs:
        raise Unsupported("no_newly_proven_selector")
    return rewritten,proofs

def expand(node,resolve,declared,constants):
    rewritten,proofs=normalize(node,constants)
    lhs,rhs=rewritten.get("left"),rewritten.get("right")
    if root_mux(rhs):
        edges,decisions,branches=expand_mux(rewritten,resolve,declared,constants)
        return edges,{"mode":"mux","decisions":decisions,"branches":branches},proofs
    if has_operator(rhs):
        edges,fixed,operators=expand_bitwise(rewritten,resolve,declared,constants)
        return edges,{"mode":"bitwise","constant_target_positions":fixed,"operators":operators},proofs
    if (rewritten.get("kind")!="Assignment" or type(rewritten.get("isNonBlocking")) is not bool
            or rewritten.get("op") is not None or rewritten.get("timingControl") is not None):
        raise Unsupported("not_plain_assignment")
    dst,state=selected(lhs,resolve,declared,constants)
    if layout(rewritten.get("type"))!=layout(lhs.get("type")):
        raise Unsupported("assignment_type_mismatch")
    if isinstance(rhs,dict) and rhs.get("kind") in ("IntegerLiteral","UnbasedUnsizedIntegerLiteral","Conversion"):
        try:
            n=constant_chain(rhs)
        except Unsupported:
            pass
        else:
            if n!=len(dst[3]):
                raise Unsupported("literal_assignment_width_mismatch")
            fixed=[{"target":dst[0],"target_packed_indices":dst[2],"target_bit":b} for b in dst[3]]
            return [],{"mode":"fixed","constant_target_positions":fixed},proofs
    src,source_state=selected(rhs,resolve,declared,constants)
    if source_state!=state or len(src[3])!=len(dst[3]):
        raise Unsupported("assignment_width_or_state_mismatch")
    edges=[{"source":src[0],"source_packed_indices":src[2],"source_bit":s,
            "target":dst[0],"target_packed_indices":dst[2],"target_bit":d,
            "relation":"fixed_position_candidate"} for s,d in zip(src[3],dst[3])]
    return edges,{"mode":"fixed","constant_target_positions":[]},proofs

def constant_positions(detail):
    if detail["mode"]=="mux":
        return [p for b in detail["branches"] for p in b["constant_target_positions"]]
    return detail["constant_target_positions"]

def build_selector_recovery(ast,index,captured,flat,dynamic,*,enabled=True):
    items,edges=[],[]
    fixed_count=0
    truncated=bool(enabled and (flat["counts"]["truncated"] or dynamic["counts"]["truncated"]))
    if enabled:
        # Focus on the exact audited PR74 residual family, not every
        # expression in the AST. Non-root dynamic expressions remain debt.
        candidates={r["flat_assignment_id"] for r in dynamic["items"]
                    if r["coverage"]=="partial" and r.get("reason")=="unproven_selector_type"}
        resolver=SignalResolver(ast,index)
        declared=layouts(index)
        for ordinal,access,node,owner,constants,context_partial in captured:
            if ordinal not in candidates:
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
                local,detail,proofs=expand(node,lambda e:resolver.resolve(owner,e),declared,constants)
                fixed=constant_positions(detail)
                if any(e["target"]!=row["target"] for e in [*local,*fixed]):
                    raise Unsupported("assignment_target_identity_mismatch")
                if len(edges)+fixed_count+len(local)+len(fixed)>MAX_EDGES:
                    raise Unsupported("edge_budget_exceeded")
            except Unsupported as exc:
                row["reason"]=str(exc)
                if str(exc) in BUDGET_REASONS:
                    truncated=True
                continue
            row.update(coverage="fixed_selector_recovery",edge_count=len(local),
                       selector_proofs=proofs,**detail)
            edges.extend({**e,"assignment_id":len(items)-1} for e in local)
            fixed_count+=len(fixed)
    status=Counter(r["coverage"] for r in items)
    return {"schema_version":1,"scope":"pr74_unproven_root_selector_recovery",
            "items":items,"edges":edges,"counts":{"captured":len(items),
                "supported":status["fixed_selector_recovery"],"partial":status["partial"],
                "edges":len(edges),"truncated":truncated},
            "caveat":"Lexically proven fixed selectors; delegated candidate semantics, not functional "
                     "influence, guard feasibility, value or temporal proof. Legacy channels remain unchanged."}

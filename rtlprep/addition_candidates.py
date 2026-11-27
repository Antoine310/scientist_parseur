"""PR96: bounded assignment-local modular addition candidates, separate report."""
import json
from collections import Counter
from .analysis_budgets import inspect_ast
from .array_dependencies import Unsupported, decompose, layout, layouts
from .packed_coordinates import selected
from .bitaccess import build_bit_access_index
from .bitgraph import build_bit_dependency_graph
from .residual_audit import exact_links, reconcile_capture, syntax
from .symbols import SignalResolver
from .typed_layout import raw_layouts

MAX_WIDTH=64
MAX_ROWS=2000
MAX_COORDINATES=32768


def result_shape(expr):
    t=layout(expr.get("type")) if isinstance(expr,dict) else None
    if t is None or t[2] or len(t[1])>1:
        raise Unsupported("unproven_unsigned_result_layout")
    n=abs(t[1][0][0]-t[1][0][1])+1 if t[1] else 1
    if n>MAX_WIDTH:
        raise Unsupported("addition_width_outside_scope")
    return t[0],n


def endpoint(expr,resolve,raw,declared):
    base,chain=decompose(expr)
    sig=resolve(base)
    if sig is None or raw.get(sig)!=base.get("type"):
        raise Unsupported("unproven_exact_signal_identity_or_type")
    # Fixed integer literals only; no runtime, parameter, or compound index.
    for sel in chain:
        keys=("selector",) if sel["kind"]=="ElementSelect" else ("left","right")
        if any(not isinstance(sel.get(k),dict) or sel[k].get("kind")!="IntegerLiteral" for k in keys):
            raise Unsupported("nonliteral_selection")
    loc,kind=selected(expr,resolve,declared,{})
    state,n=result_shape(expr)
    if kind!=state or len(loc[3])!=n or loc[1]:
        raise Unsupported("endpoint_layout_disagreement")
    return {"signal":sig,"outer_packed_indices":loc[2],"bits_lsb_first":loc[3],
            "declared_type":base["type"],"expression_type":expr["type"]}


def coordinate_set(ep):
    return {(ep["signal"],tuple(ep["outer_packed_indices"]),b) for b in ep["bits_lsb_first"]}


def expand(node,resolve,raw,declared):
    if (node.get("kind")!="Assignment" or node.get("isNonBlocking") is not False
            or node.get("op") is not None or node.get("timingControl") is not None):
        raise Unsupported("not_plain_blocking_assignment")
    lhs,rhs=node.get("left"),node.get("right")
    if not isinstance(rhs,dict) or rhs.get("kind")!="BinaryOp" or rhs.get("op")!="Add":
        raise Unsupported("not_direct_addition")
    if not isinstance(lhs,dict) or node.get("type")!=lhs.get("type"):
        raise Unsupported("assignment_type_mismatch")
    state,n=result_shape(lhs)
    operands=[rhs.get("left"),rhs.get("right")]
    if any(result_shape(e)!=(state,n) for e in [rhs,*operands]):
        raise Unsupported("addition_width_or_state_mismatch")
    dst=endpoint(lhs,resolve,raw,declared)
    src=[endpoint(e,resolve,raw,declared) for e in operands]
    if coordinate_set(src[0]) & coordinate_set(src[1]):
        raise Unsupported("overlapping_operand_coordinates")
    return {"operator":"Add","width":n,"state":state,"target":dst,"operands":src,
            "relation":"modular_addition_potential_influence_candidate",
            "representation":"lsb_prefix_per_operand","prefix_lengths":list(range(1,n+1)),
            "potential_pairs":n*(n+1),"value_equivalence":"not_proven",
            "guard_feasibility":"not_proven","timing":"not_proven",
            "model_domain":"defined_binary_inputs_only"}


def audit_additions(ast,index,graph,*,_expand=None):
    return _audit_arithmetic(ast,index,graph,operator="Add",coverage="addition_candidates",expand_candidate=_expand)


def _audit_arithmetic(ast,index,graph,*,operator,coverage,expand_candidate):
    if (operator,coverage) not in (("Add","addition_candidates"),("Subtract","subtraction_candidates")):
        raise ValueError("unsupported_arithmetic_audit_family")
    inspect_ast(ast)
    if graph["analysis_limits"]["truncated_analyzers"]:
        raise ValueError("truncated_historical_analyzers")
    _,_,residual,_,_,_=exact_links(graph)
    captured=[]
    replay=build_bit_access_index(ast,expected_top=index["top"],index=index,captured_assignments=captured)
    if json.loads(json.dumps(replay))!=graph["bit_accesses"]:
        raise ValueError("bit_access_replay_disagreement")
    if json.loads(json.dumps(build_bit_dependency_graph(replay,index)))!=graph["bit_dependency_graph"]:
        raise ValueError("flat_replay_disagreement")
    capture=reconcile_capture(replay,captured)
    constants_by_id={i:constants for i,_,_,_,constants,_ in captured}
    resolve=SignalResolver(ast,index)
    raw,declared=raw_layouts(index),layouts(index)
    rows=[]
    coordinates=0
    for i in sorted(residual):
        node,owner,partial=capture[i]
        rhs=syntax(node.get("right"))
        if not rhs["scan_complete"]:
            raise ValueError("incomplete_residual_syntax")
        if (rhs["root_after_conversions"],rhs["root_operator"])!=("BinaryOp",operator):
            continue
        if len(rows)>=MAX_ROWS:
            raise ValueError("addition_row_budget")
        f=graph["bit_dependency_graph"]["items"][i]
        row={"flat_assignment_id":i,"target":f["target"],"source_location":f.get("source_location"),
             "instance":owner,"assignment_kind":f["assignment_kind"],"procedure_kind":f.get("procedure_kind"),
             "coverage":"partial"}
        rows.append(row)
        try:
            if partial or (f["assignment_kind"]!="continuous" and f.get("procedure_kind")!="AlwaysComb"):
                raise Unsupported("unsupported_assignment_context")
            exact=lambda e:resolve.resolve_exact(owner,e)
            candidate=(expand(node,exact,raw,declared) if expand_candidate is None else
                       expand_candidate(node,exact,raw,declared,constants_by_id[i]))
            if candidate["target"]["signal"]!=f["target"]:
                raise Unsupported("assignment_target_identity_mismatch")
        except Unsupported as exc:
            row["reason"]=str(exc)
            continue
        coordinates+=sum(len(e["bits_lsb_first"]) for e in
                         [candidate["target"],*candidate["operands"]])
        if coordinates>MAX_COORDINATES:
            raise ValueError("addition_coordinate_budget")
        row.update(coverage=coverage,candidate=candidate)
    good=[r for r in rows if r["coverage"]==coverage]
    return {"schema_version":1,"scope":"residual_flat_addition_roots_only",
            "counts":{"residual_ids":len(residual),"roots":len(rows),"supported":len(good),
                      "partial":len(rows)-len(good),"potential_pairs":sum(r["candidate"]["potential_pairs"] for r in good),
                      "stored_coordinates":coordinates,"truncated":False},
            "partial_reasons":dict(Counter(r["reason"] for r in rows if "reason" in r)),
            "items":rows,"design_coverage":"not_measured","functional_influence":"not_proven",
            "formal_proof":"not_performed","caveat":"Compact potential pairs for defined binary operands only; "
            "no X/Z, global influence, guard, priority or temporal proof. No historical graph promotion."}

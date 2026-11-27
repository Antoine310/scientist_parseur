"""PR111: read-once logical trees with direct fixed-coordinate leaves.

Only residual historical flat IDs, no historical promotion. Defined-binary
model, not guard feasibility, global influence or four-state value semantics.
"""
import json
from collections import Counter
from .analysis_budgets import inspect_ast
from .array_dependencies import Unsupported,layouts
from .addition_candidates import result_shape,coordinate_set
from .zero_extended_additions import endpoint
from .bitaccess import build_bit_access_index
from .bitgraph import build_bit_dependency_graph
from .residual_audit import exact_links,reconcile_capture,syntax
from .symbols import SignalResolver
from .typed_layout import raw_layouts

LOGICAL_BINARY={"LogicalAnd","LogicalOr"}
LOGICAL_UNARY={"LogicalNot"}
REDUCTIONS={"BitwiseAnd","BitwiseOr","BitwiseXor","BitwiseNand","BitwiseNor","BitwiseXnor"}
ROOTS=LOGICAL_BINARY|LOGICAL_UNARY|REDUCTIONS
MAX_DEPTH=8
MAX_NODES=64
MAX_WIDTH=32
MAX_ROWS=2000
MAX_COORDINATES=32768


def expand(node,resolve,raw,declared,constants):
    if (node.get("kind")!="Assignment" or node.get("isNonBlocking") is not False
            or node.get("op") is not None or node.get("timingControl") is not None):
        raise Unsupported("not_plain_blocking_assignment")
    lhs,rhs=node.get("left"),node.get("right")
    if not isinstance(rhs,dict) or rhs.get("op") not in ROOTS or rhs.get("kind") not in ("BinaryOp","UnaryOp"):
        raise Unsupported("not_direct_logical_or_reduction_root")
    if not isinstance(lhs,dict) or node.get("type")!=lhs.get("type") or result_shape(lhs)!=("logic",1):
        raise Unsupported("not_matching_scalar_target")
    dst=endpoint(lhs,resolve,raw,declared,constants)
    if dst["outer_packed_indices"]:
        raise Unsupported("packed_outer_coordinate_outside_scope")
    seen=coordinate_set(dst)
    leaves=[]
    budget=[MAX_NODES]

    def leaf(expr):
        state,n=result_shape(expr)
        if state!="logic" or not 1<=n<=MAX_WIDTH:
            raise Unsupported("unproven_logic_leaf_width_or_state")
        ep=endpoint(expr,resolve,raw,declared,constants)
        if ep["outer_packed_indices"]:
            raise Unsupported("packed_outer_coordinate_outside_scope")
        coords=coordinate_set(ep)
        if seen&coords:
            raise Unsupported("repeated_or_target_alias_coordinate")
        seen.update(coords)
        i=len(leaves)
        leaves.append(ep)
        return {"leaf":i,"truth_conversion":"nonzero" if n>1 else "scalar"}

    def walk(expr,depth=0):
        budget[0]-=1
        if budget[0]<0 or depth>MAX_DEPTH:
            raise Unsupported("logical_tree_budget")
        if not isinstance(expr,dict):
            raise Unsupported("malformed_logical_expression")
        kind,op=expr.get("kind"),expr.get("op")
        if kind in ("NamedValue","ElementSelect","RangeSelect"):
            return leaf(expr)
        if result_shape(expr)!=("logic",1):
            raise Unsupported("logical_result_not_scalar")
        if kind=="BinaryOp" and op in LOGICAL_BINARY:
            return {"op":op,"args":[walk(expr.get("left"),depth+1),walk(expr.get("right"),depth+1)]}
        if kind=="UnaryOp" and op in LOGICAL_UNARY:
            return {"op":op,"args":[walk(expr.get("operand"),depth+1)]}
        if kind=="UnaryOp" and op in REDUCTIONS:
            operand=expr.get("operand")
            if not isinstance(operand,dict) or operand.get("kind") not in ("NamedValue","ElementSelect","RangeSelect"):
                raise Unsupported("composed_reduction_operand")
            l=leaf(operand)
            l["truth_conversion"]="reduction_bits"
            return {"op":op,"args":[l]}
        raise Unsupported("unsupported_logical_child_"+str(kind)[:32]+"_"+str(op)[:32])
    tree=walk(rhs)
    if "op" not in tree:
        raise Unsupported("not_operator_tree")
    return {"operator":rhs["op"],"target":dst,"operands":leaves,"tree":tree,
            "relation":"read_once_logical_potential_influence_candidate",
            "representation":"distinct_runtime_coordinates_to_scalar",
            "potential_pairs":sum(len(e["bits_lsb_first"]) for e in leaves),
            "model_domain":"defined_binary_inputs_only","value_equivalence":"not_proven",
            "guard_feasibility":"not_proven","timing":"not_proven"}


def audit_logical(ast,index,graph):
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
    constants_by_id={i:c for i,_,_,_,c,_ in captured}
    resolver=SignalResolver(ast,index)
    raw,declared=raw_layouts(index),layouts(index)
    items=[]
    nested=[]
    coordinates=0
    for i in sorted(residual):
        node,owner,partial=capture[i]
        syn=syntax(node.get("right"))
        if not syn["scan_complete"]:
            raise ValueError("incomplete_residual_syntax")
        has=any(k in syn["operators"] for k in [*("BinaryOp:"+op for op in LOGICAL_BINARY),
                                                 *("UnaryOp:"+op for op in LOGICAL_UNARY|REDUCTIONS)])
        if syn["root_operator"] not in ROOTS or syn["root_after_conversions"] not in ("BinaryOp","UnaryOp"):
            if has:
                nested.append(i)
            continue
        if len(items)>=MAX_ROWS:
            raise ValueError("logical_row_budget")
        f=graph["bit_dependency_graph"]["items"][i]
        row={"flat_assignment_id":i,"instance":owner,"target":f["target"],"source_location":f.get("source_location"),
             "assignment_kind":f["assignment_kind"],"procedure_kind":f.get("procedure_kind"),"coverage":"partial"}
        try:
            if partial or (f["assignment_kind"]!="continuous" and f.get("procedure_kind")!="AlwaysComb"):
                raise Unsupported("unsupported_assignment_context")
            candidate=expand(node,lambda e:resolver.resolve_exact(owner,e),raw,declared,constants_by_id[i])
            if candidate["target"]["signal"]!=f["target"]:
                raise Unsupported("assignment_target_identity_mismatch")
        except Unsupported as exc:
            row["reason"]=str(exc)
        else:
            coordinates+=1+candidate["potential_pairs"]
            if coordinates>MAX_COORDINATES:
                raise ValueError("logical_coordinate_budget")
            row.update(coverage="logical_candidates",candidate=candidate)
        items.append(row)
    good=[r for r in items if r["coverage"]=="logical_candidates"]
    return {"schema_version":1,"scope":"residual_flat_logical_reduction_roots_read_once",
            "counts":{"residual_ids":len(residual),"roots":len(items),"supported":len(good),
                      "partial":len(items)-len(good),"potential_pairs":sum(r["candidate"]["potential_pairs"] for r in good),
                      "stored_coordinates":coordinates,"nested_only_rows":len(nested),"truncated":False},
            "nested_only_ids":nested,"partial_reasons":dict(Counter(r["reason"] for r in items if "reason" in r)),
            "items":items,"historical_replay_exact":True,"historical_graph_promoted":False,
            "new_historical_edges":0,"design_coverage":"not_measured","functional_influence":"not_proven",
            "caveat":"Read-once local logical candidates; no global influence, X/Z, guard, short-circuit side effects, priority, timing or RTL proof."}

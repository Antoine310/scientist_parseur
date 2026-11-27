"""PR114: exact full-width signed products of equally sized fixed endpoints."""
import json
import re
from collections import Counter
from .analysis_budgets import inspect_ast
from .array_dependencies import Unsupported,layouts,layout
from .addition_candidates import coordinate_set
from .zero_extended_additions import endpoint
from .constant_indices import evaluate
from .bitaccess import build_bit_access_index
from .bitgraph import build_bit_dependency_graph
from .residual_audit import exact_links,reconcile_capture,syntax
from .symbols import SignalResolver
from .typed_layout import raw_layouts

ROOTS={"Multiply"}
WIDTHS={4,9,17}
MAX_ROWS=2000
MAX_COORDINATES=32768


def require(ok,reason):
    if not ok:
        raise Unsupported(reason)


def checked_endpoint(expr,n,resolve,raw,declared,constants):
    require(isinstance(expr,dict) and expr.get("type")==f"logic[{n-1}:0]",
            "endpoint_type_disagreement")
    kind=expr.get("kind")
    require(kind in ("NamedValue","ElementSelect"),"not_direct_or_packed_word")
    base=expr if kind=="NamedValue" else expr.get("value")
    require(isinstance(base,dict) and base.get("kind")=="NamedValue","not_flat_base")
    typ=layout(base.get("type"))
    require(typ is not None and typ[0]=="logic" and not typ[2],"unproven_packed_type")
    dims=typ[1]
    require(len(dims)==(1 if kind=="NamedValue" else 2) and dims[-1]==(n-1,0),
            "unsupported_declared_layout")
    if kind=="ElementSelect":
        sel=expr.get("selector")
        require(isinstance(sel,dict) and sel.get("kind")=="IntegerLiteral" and sel.get("type")=="int",
                "not_literal_word_selector")
        i=evaluate(sel,{})
        require(i is not None and dims[0][1]<=i<=dims[0][0],"invalid_word_selector")
    else:
        i=None
    ep=endpoint(expr,resolve,raw,declared,constants)
    require(ep["outer_packed_indices"]==([] if i is None else [i])
            and ep["bits_lsb_first"]==list(range(n)),"coordinate_disagreement")
    return ep


def signed_operand(expr,n,resolve,raw,declared,constants):
    wide=f"logic signed[{2*n-1}:0]"
    require(isinstance(expr,dict) and expr.get("kind")=="Conversion" and expr.get("type")==wide,
            "not_exact_sign_extension")
    call=expr.get("operand")
    require(isinstance(call,dict) and call.get("kind")=="Call" and call.get("subroutine")=="$signed"
            and call.get("type")==f"logic signed[{n-1}:0]","not_exact_signed_call")
    args=call.get("arguments")
    require(isinstance(args,list) and len(args)==1,"signed_call_arity")
    ep=checked_endpoint(args[0],n,resolve,raw,declared,constants)
    ep["extension"]={"kind":"signed_reinterpret_then_sign_extend","from_width":n,"to_width":2*n}
    return ep


def expand(node,resolve,raw,declared,constants):
    require(isinstance(node,dict) and node.get("kind")=="Assignment"
            and node.get("isNonBlocking") is False and node.get("op") is None
            and node.get("timingControl") is None,"not_plain_blocking_assignment")
    lhs,rhs=node.get("left"),node.get("right")
    require(isinstance(lhs,dict) and isinstance(rhs,dict),"malformed_assignment")
    n=next((w for w in WIDTHS if lhs.get("type")==f"logic[{2*w-1}:0]"),None)
    require(n is not None and node.get("type")==lhs.get("type"),"unsupported_product_target")
    dst=checked_endpoint(lhs,2*n,resolve,raw,declared,constants)
    require(rhs.get("kind")=="Conversion" and rhs.get("type")==lhs.get("type"),
            "not_exact_unsigned_result_reinterpretation")
    op=rhs.get("operand")
    require(isinstance(op,dict) and op.get("kind")=="BinaryOp" and op.get("op")=="Multiply"
            and op.get("type")==f"logic signed[{2*n-1}:0]","not_exact_signed_full_product")
    operands=[signed_operand(op.get(k),n,resolve,raw,declared,constants) for k in ("left","right")]
    seen=coordinate_set(dst)
    for ep in operands:
        coords=coordinate_set(ep)
        require(not seen&coords,"overlapping_operand_or_target_coordinates")
        seen.update(coords)
    prefixes=[min(i+1,n) for i in range(2*n)]
    return {"operator":"Multiply","target":dst,"operands":operands,"operand_width":n,
            "output_width":2*n,"relation":"signed_full_product_potential_influence_candidate",
            "representation":"lsb_prefix_per_original_operand","prefix_lengths":prefixes,
            "potential_pairs":2*sum(prefixes),"model_domain":"defined_binary_inputs_only",
            "value_equivalence":"not_proven","guard_feasibility":"not_proven","timing":"not_proven"}


def audit_multiplications(ast,index,graph):
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
        has=any("BinaryOp:"+op in syn["operators"] for op in ROOTS)
        if syn["root_operator"] not in ROOTS or syn["root_after_conversions"]!="BinaryOp":
            if has:
                nested.append(i)
            continue
        if len(items)>=MAX_ROWS:
            raise ValueError("multiply_row_budget")
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
            coordinates+=len(candidate["target"]["bits_lsb_first"])+sum(len(e["bits_lsb_first"]) for e in candidate["operands"])
            if coordinates>MAX_COORDINATES:
                raise ValueError("multiply_coordinate_budget")
            row.update(coverage="multiply_candidates",candidate=candidate)
        items.append(row)
    good=[r for r in items if r["coverage"]=="multiply_candidates"]
    return {"schema_version":1,"scope":"residual_flat_signed_full_product_roots",
            "counts":{"residual_ids":len(residual),"roots":len(items),"supported":len(good),
                      "partial":len(items)-len(good),"potential_pairs":sum(r["candidate"]["potential_pairs"] for r in good),
                      "stored_coordinates":coordinates,"nested_only_rows":len(nested),"truncated":False},
            "nested_only_ids":nested,"partial_reasons":dict(Counter(r["reason"] for r in items if "reason" in r)),
            "items":items,"historical_replay_exact":True,"historical_graph_promoted":False,
            "new_historical_edges":0,"design_coverage":"not_measured","functional_influence":"not_proven",
            "caveat":"Full signed product, defined-binary local candidates; no global influence, X/Z, guards, timing or RTL proof."}

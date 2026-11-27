"""PR113: exact $signed({control & msb,data}) >>> amount, low n-bit result."""
import json
import re
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

ROOTS={"ArithmeticShiftRight"}
MAX_ROWS=2000
MAX_COORDINATES=32768
WIDTHS={4:2,8:3,16:4}


def require(ok,reason):
    if not ok:
        raise Unsupported(reason)


def checked_endpoint(expr,resolve,raw,declared,constants):
    require(isinstance(expr,dict),"malformed_endpoint")
    kind=expr.get("kind")
    require(kind in ("NamedValue","ElementSelect","RangeSelect"),"unsupported_endpoint")
    base=expr if kind=="NamedValue" else expr.get("value")
    require(isinstance(base,dict) and base.get("kind")=="NamedValue","not_flat_endpoint")
    typ=base.get("type")
    require(isinstance(typ,str) and re.fullmatch(r"logic(?:\[[0-9]{1,5}:[0-9]{1,5}\])?",typ),
            "not_unsigned_four_state_endpoint")
    ep=endpoint(expr,resolve,raw,declared,constants)
    require(not ep["outer_packed_indices"],"outer_coordinate_outside_scope")
    bounds=re.findall(r"\[([0-9]+):([0-9]+)\]",typ)
    require(not bounds or int(bounds[0][0])>=int(bounds[0][1]),"ascending_declaration")
    bits=ep["bits_lsb_first"]
    require(bool(bits) and bits==list(range(bits[0],bits[-1]+1)),"noncontiguous_coordinates")
    if kind=="NamedValue":
        expected=typ
    elif kind=="ElementSelect":
        require(bool(bounds) and len(bits)==1,"not_vector_element")
        expected="logic"
    else:
        require(bool(bounds) and expr.get("selectionKind")=="Simple","not_simple_range")
        expected=f"logic[{bits[-1]}:{bits[0]}]"
    require(expr.get("type")==expected,"serialized_endpoint_type_disagreement")
    require(result_shape(expr)==("logic",len(bits)),"endpoint_shape_disagreement")
    return ep


def lane_support(n,m):
    # The signed prefix is d[n-1] & mode. Every k is 0..n-1.
    # Keep original source ordinals; do not invent a separate sign variable.
    require(n in WIDTHS and WIDTHS[n]==m,"unsupported_width_or_amount")
    lanes=[]
    for i in range(n):
        tokens=[min(i+k,n) for k in range(1<<m)]
        data={min(t,n-1) for t in tokens}
        control=any(t==n for t in tokens)
        amounts=[b for b in range(m) if any(tokens[k]!=tokens[k^(1<<b)] for k in range(1<<m))]
        lanes.append({"data_ordinals":sorted(data),"amount_ordinals":amounts,
                      "mode_ordinals":[0] if control else []})
    return lanes


def expand(node,resolve,raw,declared,constants):
    require(isinstance(node,dict) and node.get("kind")=="Assignment"
            and node.get("isNonBlocking") is False and node.get("op") is None
            and node.get("timingControl") is None,"not_plain_blocking_assignment")
    lhs,rhs=node.get("left"),node.get("right")
    dst=checked_endpoint(lhs,resolve,raw,declared,constants)
    n=len(dst["bits_lsb_first"])
    require(n in WIDTHS and node.get("type")==lhs.get("type"),"unsupported_target_width_or_type")
    m=WIDTHS[n]
    require(isinstance(rhs,dict) and rhs.get("kind")=="Conversion"
            and rhs.get("type")==lhs.get("type"),"not_exact_low_result_conversion")
    op=rhs.get("operand")
    signed=f"logic signed[{n}:0]"
    require(isinstance(op,dict) and op.get("kind")=="BinaryOp"
            and op.get("op")=="ArithmeticShiftRight" and op.get("type")==signed,
            "not_exact_signed_shift")
    call=op.get("left")
    require(isinstance(call,dict) and call.get("kind")=="Call"
            and call.get("subroutine")=="$signed" and call.get("type")==signed,"not_exact_signed_call")
    args=call.get("arguments")
    require(isinstance(args,list) and len(args)==1,"signed_call_arity")
    cat=args[0]
    require(isinstance(cat,dict) and cat.get("kind")=="Concatenation"
            and cat.get("type")==f"logic[{n}:0]","not_exact_sign_concat")
    parts=cat.get("operands")
    require(isinstance(parts,list) and len(parts)==2,"sign_concat_arity")
    sign,data=parts
    require(isinstance(sign,dict) and sign.get("kind")=="BinaryOp"
            and sign.get("op")=="BinaryAnd" and sign.get("type")=="logic","not_exact_sign_and")
    de=checked_endpoint(data,resolve,raw,declared,constants)
    require(len(de["bits_lsb_first"])==n,"data_width_disagreement")
    a,b=[checked_endpoint(sign.get(k),resolve,raw,declared,constants) for k in ("left","right")]
    require(len(a["bits_lsb_first"])==len(b["bits_lsb_first"])==1,"sign_operand_not_scalar")
    high={(de["signal"],(),de["bits_lsb_first"][-1])}
    if coordinate_set(a)==high:
        msb,mode=a,b
    elif coordinate_set(b)==high:
        msb,mode=b,a
    else:
        raise Unsupported("sign_not_data_msb")
    amount=checked_endpoint(op.get("right"),resolve,raw,declared,constants)
    require(len(amount["bits_lsb_first"])==m,"unsupported_amount_width")
    operands=[de,amount,mode]
    seen=coordinate_set(dst)
    for ep in operands:
        coords=coordinate_set(ep)
        require(not seen&coords,"overlapping_runtime_or_target_coordinates")
        seen.update(coords)
    lanes=lane_support(n,m)
    return {"operator":"ArithmeticShiftRight","target":dst,"operands":operands,
            "operand_roles":["data","amount","sign_mode"],"sign_msb_evidence":msb,
            "data_width":n,"amount_width":m,"signed_intermediate_width":n+1,
            "output_width":n,"lane_support":lanes,
            "relation":"controlled_signed_shift_local_potential_influence_candidate",
            "representation":"lsb_ordinal_support_per_output_lane",
            "potential_pairs":sum(len(l["data_ordinals"])+len(l["amount_ordinals"])+len(l["mode_ordinals"]) for l in lanes),
            "model_domain":"defined_binary_inputs_only","value_equivalence":"not_proven",
            "guard_feasibility":"not_proven","timing":"not_proven"}


def audit_signed_shifts(ast,index,graph):
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
            raise ValueError("shift_row_budget")
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
                raise ValueError("shift_coordinate_budget")
            row.update(coverage="signed_shift_candidates",candidate=candidate)
        items.append(row)
    good=[r for r in items if r["coverage"]=="signed_shift_candidates"]
    return {"schema_version":1,"scope":"residual_flat_controlled_signed_shift_roots",
            "counts":{"residual_ids":len(residual),"roots":len(items),"supported":len(good),
                      "partial":len(items)-len(good),"potential_pairs":sum(r["candidate"]["potential_pairs"] for r in good),
                      "stored_coordinates":coordinates,"nested_only_rows":len(nested),"truncated":False},
            "nested_only_ids":nested,"partial_reasons":dict(Counter(r["reason"] for r in items if "reason" in r)),
            "items":items,"historical_replay_exact":True,"historical_graph_promoted":False,
            "new_historical_edges":0,"design_coverage":"not_measured","functional_influence":"not_proven",
            "caveat":"Controlled-sign arithmetic right shift, defined-binary local candidates; no global influence, X/Z, guards, timing or RTL proof."}

"""PR112: bounded unsigned logical shifts and an exact constant mask shape."""
import json
from collections import Counter
from .analysis_budgets import inspect_ast
from .array_dependencies import Unsupported,layouts
from .addition_candidates import result_shape,coordinate_set
from .zero_extended_additions import endpoint
from .constant_indices import evaluate
from .bitaccess import build_bit_access_index
from .bitgraph import build_bit_dependency_graph
from .residual_audit import exact_links,reconcile_capture,syntax
from .symbols import SignalResolver
from .typed_layout import raw_layouts

ROOTS={"LogicalShiftLeft","LogicalShiftRight","ArithmeticShiftLeft","ArithmeticShiftRight"}
MAX_ROWS=2000
MAX_COORDINATES=32768
MAX_WIDTH=64
MAX_AMOUNT_BITS=5


def mask_literal(expr):
    # Narrowly match the real ALU mask, not arbitrary constant tags.
    if (not isinstance(expr,dict) or expr.get("kind")!="Conversion" or expr.get("type")!="logic[31:0]"):
        raise Unsupported("unsupported_shift_data")
    c=expr.get("operand")
    if not isinstance(c,dict) or c.get("kind")!="Concatenation" or c.get("type")!="bit[31:0]":
        raise Unsupported("unsupported_shift_data")
    parts=c.get("operands")
    if not isinstance(parts,list) or len(parts)!=1:
        raise Unsupported("unsupported_shift_data")
    lit=parts[0]
    if (not isinstance(lit,dict) or lit.get("kind")!="IntegerLiteral" or lit.get("type")!="bit[31:0]"
            or lit.get("value")!="32'd4294967294"):
        raise Unsupported("unproven_mask_literal")
    if any("constant" in x and x["constant"]!="32'd4294967294" for x in (expr,c,lit)):
        raise Unsupported("mask_constant_disagreement")
    return 4294967294


def lane_support(width,out_width,operator,amount_bits,constant_amount,mask):
    amounts=range(1<<amount_bits) if constant_amount is None else (constant_amount,)
    lanes=[]
    for i in range(out_width):
        def token(k):
            j=i-k if operator=="LogicalShiftLeft" else i+k
            if not 0<=j<width:
                return ("constant",0)
            return ("data",j) if mask is None else ("constant",(mask>>j)&1)
        tokens=[token(k) for k in amounts]
        data=sorted({j for kind,j in tokens if kind=="data"})
        controls=[] if constant_amount is not None else [
            b for b in range(amount_bits) if any(tokens[k]!=tokens[k^(1<<b)] for k in amounts)]
        fixed=tokens[0][1] if all(t==tokens[0] for t in tokens) and tokens[0][0]=="constant" else None
        lanes.append({"data_ordinals":data,"amount_ordinals":controls,"constant_value":fixed})
    return lanes


def expand(node,resolve,raw,declared,constants):
    if (node.get("kind")!="Assignment" or node.get("isNonBlocking") is not False
            or node.get("op") is not None or node.get("timingControl") is not None):
        raise Unsupported("not_plain_blocking_assignment")
    lhs,rhs=node.get("left"),node.get("right")
    if not isinstance(lhs,dict) or not isinstance(rhs,dict) or node.get("type")!=lhs.get("type"):
        raise Unsupported("assignment_type_disagreement")
    state,n=result_shape(lhs)
    if state!="logic" or not 1<=n<=MAX_WIDTH:
        raise Unsupported("unsupported_shift_target")
    dst=endpoint(lhs,resolve,raw,declared,constants)
    opnode=rhs
    if rhs.get("kind")=="Conversion":
        opnode=rhs.get("operand")
        if not isinstance(opnode,dict) or rhs["type"]!=lhs["type"]:
            raise Unsupported("unsupported_result_conversion")
    if not isinstance(opnode,dict) or opnode.get("kind")!="BinaryOp" or opnode.get("op") not in ROOTS:
        raise Unsupported("not_direct_shift")
    operator=opnode["op"]
    if operator not in ("LogicalShiftLeft","LogicalShiftRight"):
        raise Unsupported("signed_or_arithmetic_shift_outside_scope")
    typ,w=result_shape(opnode)
    if typ!="logic" or not n<=w<=MAX_WIDTH or (rhs is opnode and n!=w) or (rhs is not opnode and n>=w):
        raise Unsupported("unsupported_shift_result_width_or_state")
    data,amount=opnode.get("left"),opnode.get("right")
    if result_shape(data)!=("logic",w):
        raise Unsupported("shift_data_width_or_state")
    mask=None
    operands=[]
    if isinstance(data,dict) and data.get("kind")=="Conversion":
        mask=mask_literal(data)
        if w!=32 or operator!="LogicalShiftLeft":
            raise Unsupported("mask_outside_scope")
    else:
        operands.append(endpoint(data,resolve,raw,declared,constants))
    constant_amount=None
    amount_bits=0
    if isinstance(amount,dict) and amount.get("kind")=="IntegerLiteral":
        constant_amount=evaluate(amount,{})
        if constant_amount is None:
            raise Unsupported("unproven_shift_literal")
    else:
        astate,amount_bits=result_shape(amount)
        if astate!="logic" or not 1<=amount_bits<=MAX_AMOUNT_BITS:
            raise Unsupported("shift_amount_width_or_state")
        operands.append(endpoint(amount,resolve,raw,declared,constants))
    eps=[dst,*operands]
    seen=set()
    for e in eps:
        c=coordinate_set(e)
        if e["outer_packed_indices"] or seen&c:
            raise Unsupported("overlapping_or_outer_coordinates")
        seen.update(c)
    lanes=lane_support(w,n,operator,amount_bits,constant_amount,mask)
    return {"operator":operator,"target":dst,"operands":operands,"data_width":w,
            "output_width":n,"amount_width":amount_bits,"constant_amount":constant_amount,
            "constant_data":mask,"lane_support":lanes,
            "operand_roles":(["data"] if mask is None else [])+(["amount"] if constant_amount is None else []),
            "relation":"unsigned_shift_local_potential_influence_candidate",
            "representation":"lsb_ordinal_support_per_output_lane",
            "potential_pairs":sum(len(l["data_ordinals"])+len(l["amount_ordinals"]) for l in lanes),
            "model_domain":"defined_binary_inputs_only","value_equivalence":"not_proven",
            "guard_feasibility":"not_proven","timing":"not_proven"}


def audit_shifts(ast,index,graph):
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
            row.update(coverage="shift_candidates",candidate=candidate)
        items.append(row)
    good=[r for r in items if r["coverage"]=="shift_candidates"]
    return {"schema_version":1,"scope":"residual_flat_unsigned_shift_roots",
            "counts":{"residual_ids":len(residual),"roots":len(items),"supported":len(good),
                      "partial":len(items)-len(good),"potential_pairs":sum(r["candidate"]["potential_pairs"] for r in good),
                      "stored_coordinates":coordinates,"nested_only_rows":len(nested),"truncated":False},
            "nested_only_ids":nested,"partial_reasons":dict(Counter(r["reason"] for r in items if "reason" in r)),
            "items":items,"historical_replay_exact":True,"historical_graph_promoted":False,
            "new_historical_edges":0,"design_coverage":"not_measured","functional_influence":"not_proven",
            "caveat":"Defined-binary local shift lane candidates; no signed arithmetic shifts, global influence, X/Z, guards, timing or RTL proof."}

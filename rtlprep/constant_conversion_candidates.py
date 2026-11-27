"""PR115: exact literal-zero and lexical unsigned-index conversion candidates.

No dynamic conversion policy inferred from slang's missing ConversionKind.
"""
import json
import re
from collections import Counter
from .analysis_budgets import inspect_ast
from .array_dependencies import Unsupported,layouts,layout,decompose
from .zero_extended_additions import endpoint
from .constant_indices import evaluate,integer_value
from .bit_widths import integral_shape,width
from .bitaccess import build_bit_access_index
from .bitgraph import build_bit_dependency_graph
from .residual_audit import exact_links,reconcile_capture,syntax
from .symbols import SignalResolver
from .typed_layout import raw_layouts

ROOTS={"IntegerLiteral","UnbasedUnsizedIntegerLiteral","Call","NamedValue","ElementSelect","RangeSelect"}
MAX_ROWS=2000
MAX_COORDINATES=32768
MAX_CONVERSIONS=4


def require(ok,reason):
    if not ok:
        raise Unsupported(reason)


def shape(expr):
    typ=expr.get("type") if isinstance(expr,dict) else None
    require(isinstance(typ,str) and re.fullmatch(r"(?:logic|bit)(?:\[[0-9]{1,5}:[0-9]{1,5}\])?",typ),
            "not_explicit_unsigned_integral_type")
    sh=integral_shape(typ)
    require(sh is not None and width(sh)<=64,"conversion_layout_or_budget")
    return sh


def folded(expr,value,sh):
    # Tags corroborate independent evaluation, never establish the value.
    if "constant" not in expr:
        return
    raw=expr["constant"]
    require(isinstance(raw,str) and len(raw)<=80,"invalid_folded_tag")
    m=re.fullmatch(r"([1-9][0-9]?)'[bBoOdDhH][0-9a-fA-F]+",raw)
    require(m is not None and int(m[1])==width(sh) and integer_value(raw)==value,
            "folded_value_or_width_disagreement")


def literal_zero(expr):
    sh=shape(expr)
    require(expr.get("type")=="bit[31:0]" and expr.get("value")=="32'd0",
            "not_exact_32bit_zero_literal")
    folded(expr,0,sh)
    return 0


def expand(node,resolve,raw,declared,constants):
    require(isinstance(node,dict) and node.get("kind")=="Assignment"
            and node.get("isNonBlocking") is False and node.get("op") is None
            and node.get("timingControl") is None,"not_plain_blocking_assignment")
    lhs,rhs=node.get("left"),node.get("right")
    dst_shape=shape(lhs)
    require(isinstance(rhs,dict) and rhs.get("kind")=="Conversion" and
            node.get("type")==lhs.get("type")==rhs.get("type"),"not_exact_result_conversion")
    require(dst_shape[3],"target_not_four_state")
    base,selectors=decompose(lhs)
    typ=layout(base.get("type"))
    require(typ is not None and typ[0]=="logic" and not typ[2] and len(typ[1])==2
            and all(a>=b for a,b in typ[1]),"not_descending_packed_word_target")
    require(len(selectors) in (1,2) and selectors[0].get("kind")=="ElementSelect"
            and (len(selectors)==1 or selectors[1].get("kind")=="RangeSelect"),
            "not_fixed_word_or_word_slice")
    dst=endpoint(lhs,resolve,raw,declared,constants)
    require(len(dst["outer_packed_indices"])==1 and len(dst["bits_lsb_first"])==width(dst_shape),
            "target_coordinate_disagreement")
    layers=[]
    expr=rhs
    while isinstance(expr,dict) and expr.get("kind")=="Conversion":
        require(len(layers)<MAX_CONVERSIONS,"conversion_depth_budget")
        sh=shape(expr)
        layers.append((expr,sh))
        expr=expr.get("operand")
    require(isinstance(expr,dict),"missing_conversion_leaf")
    if expr.get("kind")=="IntegerLiteral":
        value=literal_zero(expr)
        family="literal_zero"
        leaf_width=32
    elif expr.get("kind")=="Call":
        require(expr.get("subroutine")=="$unsigned" and expr.get("type")=="logic[31:0]"
                and len(layers)==1 and width(dst_shape)==5 and len(selectors)==1,
                "not_exact_unsigned_index_cast")
        args=expr.get("arguments")
        require(isinstance(args,list) and len(args)==1 and isinstance(args[0],dict),
                "unsigned_call_arity")
        arg=args[0]
        sel=selectors[0].get("selector")
        require(isinstance(sel,dict) and arg.get("kind")==sel.get("kind")=="NamedValue"
                and arg.get("type")==sel.get("type")=="integer"
                and isinstance(arg.get("symbol"),str) and arg.get("symbol")==sel.get("symbol"),
                "unsigned_argument_not_same_lexical_selector")
        value=evaluate(arg,constants)
        require(value is not None and value==evaluate(sel,constants)==dst["outer_packed_indices"][0]
                and 0<=value<=31,"unproven_unsigned_index")
        folded(expr,value,shape(expr))
        family="lexical_unsigned_index"
        leaf_width=32
    else:
        raise Unsupported("unsupported_conversion_leaf")
    steps=[]
    for expr,sh in reversed(layers):
        require(sh[3],"not_four_state_conversion_result")
        value=value&((1<<width(sh))-1)
        folded(expr,value,sh)
        steps.append({"to_type":expr["type"],"to_width":width(sh),"value":value})
    return {"family":family,"target":dst,"operands":[],"leaf_width":leaf_width,"conversion_steps":steps,
            "value":value,"values_lsb_first":[(value>>i)&1 for i in range(width(dst_shape))],
            "relation":"statement_local_constant_conversion_candidate","potential_pairs":0,
            "model_domain":"defined_binary_inputs_only","permanent_constant":"not_inferred",
            "timing":"not_proven","guard_feasibility":"not_proven"}


def audit_constant_conversions(ast,index,graph):
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
    coordinates=0
    for i in sorted(residual):
        node,owner,partial=capture[i]
        syn=syntax(node.get("right"))
        if not syn["scan_complete"]:
            raise ValueError("incomplete_residual_syntax")
        if not syn["leading_conversions"] or syn["root_after_conversions"] not in ROOTS:
            continue
        if len(items)>=MAX_ROWS:
            raise ValueError("conversion_row_budget")
        f=graph["bit_dependency_graph"]["items"][i]
        row={"flat_assignment_id":i,"instance":owner,"target":f["target"],"source_location":f.get("source_location"),
             "assignment_kind":f["assignment_kind"],"procedure_kind":f.get("procedure_kind"),"coverage":"partial"}
        try:
            if partial or f["assignment_kind"]!="continuous":
                raise Unsupported("unsupported_assignment_context")
            candidate=expand(node,lambda e:resolver.resolve_exact(owner,e),raw,declared,constants_by_id[i])
            if candidate["target"]["signal"]!=f["target"]:
                raise Unsupported("assignment_target_identity_mismatch")
        except Unsupported as exc:
            row["reason"]=str(exc)
        else:
            coordinates+=len(candidate["target"]["bits_lsb_first"])+0
            if coordinates>MAX_COORDINATES:
                raise ValueError("conversion_coordinate_budget")
            row.update(coverage="constant_conversion_candidates",candidate=candidate)
        items.append(row)
    good=[r for r in items if r["coverage"]=="constant_conversion_candidates"]
    return {"schema_version":1,"scope":"residual_flat_direct_leaf_conversions",
            "counts":{"residual_ids":len(residual),"roots":len(items),"supported":len(good),
                      "partial":len(items)-len(good),"potential_pairs":0,"value_records":coordinates,
                      "stored_coordinates":coordinates,"truncated":False},
            "partial_reasons":dict(Counter(r["reason"] for r in items if "reason" in r)),
            "items":items,"historical_replay_exact":True,"historical_graph_promoted":False,
            "new_historical_edges":0,"design_coverage":"not_measured","functional_influence":"not_proven",
            "caveat":"Exact statement-local constant conversion values; no permanent signal constants, global influence, X/Z, guards, timing or RTL proof."}

"""Bounded composition of unsigned extension, lexical equality and scalar mux.

PR119: statement-local binary candidates, separate from the historical graph.
"""
import json
from collections import Counter
from .array_dependencies import Unsupported
from .bitaccess import build_bit_access_index
from .capture_audit import audit_capture
from .constant_indices import evaluate
from .dynamic_conversion_candidates import at_pointer, endpoint, require, position_map
from .bit_widths import integral_shape
from .residual_audit import exact_links, reconcile_capture
from .state_conversion_candidates import literal_bits, corroborate
from .symbols import SignalResolver
from .typed_layout import raw_layouts

MAX_ROWS=2000
MAX_PAIRS=16384


def obj(x):
    return x if isinstance(x,dict) else {}


def condition(rhs):
    cs=rhs.get("conditions")
    return obj(cs[0].get("expr")) if isinstance(cs,list) and len(cs)==1 and isinstance(cs[0],dict) else {}


def matches(node):
    lhs,rhs=obj(node.get("left")),obj(node.get("right"))
    eq=condition(rhs)
    return (lhs.get("kind")=="ElementSelect" and rhs.get("kind")=="ConditionalOp"
            and eq.get("kind")=="BinaryOp" and eq.get("op")=="Equality"
            and obj(eq.get("left")).get("kind")=="Conversion"
            and obj(eq.get("right")).get("kind")=="Conversion")


def decoder_model(index):
    require(type(index) is int and 0<=index<32,"decoder_index_out_of_range")
    mode,positions=position_map(integral_shape("logic[5:0]"),integral_shape("logic[31:0]"))
    require(mode=="zero_extend" and positions==list(range(6))+[None]*26,
            "decoder_extension_model_disagreement")
    return {"address_width":6,"comparison_width":32,"zero_fill_count":26,
            "index":index,"comparison":"Equality","false_value":0,
            "true_value":"enable","domain":"defined_binary_inputs_only"}


def expand(node,context,resolve,raw,constants):
    require(context=="continuous","unsupported_assignment_context")
    require(node.get("kind")=="Assignment" and node.get("isNonBlocking") is False
            and node.get("op") is None and node.get("timingControl") is None,
            "not_plain_blocking_assignment")
    require(matches(node),"unsupported_decoder_composition_shape")
    lhs,rhs=node["left"],node["right"]
    eq=condition(rhs)
    require(node.get("type")==lhs.get("type")==rhs.get("type")==eq.get("type")=="logic",
            "not_scalar_logic_composition")
    require(set(rhs["conditions"][0])=={"expr"},"unsupported_conditional_pattern")
    require(all("constant" not in e for e in (lhs,rhs,eq)),"unexpected_runtime_constant_tag")
    base,selector=obj(lhs.get("value")),obj(lhs.get("selector"))
    require(base.get("type")=="logic[31:0]","unsupported_decoder_target_layout")
    target=endpoint(base,resolve,raw)
    require(selector.get("kind")=="NamedValue" and selector.get("type")=="integer",
            "not_lexical_integer_selector")
    require(resolve(selector) is None,"selector_is_runtime_signal")
    k=evaluate(selector,constants)
    require(type(k) is int and 0<=k<32,"unproven_lexical_selector")
    a,b=eq["left"],eq["right"]
    require(a.get("type")==b.get("type")=="logic[31:0]","unsupported_comparison_width_or_sign")
    require("constant" not in a,"unexpected_runtime_constant_tag")
    address=obj(a.get("operand"))
    require(address.get("type")=="logic[5:0]","unsupported_address_layout")
    src=endpoint(address,resolve,raw)
    idx=obj(b.get("operand"))
    require(idx.get("kind")=="NamedValue" and idx.get("type")=="integer"
            and idx.get("symbol")==selector.get("symbol")
            and resolve(idx) is None,"comparison_selector_identity_disagreement")
    require(evaluate(b,constants)==k,"unproven_comparison_index")
    true,false=obj(rhs.get("left")),obj(rhs.get("right"))
    require(true.get("type")=="logic","unsupported_enable_layout")
    enable=endpoint(true,resolve,raw)
    require(false.get("kind")=="Conversion" and false.get("type")=="logic",
            "unsupported_false_branch")
    leaf=obj(false.get("operand"))
    require(leaf.get("kind")=="IntegerLiteral" and leaf.get("type")=="bit[0:0]",
            "unsupported_false_literal")
    bits=literal_bits(leaf.get("value"),1,"bit")
    require(bits==["0"],"nonzero_false_branch")
    corroborate(leaf,1,"bit",bits)
    corroborate(false,1,"logic",bits)
    require(len({src["signal"],enable["signal"],target["signal"]})==3,"overlapping_endpoints")
    model=decoder_model(k)
    pairs=[{"source":src["signal"],"source_bit":b,"target":target["signal"],"target_bit":k,
            "role":"comparison_address"} for b in src["bits_lsb_first"]]
    pairs.append({"source":enable["signal"],"source_bit":0,"target":target["signal"],
                  "target_bit":k,"role":"selected_enable"})
    return {"family":"lexical_equality_zero_mux","target":target["signal"],"target_bit":k,
            "address":src,"enable":enable,"model":model,"pairs":pairs,"potential_pairs":len(pairs),
            "guard_feasibility":"not_proven","timing":"not_proven","global_influence":"not_proven",
            "permanent_constant":"not_inferred","model_domain":"defined_binary_inputs_only"}


def audit_decoder_composition(ast,index,graph):
    census=audit_capture(ast,index,graph)
    _,_,residual,_,_,_=exact_links(graph)
    captured=[]
    replay=build_bit_access_index(ast,expected_top=index["top"],index=index,captured_assignments=captured)
    if json.loads(json.dumps(replay))!=graph["bit_accesses"]:
        raise ValueError("bit_access_replay_disagreement")
    cap=reconcile_capture(replay,captured)
    constants={i:c for i,_,_,_,c,_ in captured}
    resolver,raw=SignalResolver(ast,index),raw_layouts(index)
    rows=[]; count=0
    for occ in census["items"]:
        node=at_pointer(ast,occ["ast_path"])
        if not matches(node):
            continue
        if len(rows)>=MAX_ROWS:
            raise ValueError("decoder_composition_row_budget")
        row={k:occ[k] for k in ("ast_path","instance","context","source","historical_status","flat_assignment_id")}
        i=row["flat_assignment_id"]
        row.update(coverage="partial",historical_residual=i in residual)
        try:
            require(i is not None and i in cap,"missing_exact_capture")
            original,owner,partial=cap[i]
            require(original is node and owner==row["instance"],"capture_identity_disagreement")
            require(not partial,"unsupported_procedural_context")
            candidate=expand(node,row["context"],lambda e:resolver.resolve_exact(owner,e),raw,constants[i])
            historical=graph["bit_dependency_graph"]["items"][i]
            access=replay["items"][i]
            require(historical["target"]==candidate["target"] and
                    access["target_selection"]=={"kind":"bit","index":candidate["target_bit"]},
                    "historical_target_coordinate_disagreement")
        except Unsupported as exc:
            row["reason"]=str(exc)
        else:
            count+=candidate["potential_pairs"]
            if count>MAX_PAIRS:
                raise ValueError("decoder_composition_pair_budget")
            row.update(coverage="decoder_composition_candidates",candidate=candidate)
        rows.append(row)
    good=[r for r in rows if "candidate" in r]
    return {"schema_version":1,"scope":"active_element_target_conditional_equality_conversion_roots",
            "counts":{"ast_occurrences":census["counts"]["ast_occurrences"],
                      "historical_rows":census["counts"]["historical_rows"],"roots":len(rows),
                      "supported":len(good),"partial":len(rows)-len(good),
                      "supported_residual":sum(r["historical_residual"] for r in good),
                      "potential_pairs":count,"truncated":False},
            "items":rows,"partial_reasons":dict(Counter(r["reason"] for r in rows if "reason" in r)),
            "historical_replay_exact":True,"historical_graph_promoted":False,"new_historical_edges":0,
            "design_coverage":"not_measured","functional_influence":"not_proven",
            "caveat":"Only this statement-local binary composition. No X/Z mux semantics, guards, timing, reachability, global influence or RTL equivalence."}

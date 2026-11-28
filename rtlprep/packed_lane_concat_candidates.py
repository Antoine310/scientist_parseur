"""PR121: fixed packed lane concatenation of one selected bit and one literal.

Statement-local coordinates and values only. Keep historical bit graph unchanged.
"""
import json
from collections import Counter
from .array_dependencies import Unsupported, layouts
from .addition_candidates import endpoint
from .bitaccess import build_bit_access_index
from .capture_audit import audit_capture
from .dynamic_conversion_candidates import at_pointer, require
from .residual_audit import exact_links, reconcile_capture
from .state_conversion_candidates import literal_bits, corroborate
from .symbols import SignalResolver
from .typed_layout import raw_layouts

MAX_ROWS=2000
MAX_COORDINATES=32768


def obj(n):
    return n if isinstance(n,dict) else {}


def matches(node):
    lhs,rhs=obj(node.get("left")),obj(node.get("right"))
    parts=rhs.get("operands")
    return (lhs.get("kind")=="ElementSelect" and rhs.get("kind")=="Concatenation"
            and isinstance(parts,list) and len(parts)==2
            and obj(parts[0]).get("kind")=="ElementSelect"
            and obj(parts[1]).get("kind")=="IntegerLiteral")


def lane_model(lane,value):
    require(type(lane) is int and 0<=lane<4,"lane_outside_scope")
    require(type(value) is int and value in (0,1),"nonbinary_lane_literal")
    return {"outer_index":lane,"dynamic_inner_bit":1,"literal_inner_bit":0,
            "literal_value":value,"width":2,"domain":"defined_binary_inputs_only"}


def expand(node,context,resolve,raw,declared):
    require(context in ("continuous","AlwaysComb"),"unsupported_assignment_context")
    require(node.get("kind")=="Assignment" and node.get("isNonBlocking") is False
            and node.get("op") is None and node.get("timingControl") is None,
            "not_plain_blocking_assignment")
    require(matches(node),"unsupported_lane_concat_shape")
    lhs,rhs=node["left"],node["right"]
    src,lit=rhs["operands"]
    require(node.get("type")==lhs.get("type")==rhs.get("type")=="logic[1:0]",
            "lane_concat_result_type_disagreement")
    require(obj(lhs.get("value")).get("kind")=="NamedValue"
            and lhs["value"].get("type")=="logic[3:0][1:0]",
            "unsupported_packed_lane_layout")
    require(src.get("type")=="logic" and obj(src.get("value")).get("kind")=="NamedValue"
            and src["value"].get("type") in ("logic[1:0]","logic[31:0]"),
            "unsupported_source_bit_layout")
    require(all("constant" not in n for n in (lhs,lhs["value"],rhs,src,src["value"])),
            "unexpected_runtime_constant_tag")
    dst=endpoint(lhs,resolve,raw,declared)
    source=endpoint(src,resolve,raw,declared)
    require(len(dst["outer_packed_indices"])==1 and dst["bits_lsb_first"]==[0,1]
            and source["outer_packed_indices"]==[] and len(source["bits_lsb_first"])==1,
            "lane_coordinate_disagreement")
    require(dst["signal"]!=source["signal"],"overlapping_endpoints")
    require(lit.get("type")=="bit[0:0]","unsupported_lane_literal_type")
    bits=literal_bits(lit.get("value"),1,"bit")
    corroborate(lit,1,"bit",bits)
    k=dst["outer_packed_indices"][0]
    v=int(bits[0])
    model=lane_model(k,v)
    return {"family":"selected_bit_literal_packed_lane_concat",
            "target":dst["signal"],"outer_index":k,"model":model,
            "pairs":[{"source":source["signal"],"source_packed_indices":[],
                       "source_bit":source["bits_lsb_first"][0],"target":dst["signal"],
                       "target_packed_indices":[k],"target_bit":1}],
            "local_values":[{"target":dst["signal"],"target_packed_indices":[k],
                             "target_bit":0,"value":v}],
            "potential_pairs":1,"permanent_constant":"not_inferred",
            "guard_feasibility":"not_proven","priority":"not_proven","timing":"not_proven",
            "model_domain":"defined_binary_inputs_only"}


def audit_packed_lane_concat(ast,index,graph):
    census=audit_capture(ast,index,graph)
    _,_,residual,_,_,_=exact_links(graph)
    captured=[]
    replay=build_bit_access_index(ast,expected_top=index["top"],index=index,captured_assignments=captured)
    if json.loads(json.dumps(replay))!=graph["bit_accesses"]:
        raise ValueError("bit_access_replay_disagreement")
    cap=reconcile_capture(replay,captured)
    resolver,raw=SignalResolver(ast,index),raw_layouts(index)
    declared=layouts(index)
    rows=[]; count=0
    for occ in census["items"]:
        node=at_pointer(ast,occ["ast_path"])
        if not matches(node):
            continue
        if len(rows)>=MAX_ROWS:
            raise ValueError("packed_lane_concat_row_budget")
        row={k:occ[k] for k in ("ast_path","instance","context","source","historical_status","flat_assignment_id")}
        i=row["flat_assignment_id"]
        row.update(coverage="partial",historical_residual=i in residual)
        try:
            require(i is not None and i in cap,"missing_exact_capture")
            original,owner,partial=cap[i]
            require(original is node and owner==row["instance"],"capture_identity_disagreement")
            require(not partial,"unsupported_procedural_context")
            candidate=expand(node,row["context"],lambda e:resolver.resolve_exact(owner,e),raw,declared)
            historical=graph["bit_dependency_graph"]["items"][i]
            access=replay["items"][i]
            require(historical["target"]==candidate["target"] and
                    access["target_selection"]=={"kind":"bit","index":candidate["outer_index"]},
                    "historical_target_selection_disagreement")
        except Unsupported as exc:
            row["reason"]=str(exc)
        else:
            count+=candidate["potential_pairs"]
            if 2*count>MAX_COORDINATES:
                raise ValueError("packed_lane_concat_coordinate_budget")
            row.update(coverage="packed_lane_concat_candidates",candidate=candidate)
        rows.append(row)
    good=[r for r in rows if "candidate" in r]
    return {"schema_version":1,"scope":"active_element_target_two_operand_selected_bit_literal_concat",
            "counts":{"ast_occurrences":census["counts"]["ast_occurrences"],
                      "historical_rows":census["counts"]["historical_rows"],"roots":len(rows),
                      "supported":len(good),"partial":len(rows)-len(good),
                      "supported_residual":sum(r["historical_residual"] for r in good),
                      "potential_pairs":count,"local_value_records":count,"stored_coordinates":2*count,"truncated":False},
            "items":rows,"partial_reasons":dict(Counter(r["reason"] for r in rows if "reason" in r)),
            "historical_replay_exact":True,"historical_graph_promoted":False,"new_historical_edges":0,
            "design_coverage":"not_measured","functional_influence":"not_proven",
            "caveat":"Statement-local coordinates and literal values only. Historical target selection index denotes outer lane here, not a flat bit. No permanent constants, X/Z, guards, priority, timing, reachability or RTL equivalence."}

"""PR123: localparam-bounded simple range concatenations.

Separate statement-local position candidates. No guard, priority, timing,
reachability, permanent constant or historical graph promotion claim.
"""
import json
from collections import Counter, defaultdict
from .array_dependencies import Unsupported, layouts
from .zero_extended_additions import endpoint
from .bitaccess import build_bit_access_index
from .capture_audit import audit_capture
from .constant_indices import evaluate, integer_value
from .dynamic_conversion_candidates import at_pointer, require
from .residual_audit import exact_links, reconcile_capture
from .symbols import SignalResolver
from .typed_layout import raw_layouts
from .parameter_mux_candidates import inventory, PARAM_TYPE, obj
from .enum_member_writes import SYMBOL

MAX_ROWS=2000
MAX_COORDINATES=32768
MAX_HISTORICAL_EDGES=100000


def matches(node):
    lhs,rhs=obj(node.get("left")),obj(node.get("right"))
    parts=rhs.get("operands")
    return (lhs.get("kind")=="NamedValue" and rhs.get("kind")=="Concatenation"
            and isinstance(parts,list) and len(parts)==2
            and obj(parts[0]).get("kind")=="NamedValue"
            and obj(parts[1]).get("kind")=="RangeSelect"
            and all(obj(parts[1].get(k)).get("kind")=="NamedValue" for k in ("left","right")))


def bound(expr,owner,resolve,inv):
    parents,parameters=inv
    require(owner in parents and expr.get("kind")=="NamedValue"
            and expr.get("type")==PARAM_TYPE and resolve(owner,expr) is None,
            "unsupported_localparam_reference")
    token=expr.get("symbol")
    m=SYMBOL.fullmatch(token) if isinstance(token,str) else None
    require(m is not None,"malformed_localparam_symbol")
    addr,name=m.groups()
    actual,p=parameters.get(addr,(None,{}))
    require(actual==owner and p.get("name")==name and p.get("type")==PARAM_TYPE
            and p.get("isLocal") is True and p.get("isPort") is False
            and p.get("isBody") is True,"unproven_localparam_identity")
    init=obj(p.get("initializer"))
    require(init.get("kind")=="Conversion" and init.get("type")==PARAM_TYPE
            and obj(init.get("operand")).get("kind")=="IntegerLiteral"
            and obj(init.get("operand")).get("type")=="int","unsupported_localparam_initializer")
    value=evaluate(init,{})
    require(type(value) is int and 0<=value<32,"unsupported_localparam_value")
    require(integer_value(p.get("value"))==value and evaluate(expr,{addr:(name,value)})==value,
            "localparam_value_or_tag_disagreement")
    return addr,(name,value),{"instance":owner,"parameter":name,"value":value,
                              "method":"direct_typed_literal_localparam"}


def range_model(hi,lo):
    require(type(hi) is int and type(lo) is int and 0<=lo<=hi<32 and hi-lo==4,
            "unsupported_range_bounds")
    return {"msb":hi,"lsb":lo,"range_width":5,"result_width":6,
            "scalar_target_bit":5,"domain":"defined_binary_inputs_only"}


def expand(node,context,owner,resolve,raw,declared,inv):
    require(context in ("continuous","AlwaysComb") and node.get("kind")=="Assignment"
            and node.get("isNonBlocking") is False and node.get("op") is None
            and node.get("timingControl") is None,"unsupported_range_concat_assignment")
    require(matches(node),"unsupported_range_concat_shape")
    lhs,rhs=node["left"],node["right"]
    scalar,part=rhs["operands"]
    base=obj(part.get("value"))
    require(node.get("type")==lhs.get("type")==rhs.get("type")=="logic[5:0]"
            and scalar.get("type")=="logic" and base.get("kind")=="NamedValue"
            and base.get("type")=="logic[31:0]" and part.get("selectionKind")=="Simple",
            "range_concat_type_or_selection_disagreement")
    require(all("constant" not in n for n in (lhs,rhs,scalar,part,base)),
            "unexpected_runtime_constant_tag")
    h,hv,hproof=bound(part["left"],owner,resolve,inv)
    l,lv,lproof=bound(part["right"],owner,resolve,inv)
    model=range_model(hv[1],lv[1])
    require(h!=l and part.get("type")==f"logic[{hv[1]}:{lv[1]}]",
            "range_result_type_disagreement")
    local=lambda e:resolve(owner,e)
    dst=endpoint(lhs,local,raw,declared,{})
    src=endpoint(scalar,local,raw,declared,{})
    low=endpoint(part,local,raw,declared,{h:hv,l:lv})
    require(all(x["outer_packed_indices"]==[] for x in (dst,src,low))
            and dst["bits_lsb_first"]==list(range(6)) and src["bits_lsb_first"]==[0]
            and low["bits_lsb_first"]==list(range(lv[1],hv[1]+1))
            and len({dst["signal"],src["signal"],low["signal"]})==3,
            "range_concat_coordinate_disagreement")
    pairs=[{"source":low["signal"],"source_bit":b,"target":dst["signal"],"target_bit":j}
           for j,b in enumerate(low["bits_lsb_first"])]
    pairs.append({"source":src["signal"],"source_bit":0,"target":dst["signal"],"target_bit":5})
    return {"family":"localparam_range_concat","target":dst["signal"],"scalar_source":src["signal"],
            "range_source":low["signal"],"model":model,"bounds":[hproof,lproof],"pairs":pairs,
            "potential_pairs":6,"guard_feasibility":"not_proven","priority":"not_proven",
            "timing":"not_proven","permanent_constant":"not_inferred",
            "model_domain":"defined_binary_inputs_only"}


def historical_agreement(candidate,historical,edges,i):
    expected=[{**p,"value_transform":"position_only","assignment_id":i} for p in candidate["pairs"]]
    if historical["coverage"]=="assignment_local_position_candidates":
        require(historical["edge_count"]==6 and historical["constant_target_bits"]==[]
                and len(edges)==6 and sorted(edges,key=lambda e:e["target_bit"])==expected,
                "historical_position_disagreement")
        return 6
    require(historical["coverage"]=="partial" and historical["edge_count"]==0
            and not edges and historical["constant_target_bits"]==[],
            "unexpected_partial_historical_edges")
    return 0


def audit_localparam_range_concat(ast,index,graph):
    census=audit_capture(ast,index,graph)
    _,_,residual,_,_,_=exact_links(graph)
    captured=[]
    replay=build_bit_access_index(ast,expected_top=index["top"],index=index,captured_assignments=captured)
    if json.loads(json.dumps(replay))!=graph["bit_accesses"]:
        raise ValueError("bit_access_replay_disagreement")
    cap=reconcile_capture(replay,captured)
    resolver,raw=SignalResolver(ast,index),raw_layouts(index)
    declared=layouts(index); inv=inventory(ast)
    flat=graph["bit_dependency_graph"]
    if len(flat["edges"])>MAX_HISTORICAL_EDGES: raise ValueError("historical_edge_budget")
    edges=defaultdict(list)
    for e in flat["edges"]:
        i=e.get("assignment_id")
        if type(i) is not int or not 0<=i<len(flat["items"]):
            raise ValueError("invalid_historical_edge_identity")
        edges[i].append(e)
    rows=[]; count=matched=0
    for occ in census["items"]:
        node=at_pointer(ast,occ["ast_path"])
        if not matches(node): continue
        if len(rows)>=MAX_ROWS: raise ValueError("localparam_range_concat_row_budget")
        row={k:occ[k] for k in ("ast_path","instance","context","source","historical_status","flat_assignment_id")}
        i=row["flat_assignment_id"]
        row.update(coverage="partial",historical_residual=i in residual)
        try:
            require(i is not None and i in cap,"missing_exact_capture")
            original,owner,partial=cap[i]
            require(original is node and owner==row["instance"],"capture_identity_disagreement")
            require(not partial,"unsupported_procedural_context")
            candidate=expand(node,row["context"],owner,resolver.resolve_exact,raw,declared,inv)
            historical=flat["items"][i]; access=replay["items"][i]
            require(historical["target"]==candidate["target"] and access["target_selection"]=={"kind":"whole"},
                    "historical_target_selection_disagreement")
            n=historical_agreement(candidate,historical,edges[i],i)
        except Unsupported as exc:
            row["reason"]=str(exc)
        else:
            count+=candidate["potential_pairs"]; matched+=n
            if count>MAX_COORDINATES: raise ValueError("localparam_range_concat_coordinate_budget")
            row.update(coverage="localparam_range_concat_candidates",candidate=candidate,
                       matched_historical_edges=n)
        rows.append(row)
    good=[r for r in rows if "candidate" in r]
    return {"schema_version":1,"scope":"active_named_target_scalar_and_localparam_range_concat",
            "counts":{"ast_occurrences":census["counts"]["ast_occurrences"],
                      "historical_rows":census["counts"]["historical_rows"],"roots":len(rows),
                      "supported":len(good),"partial":len(rows)-len(good),
                      "supported_residual":sum(r["historical_residual"] for r in good),
                      "potential_pairs":count,"matched_historical_edges":matched,
                      "residual_candidate_pairs":sum(r["candidate"]["potential_pairs"] for r in good if r["historical_residual"]),
                      "stored_coordinates":count,"truncated":False},
            "items":rows,"partial_reasons":dict(Counter(r["reason"] for r in rows if "reason" in r)),
            "historical_replay_exact":True,"historical_graph_promoted":False,"new_historical_edges":0,
            "design_coverage":"not_measured","functional_influence":"not_proven",
            "caveat":"Local binary positions; previously supported edges checked exactly. No X/Z, guard, priority, timing, reachability, permanent constants or RTL equivalence."}

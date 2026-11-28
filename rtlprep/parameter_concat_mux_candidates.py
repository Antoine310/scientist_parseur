"""PR124: configuration-selected zero-prefixed concatenations.

Reuse the exact parameter chain, typed literal checks and packed coordinates.
Inactive branch evidence is separate from selected pairs and local values.
"""
import json
from collections import Counter
from .array_dependencies import Unsupported, layouts
from .addition_candidates import endpoint
from .bitaccess import build_bit_access_index
from .capture_audit import audit_capture
from .constant_indices import evaluate
from .dynamic_conversion_candidates import at_pointer, require
from .residual_audit import exact_links, reconcile_capture
from .state_conversion_candidates import literal_bits, corroborate
from .symbols import SignalResolver
from .typed_layout import raw_layouts
from .parameter_mux_candidates import inventory, parameter_chain, PARAM_TYPE, WORD, obj

MAX_ROWS=2000
MAX_COORDINATES=32768
WIDTHS={"logic[4:0]":5,"logic[2:0]":3}


def matches(node):
    lhs,rhs=obj(node.get("left")),obj(node.get("right"))
    cs=rhs.get("conditions")
    if not (lhs.get("kind")=="NamedValue" and rhs.get("kind")=="ConditionalOp"
            and isinstance(cs,list) and len(cs)==1): return False
    test=obj(obj(cs[0]).get("expr"))
    return (test.get("kind")=="BinaryOp" and test.get("op")=="Equality"
            and obj(test.get("left")).get("kind")=="NamedValue"
            and obj(test.get("right")).get("kind")=="Conversion"
            and obj(rhs.get("left")).get("kind")=="Concatenation"
            and obj(rhs.get("right")).get("kind")=="UnbasedUnsizedIntegerLiteral")


def concat_mux_model(value,widths):
    require(type(value) is int and value in (0,1),"unsupported_parameter_value")
    require(isinstance(widths,(list,tuple)) and all(type(w) is int for w in widths)
            and tuple(widths) in ((5,),(3,),(3,5)),"unsupported_concat_layout")
    return {"parameter_value":value,"operand_widths_msb_first":list(widths),"width":32,
            "zero_prefix_width":32-sum(widths),"selected_branch":"concat" if value else "zero",
            "domain":"defined_binary_inputs_only"}


def zero_literal(node,n,domain,kind):
    require(node.get("kind")==kind,"unsupported_zero_literal_kind")
    typ=f"{domain}[{n-1}:0]"
    require(node.get("type")==typ,"zero_literal_type_disagreement")
    bits=literal_bits(node.get("value"),n,domain)
    require(bits==["0"]*n,"nonzero_literal")
    corroborate(node,n,domain,bits)


def expand(node,context,owner,resolve,raw,declared,inv):
    require(context in ("AlwaysComb","continuous") and node.get("kind")=="Assignment"
            and node.get("isNonBlocking") is False and node.get("op") is None
            and node.get("timingControl") is None,"unsupported_concat_mux_assignment")
    require(matches(node),"unsupported_concat_mux_shape")
    lhs,rhs=node["left"],node["right"]
    cond=rhs["conditions"][0]
    require(set(cond)=={"expr"},"unsupported_conditional_pattern")
    test=cond["expr"]; concat,zero=rhs["left"],rhs["right"]
    require(test.get("type")=="logic" and node.get("type")==lhs.get("type")==rhs.get("type")
            ==concat.get("type")==zero.get("type")==WORD,"concat_mux_type_disagreement")
    compare=test["right"]
    require(compare.get("type")==PARAM_TYPE and obj(compare.get("operand")).get("kind")=="IntegerLiteral"
            and obj(compare.get("operand")).get("type")=="int" and evaluate(compare,{})==1,
            "unsupported_comparison_literal")
    value,chain=parameter_chain(test["left"],owner,resolve,inv)
    corroborate(test,1,"logic",[str(value)])
    zero_literal(zero,32,"logic","UnbasedUnsizedIntegerLiteral")
    parts=concat.get("operands")
    require(isinstance(parts,list) and len(parts) in (2,3)
            and all(isinstance(p,dict) for p in parts),"unsupported_concat_arity")
    prefix,*leaves=parts
    require(all(p.get("kind")=="NamedValue" and p.get("type") in WIDTHS for p in leaves),
            "unsupported_concat_leaf")
    widths=[WIDTHS[p["type"]] for p in leaves]
    model=concat_mux_model(value,widths)
    n=model["zero_prefix_width"]
    zero_literal(prefix,n,"bit","IntegerLiteral")
    require(all("constant" not in p for p in [lhs,concat,*leaves]),"unexpected_runtime_constant_tag")
    if value==0: corroborate(rhs,32,"logic",["0"]*32)
    else: require("constant" not in rhs,"unexpected_runtime_constant_tag")
    local=lambda e:resolve(owner,e)
    dst=endpoint(lhs,local,raw,declared)
    src=[endpoint(p,local,raw,declared) for p in leaves]
    require(dst["outer_packed_indices"]==[] and dst["bits_lsb_first"]==list(range(32))
            and all(ep["outer_packed_indices"]==[] and ep["bits_lsb_first"]==list(range(w))
                    for ep,w in zip(src,widths))
            and len({dst["signal"],*(ep["signal"] for ep in src)})==1+len(src),
            "concat_mux_coordinate_disagreement")
    pairs=[]; offset=0
    for ep,w in reversed(list(zip(src,widths))):
        pairs.extend({"source":ep["signal"],"source_bit":b,"target":dst["signal"],
                      "target_bit":offset+b} for b in range(w))
        offset+=w
    def zeros(start):
        return [{"target":dst["signal"],"target_bit":b,"value":0} for b in range(start,32)]
    return {"family":"parameter_selected_zero_prefix_concat_mux","target":dst["signal"],
            "model":model,"parameter_chain":chain,"sources_msb_first":[p["signal"] for p in src],
            "pairs":pairs if value else [],"alternative_positions":[] if value else pairs,
            "local_values":zeros(offset if value else 0),
            "inactive_zero_prefix_values":[] if value else zeros(offset),
            "potential_pairs":len(pairs) if value else 0,"permanent_constant":"not_inferred",
            "guard_feasibility":"not_proven","priority":"not_proven","timing":"not_proven",
            "model_domain":"defined_binary_inputs_only"}


def audit_parameter_concat_mux(ast,index,graph):
    census=audit_capture(ast,index,graph)
    _,_,residual,_,_,_=exact_links(graph)
    captured=[]
    replay=build_bit_access_index(ast,expected_top=index["top"],index=index,captured_assignments=captured)
    if json.loads(json.dumps(replay))!=graph["bit_accesses"]:
        raise ValueError("bit_access_replay_disagreement")
    cap=reconcile_capture(replay,captured)
    resolver,raw=SignalResolver(ast,index),raw_layouts(index)
    declared=layouts(index)
    inv=inventory(ast)
    rows=[]; count=values=alternatives=inactive_zeros=0
    for occ in census["items"]:
        node=at_pointer(ast,occ["ast_path"])
        if not matches(node):
            continue
        if len(rows)>=MAX_ROWS:
            raise ValueError("parameter_concat_mux_row_budget")
        row={k:occ[k] for k in ("ast_path","instance","context","source","historical_status","flat_assignment_id")}
        i=row["flat_assignment_id"]
        row.update(coverage="partial",historical_residual=i in residual)
        try:
            require(i is not None and i in cap,"missing_exact_capture")
            original,owner,partial=cap[i]
            require(original is node and owner==row["instance"],"capture_identity_disagreement")
            require(not partial,"unsupported_procedural_context")
            candidate=expand(node,row["context"],owner,resolver.resolve_exact,raw,declared,inv)
            historical=graph["bit_dependency_graph"]["items"][i]
            access=replay["items"][i]
            require(historical["target"]==candidate["target"] and
                    access["target_selection"]=={"kind":"whole"},
                    "historical_target_selection_disagreement")
        except Unsupported as exc:
            row["reason"]=str(exc)
        else:
            count+=candidate["potential_pairs"]
            values+=len(candidate['local_values']); alternatives+=len(candidate['alternative_positions'])
            inactive_zeros+=len(candidate['inactive_zero_prefix_values'])
            if count+values+alternatives+inactive_zeros>MAX_COORDINATES:
                raise ValueError("parameter_concat_mux_coordinate_budget")
            row.update(coverage="parameter_concat_mux_candidates",candidate=candidate)
        rows.append(row)
    good=[r for r in rows if "candidate" in r]
    return {"schema_version":1,"scope":"active_named_target_parameter_equality_zero_prefixed_concat_mux",
            "counts":{"ast_occurrences":census["counts"]["ast_occurrences"],
                      "historical_rows":census["counts"]["historical_rows"],"roots":len(rows),
                      "supported":len(good),"partial":len(rows)-len(good),
                      "supported_residual":sum(r["historical_residual"] for r in good),
                      "potential_pairs":count,"local_value_records":values,"inactive_alternative_positions":alternatives,"inactive_zero_prefix_records":inactive_zeros,"stored_coordinates":count+values+alternatives+inactive_zeros,"truncated":False},
            "items":rows,"partial_reasons":dict(Counter(r["reason"] for r in rows if "reason" in r)),
            "historical_replay_exact":True,"historical_graph_promoted":False,"new_historical_edges":0,
            "design_coverage":"not_measured","functional_influence":"not_proven",
            "caveat":"Configuration-specific local values and selected branch pairs; inactive dynamic positions and inactive prefix values are separate evidence, not selected pairs or permanent constants. No permanent constants, X/Z, guards, priority, timing, reachability or RTL equivalence."}

"""Opt-in typed position channel, distinct from historical signal/flat graphs.

Coordinates are checked against exact index types and producer field layout,
not independently bound member declarations. No global equality, priority,
reachability or functional influence claim.
"""
from collections import Counter
from copy import deepcopy

from .array_dependencies import Unsupported
from .packed_members import integral, fields
from .local_packed_members import local_types, field_layout, coordinates
from .typed_layout import Types, raw_layouts
from .member_occurrences import collect_linked
from .member_evidence import natural

MAX_POSITIONS = 32768


def layout_for(raw, owner, types, locals_):
    if not isinstance(raw, str):
        raise Unsupported("unproven_endpoint_type")
    if (owner, raw) in locals_:
        members=field_layout(raw,owner,locals_)
        return {"kind":"packed_struct_offset","members":{
            name:[offset,list(map(list,coords))] for name,(_,coords,offset) in members.items()}}
    try:
        _,members=fields(raw,types)
    except Unsupported as exc:
        if "budget" in str(exc):
            raise
    else:
        return {"kind":"packed_struct_offset","members":{
            name:[offset,[[bit] for bit in bits]] for name,(_,bits,offset) in members.items()}}
    try:
        _,bits=integral(raw,types)
    except Unsupported as exc:
        if "budget" in str(exc):
            raise
        coords=coordinates(raw)
        if not coords or len(coords[0])!=2:
            raise Unsupported("unproven_endpoint_layout") from exc
        return {"kind":"packed_vector_coordinates","coordinates":list(map(list,coords))}
    return {"kind":"declared_index","indices":bits}


def endpoint(signal,raw,layout,bit,field=None,field_coord=None,coords=None):
    if not isinstance(signal,str) or not natural(bit):
        raise Unsupported("invalid_endpoint")
    kind=layout["kind"]
    result={"signal":signal,"coordinate_kind":kind,"position":bit}
    if kind=="declared_index":
        if bit not in layout["indices"] or field is not None or field_coord is not None or coords is not None:
            raise Unsupported("invalid_declared_index")
    elif kind=="packed_struct_offset":
        members=layout["members"]
        if not isinstance(field,str) or field not in members or coords is not None:
            raise Unsupported("unproven_endpoint_field")
        offset,lanes=members[field]
        if not offset<=bit<offset+len(lanes):
            raise Unsupported("offset_outside_field")
        expected=lanes[bit-offset]
        if field_coord is not None and field_coord!=expected:
            raise Unsupported("field_coordinate_disagreement")
        result.update(field=field,field_coordinates=expected)
    elif kind=="packed_vector_coordinates":
        lanes=layout["coordinates"]
        if bit>=len(lanes) or coords!=lanes[bit] or field is not None or field_coord is not None:
            raise Unsupported("packed_coordinate_disagreement")
        result["coordinates"]=coords
    else:
        raise Unsupported("unknown_coordinate_kind")
    # Preserve qualified type name, not the process-local slang address.
    result["declared_type"]=raw.split(" ",1)[1] if raw.split(" ",1)[0].isdecimal() and " " in raw else raw
    return result


def field_info(p,side):
    field=p.get(side+"_field")
    if isinstance(field,dict):
        name=field.get("field")
        bit=field.get("field_bit")
        if not natural(bit):
            raise Unsupported("invalid_field_index")
        return name,[bit]
    if side=="target" and "field" in p:
        return p["field"],[p["field_bit"]]
    coord=p.get(side+"_field_coordinates")
    if coord is None and side+"_field_bit" in p:
        coord=[p[side+"_field_bit"]]
    return field,coord


def compare_history(items,graph):
    # Pair presence ignores occurrence and edge kind; not an identity test.
    pairs={(e["source"],e["target"]) for e in graph["edges"]}
    flat={(e["source"],e["source_bit"],e["target"],e["target_bit"])
          for e in graph["bit_dependency_graph"]["edges"]}
    counts=Counter({"signal_pair_present":0,"signal_pair_absent":0,
                    "flat_coordinate_comparable":0,"flat_coordinate_incomparable":0,
                    "flat_endpoint_tuple_present":0,"flat_endpoint_tuple_absent":0})
    for item in items:
        s,t=item["source"],item["target"]
        counts["signal_pair_present" if (s["signal"],t["signal"]) in pairs else "signal_pair_absent"]+=1
        if s["coordinate_kind"]==t["coordinate_kind"]=="declared_index":
            counts["flat_coordinate_comparable"]+=1
            key=(s["signal"],s["position"],t["signal"],t["position"])
            counts["flat_endpoint_tuple_present" if key in flat else "flat_endpoint_tuple_absent"]+=1
        else:
            counts["flat_coordinate_incomparable"]+=1
    return dict(counts)


def build_member_positions(ast,index,graph):
    envelope,_,linked=collect_linked(ast,index)
    if any(linked["counts"][k] for k in ("duplicate_records","candidate_disagreement_groups","mixed_coordinate_groups")):
        raise Unsupported("unresolved_member_candidate_overlap")
    types=Types(ast)
    if types.truncated:
        raise Unsupported("package_inventory_budget")
    locals_=local_types(ast)
    raw=raw_layouts(index)
    nodes=set(graph["nodes"])
    by_row={rid:g for g in linked["occurrences"] for rid in g["row_ids"]}
    cache={}
    items=[]
    for r in envelope["records"]:
        if r["category"]!="position":
            continue
        if len(items)>=MAX_POSITIONS:
            raise Unsupported("member_position_channel_budget")
        p=r["payload"]
        occurrence=by_row[r["row_id"]]
        owner=occurrence["instance"]
        if occurrence["context"] not in ("continuous","AlwaysComb"):
            raise Unsupported("unsupported_position_context")
        endpoints=[]
        for side in ("source","target"):
            sig=p[side]
            if sig not in nodes or sig not in raw:
                raise Unsupported("unproven_endpoint_signal")
            key=(owner,sig)
            if key not in cache:
                cache[key]=layout_for(raw[sig],owner,types,locals_)
            field,coord=field_info(p,side)
            packed=side=="target" and "target_packed_offset" in p
            lay=cache[key]
            if packed!=(lay["kind"]=="packed_vector_coordinates"):
                raise Unsupported("endpoint_coordinate_kind_disagreement")
            endpoints.append(endpoint(sig,raw[sig],lay,p["target_packed_offset"] if packed else p[side+"_bit"],
                                      field,coord,p.get("target_coordinates") if packed else None))
        items.append({"record_id":r["record_id"],"producer":r["producer"],"row_id":r["row_id"],
                      "occurrence_ordinal":occurrence["occurrence_ordinal"],"instance":owner,
                      "context":occurrence["context"],"source_location":deepcopy(occurrence["source"]),
                      "source":endpoints[0],"target":endpoints[1],"payload":deepcopy(p)})
    counts={"positions":len(items),"multidimensional_targets":sum(
        i["target"]["coordinate_kind"]=="packed_vector_coordinates" for i in items),
        "position_occurrences":len({i["occurrence_ordinal"] for i in items}),
        "signal_pairs":len({(i["source"]["signal"],i["target"]["signal"]) for i in items}),
        "other_candidate_records_not_promoted":len(envelope["records"])-len(items),
        **compare_history(items,graph)}
    return {"schema_version":1,"scope":"assignment_local_typed_member_position_candidates",
            "items":items,"counts":counts,"identity":"same_ast_traversal_only",
            "truncated":False,"design_coverage":"not_measured","functional_influence":"not_proven",
            "formal_proof":"not_performed",
            "caveat":"Opt-in channel, not appended to flat or signal edges. Member identity depends on serialized type/token evidence. "
                     "Signal-pair and compatible flat endpoint comparisons ignore occurrence and are not semantic deduplication. "
                     "No global equality, priority, timing, reachability or functional influence proof."}

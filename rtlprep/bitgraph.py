"""Assignment-local bit dependency candidates from validated bit-access rows."""
from collections import defaultdict
import re
from .bit_widths import integral_shape

MAX_EDGES = 16384
MAX_WIDTH = 1024


def packed_bounds(type_string):
    """Recognize only scalar or one-dimensional descending packed types."""
    if type_string in ("logic","bit"):
        return (0,0)
    if not isinstance(type_string,str) or len(type_string)>96:
        return None
    match=re.fullmatch(r"(?:logic|bit)\[(\d+):(\d+)\]",type_string)
    if match is None:
        return None
    hi,lo=map(int,match.groups())
    if not 0<=lo<=hi<=65535 or hi-lo+1>MAX_WIDTH:
        return None
    return hi,lo


def declared_bounds(index, *, extended=False):
    def parse(raw):
        if not extended:
            return packed_bounds(raw)
        shape=integral_shape(raw)
        return shape[:2] if shape is not None else None
    candidates=defaultdict(set)
    for instance in index["instances"]:
        for port in instance["ports"]:
            candidates[instance["path"]+"."+port["name"]].add(parse(port.get("type")))
    for signal in index["signals"]:
        name=signal.get("path") or signal["instance_path"]+"."+signal["name"]
        candidates[name].add(parse(signal.get("type")))
    return {name:next(iter(values)) for name,values in candidates.items()
            if len(values)==1 and None not in values}


def selected_bounds(selection,bounds):
    if bounds is None or not isinstance(selection,dict):
        raise ValueError("unproven_packed_layout")
    hi,lo=bounds
    kind=selection.get("kind")
    if kind=="whole":
        return hi,lo
    if kind=="bit":
        start=end=selection.get("index")
    elif kind=="range":
        start,end=selection.get("lsb"),selection.get("msb")
    else:
        raise ValueError("unsupported_selection")
    if type(start) is not int or type(end) is not int or not lo<=start<=end<=hi:
        raise ValueError("selection_outside_declared_bounds")
    return end,start


def source_positions(selection,bounds,lanes,depth=0):
    if depth>12 or not isinstance(selection,dict):
        raise ValueError("invalid_conversion_view")
    if selection.get("kind")!="conversion_view":
        hi,lo=selected_bounds(selection,bounds)
        if hi-lo+1!=lanes:
            raise ValueError("source_width_mismatch")
        return list(range(lo,hi+1))
    span=selection.get("base_width")
    offset=selection.get("offset")
    repeat=selection.get("repeat")
    if (type(span) is not int or not 1<=span<=MAX_WIDTH
            or type(offset) is not int or not 0<=offset<span
            or type(repeat) is not bool or selection.get("width")!=lanes
            or (not repeat and offset+lanes>span)):
        raise ValueError("invalid_conversion_view")
    base=source_positions(selection.get("base"),bounds,span,depth+1)
    return [base[offset]]*lanes if repeat else base[offset:offset+lanes]


def expand_assignment(row,bounds):
    """Atomically expand one row; never emit a partial bit map."""
    if row.get("coverage") not in ("explicit_target_lanes","rhs_lanes_only"):
        raise ValueError("partial_bit_access")
    if row.get("bit_graph_eligible") is not True:
        raise ValueError("unvalidated_ast_positions")
    if row.get("assignment_kind")=="procedural":
        # Preserve syntax only; no local final-write or NBA priority analysis.
        if row.get("procedure_kind") not in ("AlwaysFF","AlwaysComb","AlwaysLatch","Always"):
            raise ValueError("unsupported_procedure")
    target=row["target"]
    hi,lo=selected_bounds(row["target_selection"],bounds.get(target))
    width=row.get("rhs_width")
    if type(width) is not int or width!=hi-lo+1 or not 1<=width<=MAX_WIDTH:
        raise ValueError("target_rhs_width_mismatch")
    segments=row.get("source_segments")
    if not isinstance(segments,list) or not 1<=len(segments)<=32:
        raise ValueError("invalid_segments")
    occupied=set()
    edges=[]
    constant_lanes=[]
    for seg in segments:
        start,end=seg.get("rhs_lsb"),seg.get("rhs_msb")
        if type(start) is not int or type(end) is not int or not 0<=start<=end<width:
            raise ValueError("invalid_rhs_lane")
        lanes=set(range(start,end+1))
        if occupied & lanes:
            raise ValueError("overlapping_rhs_lanes")
        occupied.update(lanes)
        if row["coverage"]=="explicit_target_lanes" and (
            seg.get("target_lsb")!=lo+start or seg.get("target_msb")!=lo+end):
            raise ValueError("inconsistent_target_lanes")
        transform=seg.get("value_transform","position_only")
        if transform not in ("position_only","bitwise_not"):
            raise ValueError("unsupported_transform")
        source=seg.get("source")
        if source is None:
            if seg.get("selection",{}).get("kind") not in ("literal","constant_reference") or seg["selection"].get("width")!=len(lanes):
                raise ValueError("unknown_source")
            constant_lanes.extend(lo+k for k in sorted(lanes))
            continue
        if seg["selection"].get("kind")=="conversion_view" and not row.get("width_conversions"):
            raise ValueError("unvalidated_conversion_view")
        positions=source_positions(seg["selection"],bounds.get(source),len(lanes))
        for offset,source_bit in enumerate(positions):
            edges.append({"source":source,"source_bit":source_bit,
                          "target":target,"target_bit":lo+start+offset,
                          "value_transform":transform})
    if len(occupied)!=width:
        raise ValueError("missing_rhs_lanes")
    return edges,sorted(constant_lanes)


def build_bit_dependency_graph(access,index):
    if access.get("schema_version")!=1 or index.get("schema_version")!=1:
        raise ValueError("bit access and index v1 required")
    bounds=declared_bounds(index)
    extended_bounds=declared_bounds(index,extended=True)
    edges=[]
    items=[]
    truncated=bool(access["counts"]["truncated"])
    for i,row in enumerate(access["items"]):
        item={"assignment_id":i,"target":row["target"],"source_location":row.get("source"),
              "assignment_kind":row.get("assignment_kind","continuous"),
              "procedure_kind":row.get("procedure_kind"),"guards":row.get("guards",[]),
              "events":row.get("events",[]),"nonblocking":row.get("nonblocking"),
              "coverage":"partial","edge_count":0,"constant_target_bits":[]}
        items.append(item)
        try:
            local,constants=expand_assignment(row,extended_bounds if row.get("width_conversions") else bounds)
        except (ValueError,KeyError,TypeError,AttributeError) as exc:
            item["reason"]=str(exc)
            continue
        if len(edges)+len(local)>MAX_EDGES:
            truncated=True
            item["reason"]="edge_budget_exceeded"
            continue
        edges.extend({**edge,"assignment_id":i} for edge in local)
        item.update(coverage="assignment_local_position_candidates",edge_count=len(local),
                    constant_target_bits=constants)
    return {"schema_version":1,"scope":"assignment_local_bit_position_candidates",
            "items":items,"edges":edges,"counts":{"assignments":len(items),
                "supported":sum(r["coverage"]!="partial" for r in items),
                "partial":sum(r["coverage"]=="partial" for r in items),
                "edges":len(edges),"truncated":truncated},
            "caveat":"Only observed assignment-local positions, not global writers, functional "
                     "influence, value equivalence, priority, timing or complete design coverage."}

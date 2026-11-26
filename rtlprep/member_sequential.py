"""Opt-in statement-local nonblocking assignment candidates.

A sampled RHS and a deferred update are not a complete next-state relation.
No event, clock domain, reset priority, guard feasibility or writer dominance
is inferred. All published endpoints are typed packed struct offsets.
"""
from collections import defaultdict
from copy import deepcopy

from .aggregate_layout import assignment_sites
from .array_dependencies import Unsupported
from .member_positions import layout_for, endpoint, field_info
from .local_packed_members import local_types
from .typed_layout import Types, raw_layouts
from .symbols import SignalResolver

MAX_RECORDS=32768
MAX_OCCURRENCES=100000
CATEGORIES=("nba_sampled","nba_constant")


def check_nba_node(node,context,row):
    if (context!="AlwaysFF" or row.get("context")!=context
            or row.get("coverage")!="nba_assignment_candidates"
            or row.get("kind")!="StructuredAssignmentPattern"
            or not isinstance(node,dict) or node.get("kind")!="Assignment"
            or node.get("isNonBlocking") is not True
            or node.get("op") is not None or node.get("timingControl") is not None):
        raise Unsupported("unproven_nba_statement")
    lhs,rhs=node.get("left"),node.get("right")
    if (not isinstance(lhs,dict) or lhs.get("kind")!="NamedValue"
            or not isinstance(rhs,dict) or rhs.get("kind")!="StructuredAssignmentPattern"
            or not isinstance(lhs.get("type"),str)
            or rhs.get("type")!=lhs["type"] or node.get("type")!=lhs["type"]):
        raise Unsupported("unproven_nba_pattern_type")
    return lhs


def validate_partition(items,layout,target):
    if layout.get("kind")!="packed_struct_offset":
        raise Unsupported("unproven_nba_target_layout")
    expected={offset+i for offset,coords in layout["members"].values()
              for i in range(len(coords))}
    positions=[]
    for r in items:
        t=r["target"]
        if t["signal"]!=target or t["coordinate_kind"]!="packed_struct_offset":
            raise Unsupported("nba_target_disagreement")
        positions.append(t["position"])
    if len(positions)!=len(set(positions)) or set(positions)!=expected or not expected:
        raise Unsupported("incomplete_or_overlapping_nba_partition")
    return len(expected)


def _build_sequential(ast,index,graph,envelope,linked):
    if any(linked["counts"][k] for k in ("duplicate_records","candidate_disagreement_groups","mixed_coordinate_groups")):
        raise Unsupported("unresolved_member_candidate_overlap")
    types=Types(ast)
    if types.truncated:
        raise Unsupported("package_inventory_budget")
    locals_=local_types(ast)
    raw=raw_layouts(index)
    resolver=SignalResolver(ast,index)
    nodes=set(graph["nodes"])
    rows={r["row_id"]:r["payload"] for r in envelope["rows"]}
    by_row={rid:g for g in linked["occurrences"] for rid in g["row_ids"]}
    records=[r for r in envelope["records"] if r["category"] in CATEGORIES]
    if len(records)>MAX_RECORDS:
        raise Unsupported("member_sequential_channel_budget")
    needed={by_row[r["row_id"]]["occurrence_ordinal"] for r in records}
    inventory={}
    for ordinal,site in enumerate(assignment_sites(ast)):
        if ordinal>=MAX_OCCURRENCES:
            raise Unsupported("nba_occurrence_inventory_budget")
        if ordinal in needed:
            inventory[ordinal]=site
    if set(inventory)!=needed:
        raise Unsupported("missing_nba_occurrence")
    cache={}
    groups=defaultdict(list)
    targets={}
    collections={k:[] for k in CATEGORIES}
    def get_endpoint(owner,p,side):
        sig=p[side]
        if sig not in nodes or sig not in raw:
            raise Unsupported("unproven_endpoint_signal")
        key=(owner,sig)
        if key not in cache:
            cache[key]=layout_for(raw[sig],owner,types,locals_)
        lay=cache[key]
        if lay["kind"]!="packed_struct_offset":
            raise Unsupported("unproven_nba_endpoint_layout")
        field,coord=field_info(p,side)
        return endpoint(sig,raw[sig],lay,p[side+"_bit"],field,coord)
    for r in records:
        rid=r["row_id"]
        row=rows[rid]
        occ=by_row[rid]
        ordinal=occ["occurrence_ordinal"]
        owner,context,node=inventory[ordinal]
        if owner!=occ["instance"] or context!=occ["context"] or r["producer"]!="pr84":
            raise Unsupported("nba_occurrence_disagreement")
        lhs=check_nba_node(node,context,row)
        p=r["payload"]
        dest=resolver.resolve_exact(owner,lhs)
        if dest is None or p["target"]!=dest or raw.get(dest)!=lhs["type"]:
            raise Unsupported("unproven_nba_target_identity")
        category=r["category"]
        item={"record_id":r["record_id"],"producer":r["producer"],"row_id":rid,
              "occurrence_ordinal":ordinal,"instance":owner,"context":context,
              "source_location":deepcopy(occ["source"]),"payload":deepcopy(p),
              "target":get_endpoint(owner,p,"target"),
              "update_semantics":"deferred_nonblocking_when_executed",
              "guard_feasibility":"not_proven","writer_priority":"not_proven",
              "event_binding":"not_performed"}
        if category=="nba_sampled":
            if raw.get(p["source"])!=raw.get(dest) or "value" in p:
                raise Unsupported("nba_source_type_disagreement")
            item["source"]=get_endpoint(owner,p,"source")
            item["semantics"]="rhs_sampled_when_statement_executes"
        else:
            if type(p.get("value")) is not int or p["value"] not in (0,1) or "source" in p:
                raise Unsupported("invalid_nba_constant")
            item["value"]=p["value"]
            item["semantics"]="constant_rhs_when_statement_executes"
        groups[ordinal].append(item)
        targets[ordinal]=(owner,dest)
        collections[category].append(item)
    partitions=[]
    for ordinal,items in groups.items():
        owner,dest=targets[ordinal]
        width=validate_partition(items,cache[(owner,dest)],dest)
        partitions.append({"occurrence_ordinal":ordinal,"target":dest,"width":width,
                           "record_ids":[r["record_id"] for r in items],
                           "scope":"complete_statement_target_positions_only"})
    return {"schema_version":1,"scope":"assignment_local_member_nba_candidates",
            "collections":collections,"partitions":partitions,
            "counts":{"nba_sampled":len(collections["nba_sampled"]),"nba_constant":len(collections["nba_constant"]),
                      "records":len(records),"occurrences":len(groups),"complete_statement_partitions":len(partitions),
                      "other_candidate_records_not_promoted":len(envelope["records"])-len(records)},
            "identity":"same_ast_traversal_only","truncated":False,"design_coverage":"not_measured",
            "functional_influence":"not_proven","formal_proof":"not_performed",
            "caveat":"RHS sampled when the NBA statement executes, update deferred. Complete statement partition is not a "
                     "global next-state proof. No guard feasibility, last-writer priority, reset/clock event binding, "
                     "cycle latency or reachability proof. Field identity conditional on serialized metadata. "
                     "No historical graph promotion."}

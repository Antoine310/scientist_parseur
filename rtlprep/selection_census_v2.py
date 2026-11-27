"""Versioned conservative selection census, separate from historical graph."""
import json
from collections import Counter
from .capture_audit import audit_capture, inventory, Budget, reconcile
from .bitaccess import build_bit_access_index
from .bitgraph import build_bit_dependency_graph
from .residual_audit import reconcile_capture


def canonical(obj):
    return json.loads(json.dumps(obj))


def compare_versions(old_audit,new_rows,old_access,new_access,old_graph,new_graph):
    """Map by AST pointer and instance, never by line or ordinal coincidence."""
    def keyed(rows):
        result={}
        for row in rows:
            key=(row["instance"],row["ast_path"])
            if key in result:
                raise ValueError("duplicate_version_occurrence")
            result[key]=row
        return result
    old=keyed(old_audit["items"])
    new=keyed(new_rows)
    if set(old)!=set(new):
        raise ValueError("version_inventory_disagreement")
    mapping={}
    added=[]
    for key,prior in old.items():
        now=new[key]
        if prior["classification"]=="captured":
            if now["classification"]!="captured":
                raise ValueError("historical_capture_lost")
            a,b=prior["flat_assignment_id"],now["flat_assignment_id"]
            if a in mapping or b in mapping.values():
                raise ValueError("duplicate_version_mapping")
            mapping[a]=b
        elif prior["classification"]=="selection_gate_missed_syntax":
            if now["classification"]!="captured":
                raise ValueError("selection_omission_not_recovered")
            added.append({"instance":key[0],"ast_path":key[1],"old_flat_assignment_id":None,
                          "new_flat_assignment_id":now["flat_assignment_id"],"source":prior["source"],
                          "lhs_kind":prior["lhs_kind"],"rhs_kind":prior["rhs_kind"],
                          "selections":prior["selections"],"call_argument_selection":prior["call_argument_selection"],
                          "coverage":"partial","reason":"selection_census_v2_semantics_not_validated"})
        elif now["classification"]!=prior["classification"]:
            raise ValueError("unintended_classification_change")
    old_ids=set(range(len(old_access["items"])))
    new_ids=set(range(len(new_access["items"])))
    extra_ids={r["new_flat_assignment_id"] for r in added}
    if set(mapping)!=old_ids or len(extra_ids)!=len(added) or set(mapping.values())&extra_ids or set(mapping.values())|extra_ids!=new_ids:
        raise ValueError("version_id_partition_disagreement")
    for a,b in mapping.items():
        if canonical(old_access["items"][a])!=canonical(new_access["items"][b]):
            raise ValueError("historical_access_row_changed")
        prev=old_graph["items"][a]
        curr=new_graph["items"][b]
        if canonical({**prev,"assignment_id":b})!=canonical(curr):
            raise ValueError("historical_graph_row_changed")
    for b in extra_ids:
        a=new_access["items"][b]
        g=new_graph["items"][b]
        if (a["coverage"]!="partial" or a.get("reason")!="selection_census_v2_semantics_not_validated"
                or a["bit_graph_eligible"] is not False or a["source_segments"]
                or g["coverage"]!="partial" or g["edge_count"]!=0 or g["constant_target_bits"]):
            raise ValueError("new_row_semantics_promoted")
    mapped_edges=[{**e,"assignment_id":mapping[e["assignment_id"]]} for e in old_graph["edges"]]
    # Sorting canonical serialized edge objects permits only an order change.
    if sorted(json.dumps(e,sort_keys=True) for e in mapped_edges)!=sorted(json.dumps(e,sort_keys=True) for e in new_graph["edges"]):
        raise ValueError("historical_edges_changed")
    if new_graph["counts"]["truncated"] or new_access["counts"]["truncated"]:
        raise ValueError("version_truncated")
    return {"old_to_new":[{"old_flat_assignment_id":a,"new_flat_assignment_id":mapping[a]} for a in sorted(mapping)],
            "added":added}


def audit_selection_v2(ast,index,graph):
    old=audit_capture(ast,index,graph)
    captured=[]
    trace=[]
    access=build_bit_access_index(ast,expected_top=index["top"],index=index,
        captured_assignments=captured,capture_trace=trace,selection_census_v2=True)
    if access["counts"]["truncated"] or len(trace)!=access["counts"]["assignments_seen"]:
        raise ValueError("incomplete_v2_capture")
    budget=Budget()
    sites=inventory(ast,{r["path"] for r in index["instances"]},budget)
    rows=reconcile(sites,trace,reconcile_capture(access,captured),budget)
    flat=build_bit_dependency_graph(access,index)
    maps=compare_versions(old,rows,graph["bit_accesses"],access,graph["bit_dependency_graph"],flat)
    counts=Counter(r["classification"] for r in rows)
    if counts["captured"]!=access["counts"]["captured"] or counts["unsupported_target"]!=access["counts"]["unsupported_targets"]:
        raise ValueError("v2_count_disagreement")
    added=maps["added"]
    by_instance=dict(Counter(r["instance"] for r in added))
    return {"schema_version":2,"scope":"selection_admission_v2_separate_from_historical_graph",
            "historical_census_version":1,"counts":{"ast_occurrences":len(rows),
            "historical_rows":old["counts"]["historical_rows"],"v2_rows":len(access["items"]),
            "new_partial_rows":len(added),"new_supported_rows":0,"new_edges":0,
            "historical_supported":graph["bit_dependency_graph"]["counts"]["supported"],
            "v2_supported":flat["counts"]["supported"],"classification":dict(counts),
            "added_with_call_argument_selection":sum(r["call_argument_selection"] for r in added)},
            "added_by_instance":by_instance,"historical_replay_exact":True,"historical_projection_exact":True,
            "id_mapping":maps["old_to_new"],"added":added,"v2_items":rows,
            "v2_bit_accesses":access,"v2_bit_dependency_graph":flat,
            "design_coverage":"not_measured","functional_influence":"not_proven",
            "caveat":"Versioned syntax admission only. New rows deliberately partial, no semantic promotion. Historical graph unchanged."}

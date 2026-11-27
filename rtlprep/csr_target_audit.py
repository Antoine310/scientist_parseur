"""PR107: reconcile historical rejected targets with exact scoped identity
and existing member-position evidence. No new position or semantic channel.
"""
from collections import Counter, defaultdict
from .aggregate_layout import assignment_sites
from .bitaccess import _base, _Partial, _target_name
from .symbols import SignalResolver, member_name
from .typed_layout import raw_layouts
from .member_occurrences import collect_linked
from .member_positions import _build_member_positions
from .walker_exclusion_audit import audit_walker, ancestors

MAX_SITES=20000
MAX_ORDINALS=100000


def ordinal_index(sites):
    result={}
    for i,(owner,context,node) in enumerate(sites):
        if i>=MAX_ORDINALS:
            raise ValueError("csr_ordinal_budget")
        k=(owner,id(node))
        if k in result:
            raise ValueError("duplicate_assignment_identity")
        result[k]=(i,context)
    return result


def classify_target(lhs,owner,known,resolver,declared,scopes):
    """Replay the actual legacy target gate, then inspect exact declaration."""
    if _target_name(lhs,known,owner,resolver) is not None:
        raise ValueError("historical_target_refusal_disagreement")
    kind=lhs.get("kind")
    base=lhs.get("value") if kind=="MemberAccess" else lhs
    if not isinstance(base,dict) or base.get("kind")!="NamedValue":
        return {"reason":"other_target_shape","exact_target":None,"field":None}
    sig=resolver.resolve_exact(owner,base)
    if sig is None or declared.get(sig)!=base.get("type"):
        return {"reason":"unproven_exact_declaration","exact_target":None,"field":None}
    if kind=="MemberAccess":
        field=member_name(lhs)
        return {"reason":"member_access_outside_legacy_target_gate","exact_target":sig,"field":field}
    try:
        _base(lhs,known,owner,resolver)
    except _Partial as exc:
        reason=str(exc)
    else:
        raise ValueError("historical_base_refusal_disagreement")
    if scopes.get(sig) and sig.startswith(owner+".") and sig.rsplit(".",1)[0]!=owner:
        classification="generate_scoped_target_outside_legacy_flat_gate"
    else:
        classification="other_named_target_refusal"
    return {"reason":classification,"exact_target":sig,"field":None,"legacy_base_reason":reason}


def select_existing(ordinal,identity,positions):
    """Exact occurrence linkage; source lines never serve as join keys."""
    selected=[]
    for r in positions:
        if r["occurrence_ordinal"]!=ordinal:
            raise ValueError("position_ordinal_disagreement")
        target=r["target"]
        if (identity["exact_target"]!=target["signal"] or identity["field"]!=target.get("field")
                or target["coordinate_kind"]!="packed_struct_offset"
                or r["category"]!="position"):
            raise ValueError("member_target_evidence_disagreement")
        selected.append({k:r[k] for k in ("record_id","row_id","producer","source","target")})
    if len({r["record_id"] for r in selected})!=len(selected):
        raise ValueError("duplicate_member_position_record")
    return selected


def audit_targets(ast,index,graph):
    prior=audit_walker(ast,index,graph)
    known={i["path"]:{p["name"] for p in i["ports"]} for i in index["instances"]}
    scopes={}
    for sig in index["signals"]:
        path=sig.get("path") or sig["instance_path"]+"."+sig["name"]
        scopes[path]=sig.get("scope")
        if not sig.get("scope"):
            known[sig["instance_path"]].add(sig["name"])
    resolver=SignalResolver(ast,index)
    declared=raw_layouts(index)
    nodes=set(graph["nodes"])
    ordinals=ordinal_index(assignment_sites(ast))
    env,_,linked=collect_linked(ast,index)
    members=_build_member_positions(ast,index,graph,env,linked)
    by_ordinal=defaultdict(list)
    for item in members["items"]:
        by_ordinal[item["occurrence_ordinal"]].append({**item,"category":"position"})
    groups={g["occurrence_ordinal"]:g for g in linked["occurrences"]}
    result=[]
    for row in prior["unsupported_targets"]:
        if len(result)>=MAX_SITES:
            raise ValueError("csr_target_site_budget")
        owner=row["instance"]
        node=ancestors(ast,row["ast_path"])[-1][1]
        key=(owner,id(node))
        if key not in ordinals:
            raise ValueError("missing_exact_assignment_identity")
        ordinal,context=ordinals[key]
        if context!=row["context"]:
            raise ValueError("assignment_context_disagreement")
        identity=classify_target(node["left"],owner,known[owner],resolver,declared,scopes)
        sig=identity["exact_target"]
        if sig is not None and sig not in nodes:
            raise ValueError("exact_target_not_in_signal_graph")
        group=groups.get(ordinal)
        if group is not None and (group["instance"]!=owner or group["context"]!=context):
            raise ValueError("member_occurrence_metadata_disagreement")
        positions=select_existing(ordinal,identity,by_ordinal.get(ordinal,[]))
        if positions and (group is None or not {p["record_id"] for p in positions}<=set(group["record_ids"])):
            raise ValueError("member_record_link_disagreement")
        result.append({**row,**identity,"occurrence_ordinal":ordinal,"historical_flat_assignment_id":None,
                       "existing_member_row_ids":list(group["row_ids"]) if group else [],
                       "existing_member_record_ids":list(group["record_ids"]) if group else [],
                       "existing_typed_positions":positions,
                       "member_channel_status":"existing_position_evidence" if positions else "no_linked_position_evidence",
                       "new_records":0})
    return {"schema_version":1,"scope":"historical_unsupported_target_identity_and_existing_member_overlap",
            "counts":{"historical_unsupported_targets":len(result),
                      "reason_counts":dict(Counter(r["reason"] for r in result)),
                      "existing_position_occurrences":sum(bool(r["existing_typed_positions"]) for r in result),
                      "existing_position_records":sum(len(r["existing_typed_positions"]) for r in result),
                      "without_linked_member_positions":sum(not r["existing_typed_positions"] for r in result),
                      "new_records":0,"new_edges":0},
            "items":result,"historical_replay_exact":True,"historical_graph_promoted":False,
            "design_coverage":"not_measured","functional_influence":"not_proven",
            "caveat":"Exact overlap with the existing typed member channel only; absence is not absence of all evidence. "
                     "No new mapping, guard, priority, temporal or RTL proof. Serialized member identity remains conditional."}

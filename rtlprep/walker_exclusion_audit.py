"""Explain nonvisited syntax occurrences using actual historical stop decisions.

No procedural execution, initial-state semantics, new capture or graph mutation.
"""
from collections import Counter
import json
import re
from .capture_audit import audit_capture, MAX_SITES
from .bitaccess import build_bit_access_index
from .bitgraph import build_bit_dependency_graph

MAX_PATH_DEPTH=128
MAX_PATH_CHARS=4096
MAX_EVENTS=20000
REASONS={"excluded_procedure_kind","unsupported_statement_kind",
         "non_assignment_expression_statement","assignment_expression_boundary"}
SUPPORTED_PROCEDURES={"AlwaysFF","AlwaysComb","AlwaysLatch","Always"}


def ancestors(ast,path):
    """Resolve exact escaped JSON pointer; reject malformed or excessive paths."""
    if not isinstance(path,str) or not path.startswith("/design/members/") or len(path)>MAX_PATH_CHARS:
        raise ValueError("invalid_occurrence_pointer")
    tokens=path[1:].split("/")
    if len(tokens)>MAX_PATH_DEPTH:
        raise ValueError("occurrence_pointer_depth_budget")
    node=ast
    result=[]
    prefix=""
    for token in tokens:
        if re.search(r"~(?![01])",token):
            raise ValueError("invalid_pointer_escape")
        key=token.replace("~1","/").replace("~0","~")
        if isinstance(node,list):
            if not re.fullmatch(r"0|[1-9][0-9]*",key) or len(key)>10 or int(key)>=len(node):
                raise ValueError("invalid_pointer_index")
            node=node[int(key)]
        elif isinstance(node,dict) and key in node:
            node=node[key]
        else:
            raise ValueError("unresolved_occurrence_pointer")
        prefix+="/"+token
        if isinstance(node,dict):
            result.append((prefix,node))
    if not isinstance(node,dict) or node.get("kind")!="Assignment":
        raise ValueError("pointer_not_assignment")
    return result


def event_index(events):
    if len(events)>MAX_EVENTS:
        raise ValueError("walk_exclusion_event_budget")
    indexed={}
    for owner,node,reason in events:
        if not isinstance(owner,str) or not isinstance(node,dict) or reason not in REASONS:
            raise ValueError("invalid_exclusion_event")
        key=(owner,id(node))
        if key in indexed:
            raise ValueError("duplicate_exclusion_event")
        kind=node.get("kind")
        if reason=="excluded_procedure_kind":
            if kind!="ProceduralBlock" or node.get("procedureKind") in SUPPORTED_PROCEDURES:
                raise ValueError("invalid_procedure_exclusion")
        elif reason=="non_assignment_expression_statement":
            if kind!="ExpressionStatement" or (isinstance(node.get("expr"),dict) and node["expr"].get("kind")=="Assignment"):
                raise ValueError("invalid_expression_exclusion")
        elif reason=="assignment_expression_boundary" and kind!="Assignment":
            raise ValueError("invalid_assignment_boundary")
        indexed[key]=reason
    return indexed


def explain(ast,rows,events):
    """Partition only PR102 nonvisited occurrences. Unexplained stays explicit."""
    indexed=event_index(events)
    if len(rows)>MAX_SITES:
        raise ValueError("walk_exclusion_site_budget")
    excluded=[]
    targets=[]
    keys=set()
    used=set()
    for row in rows:
        key=(row["instance"],row["ast_path"])
        if key in keys:
            raise ValueError("duplicate_occurrence")
        keys.add(key)
        cls=row["classification"]
        if cls not in ("not_visited_by_historical_walker","unsupported_target"):
            continue
        chain=ancestors(ast,row["ast_path"])
        node=chain[-1][1]
        lhs=node.get("left")
        lhs_kind=lhs.get("kind") if isinstance(lhs,dict) else None
        if lhs_kind!=row["lhs_kind"]:
            raise ValueError("occurrence_lhs_disagreement")
        base={k:row[k] for k in ("instance","ast_path","source","context","lhs_kind","rhs_kind","selections")}
        if cls=="unsupported_target":
            targets.append({**base,"classification":"unsupported_target",
                "reason":"concatenation_target_outside_historical_target_gate" if lhs_kind=="Concatenation" else "target_gate_refused_other",
                "new_edges":0})
            continue
        # Proper ancestors only: an assignment boundary is not evidence that
        # the directly visited assignment itself was omitted.
        matches=[(path,obj,indexed[(row["instance"],id(obj))]) for path,obj in chain[:-1]
                 if (row["instance"],id(obj)) in indexed]
        if len(matches)>1:
            raise ValueError("ambiguous_exclusion_boundary")
        if matches:
            path,obj,reason=matches[0]
            if reason=="excluded_procedure_kind" and obj.get("procedureKind")!=row["context"]:
                raise ValueError("procedure_context_disagreement")
            used.add((row["instance"],id(obj)))
            boundary={"ast_path":path,"kind":obj.get("kind"),"procedure_kind":obj.get("procedureKind")}
        else:
            reason="unexplained_not_visited"
            boundary=None
        excluded.append({**base,"reason":reason,"boundary":boundary,
                         "has_selection_syntax":bool(row["selections"]),
                         "classification":"not_visited_by_historical_walker"})
    reasons=Counter(r["reason"] for r in excluded)
    return {"nonvisited":excluded,"unsupported_targets":targets,
            "reason_counts":dict(sorted(reasons.items())),
            "procedure_kind_counts":dict(Counter(r["context"] for r in excluded if r["reason"]=="excluded_procedure_kind")),
            "nonvisited_with_selection":sum(r["has_selection_syntax"] for r in excluded),
            "matched_exclusion_boundaries":len(used),"unexplained":reasons["unexplained_not_visited"]}


def audit_walker(ast,index,graph):
    prior=audit_capture(ast,index,graph)
    events=[]
    replay=build_bit_access_index(ast,expected_top=index["top"],index=index,walk_exclusions=events)
    if json.loads(json.dumps(replay))!=graph["bit_accesses"]:
        raise ValueError("walker_access_replay_disagreement")
    if json.loads(json.dumps(build_bit_dependency_graph(replay,index)))!=graph["bit_dependency_graph"]:
        raise ValueError("walker_graph_replay_disagreement")
    if sum(reason=="excluded_procedure_kind" for _,_,reason in events)!=replay["counts"]["procedural_blocks_skipped"]:
        raise ValueError("skipped_process_count_disagreement")
    details=explain(ast,prior["items"],events)
    classes=prior["counts"]["classification"]
    if len(details["nonvisited"])!=classes.get("not_visited_by_historical_walker",0) or len(details["unsupported_targets"])!=classes.get("unsupported_target",0):
        raise ValueError("exclusion_partition_disagreement")
    return {"schema_version":1,"scope":"historical_walker_stop_evidence_pr67_occurrences",
            "counts":prior["counts"],"historical_replay_exact":True,
            "event_counts":dict(Counter(reason for _,_,reason in events)),
            "procedural_blocks_skipped":replay["counts"]["procedural_blocks_skipped"],
            "new_edges":0,"new_supported_rows":0,
            "design_coverage":"not_measured","functional_influence":"not_proven",
            "caveat":"Observed stop boundary, not proof of intentional design semantics or execution. Initial and unsupported contexts remain excluded.",
            **details}

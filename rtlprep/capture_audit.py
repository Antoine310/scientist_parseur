"""PR102: separate, bounded syntax occurrence / historical capture reconciliation.

Identity is object identity in one parsed AST, published as JSON pointer + instance.
No source-line matching, execution counting, or historical coverage promotion.
"""
import json
from collections import Counter
from .analysis_budgets import inspect_ast
from .bitaccess import build_bit_access_index
from .bitgraph import build_bit_dependency_graph
from .residual_audit import exact_links, reconcile_capture

MAX_VISITS=2_000_000
MAX_SITES=20000
MAX_DEPTH=128
MAX_SELECTIONS=100000
META={"type","definition","internalSymbol","symbol","addr","subroutine"}
EXCLUDED={"Function","Task","Subroutine","Variable","Net","Parameter","TypeAlias"}
SELECT={"ElementSelect","RangeSelect","Concatenation"}


class AuditLimit(ValueError):
    pass


def pointer(path,key):
    return path+"/"+str(key).replace("~","~0").replace("/","~1")


def children(obj,path):
    if isinstance(obj,list):
        for i,v in enumerate(obj):
            if isinstance(v,(dict,list)):
                yield v,pointer(path,i),str(i)
    elif isinstance(obj,dict):
        for k in sorted(obj):
            v=obj[k]
            if k not in META and isinstance(v,(dict,list)):
                yield v,pointer(path,k),k


class Budget:
    def __init__(self,max_visits=MAX_VISITS,max_sites=MAX_SITES,max_depth=MAX_DEPTH,max_selections=MAX_SELECTIONS):
        for value,cap in zip((max_visits,max_sites,max_depth,max_selections),(MAX_VISITS,MAX_SITES,MAX_DEPTH,MAX_SELECTIONS)):
            if type(value) is not int or not 1<=value<=cap:
                raise ValueError("invalid_capture_audit_budget")
        self.max_visits=max_visits
        self.max_sites=max_sites
        self.max_depth=max_depth
        self.max_selections=max_selections
        self.visits=0
        self.selections=0

    def visit(self,depth):
        self.visits+=1
        if self.visits>self.max_visits or depth>self.max_depth:
            raise AuditLimit("capture_audit_visit_or_depth_budget")


def inventory(ast,instances,budget):
    """Independent active process/continuous occurrence census (PR67 scope)."""
    sites=[]
    def walk(obj,path,owner,context,depth):
        budget.visit(depth)
        if isinstance(obj,list):
            for v,p,_ in children(obj,path):
                walk(v,p,owner,context,depth+1)
            return
        if not isinstance(obj,dict) or obj.get("isUninstantiated") is True:
            return
        k=obj.get("kind")
        if k=="Instance":
            name=obj.get("name")
            if not isinstance(name,str):
                raise ValueError("unnamed_instance")
            owner=(owner+"." if owner else "")+name
            if owner not in instances:
                raise ValueError("unindexed_instance")
            walk(obj["body"]["members"],path+"/body/members",owner,None,depth+2)
            return
        if k in ("GenerateBlock","GenerateBlockArray","Scope"):
            walk(obj.get("members"),path+"/members",owner,context,depth+1)
            return
        if k in ("ContinuousAssign","ProceduralBlock"):
            field="assignment" if k=="ContinuousAssign" else "body"
            ctx="continuous" if k=="ContinuousAssign" else obj.get("procedureKind") or "procedural_unknown"
            walk(obj.get(field),pointer(path,field),owner,ctx,depth+1)
            return
        if context is None or k in EXCLUDED:
            return
        if k=="Assignment":
            if len(sites)>=budget.max_sites:
                raise AuditLimit("capture_audit_site_budget")
            sites.append((obj,path,owner,context))
        for v,p,_ in children(obj,path):
            walk(v,p,owner,context,depth+1)
    walk(ast["design"]["members"],"/design/members",None,None,0)
    return sites


def selections(node,budget):
    """Walk all expression container fields, not the legacy selection whitelist."""
    result=[]
    def scan(obj,path,in_call,depth):
        budget.visit(depth)
        if isinstance(obj,dict) and obj.get("kind") in SELECT:
            budget.selections+=1
            if budget.selections>budget.max_selections:
                raise AuditLimit("capture_audit_selection_budget")
            result.append({"path":path,"kind":obj["kind"],"inside_call_arguments":in_call})
        for child,p,key in children(obj,path):
            scan(child,p,in_call or (isinstance(obj,dict) and obj.get("kind")=="Call" and key=="arguments"),depth+1)
    for side in ("left","right"):
        scan(node.get(side),"/"+side,False,0)
    return result


def reconcile(sites,trace,captured,budget):
    """One row per occurrence, exact identity or fail closed."""
    identities={}
    for node,path,owner,context in sites:
        key=(owner,id(node))
        if key in identities:
            raise ValueError("duplicate_ast_object_occurrence")
        identities[key]=(node,path,owner,context)
    attempts={}
    for owner,node,status in trace:
        key=(owner,id(node))
        if key not in identities or key in attempts:
            raise ValueError("trace_identity_disagreement")
        if status not in ("captured","selection_gate_negative","unsupported_target"):
            raise ValueError("unknown_or_incomplete_trace_status")
        attempts[key]=status
    linked={}
    for ordinal,(node,owner,_) in captured.items():
        key=(owner,id(node))
        if key in linked or attempts.get(key)!="captured":
            raise ValueError("capture_trace_disagreement")
        linked[key]=ordinal
    if set(linked)!={k for k,v in attempts.items() if v=="captured"}:
        raise ValueError("capture_trace_incomplete")
    rows=[]
    for key,(node,path,owner,context) in identities.items():
        sel=selections(node,budget)
        status=attempts.get(key,"not_visited")
        if status=="selection_gate_negative":
            reason="selection_gate_missed_syntax" if sel else "no_selection_syntax_in_operands"
        else:
            reason={"captured":"captured","unsupported_target":"unsupported_target",
                    "not_visited":"not_visited_by_historical_walker"}[status]
        rows.append({"ast_path":path,"instance":owner,"context":context,
                     "source":{"file":node.get("source_file_start") or node.get("source_file"),
                               "line":node.get("source_line_start") or node.get("source_line")},
                     "lhs_kind":node.get("left",{}).get("kind") if isinstance(node.get("left"),dict) else None,
                     "rhs_kind":node.get("right",{}).get("kind") if isinstance(node.get("right"),dict) else None,
                     "historical_status":status,"classification":reason,
                     "flat_assignment_id":linked.get(key),"selections":sel,
                     "call_argument_selection":any(x["inside_call_arguments"] for x in sel)})
    return rows


def audit_capture(ast,index,graph,budget=None):
    inspect_ast(ast)
    if graph["analysis_limits"]["truncated_analyzers"]:
        raise ValueError("truncated_historical_analyzers")
    exact_links(graph)
    budget=budget if budget is not None else Budget()
    instances={r["path"] for r in index["instances"]}
    sites=inventory(ast,instances,budget)
    captured=[]
    trace=[]
    replay=build_bit_access_index(ast,expected_top=index["top"],index=index,
                                  captured_assignments=captured,capture_trace=trace)
    if json.loads(json.dumps(replay))!=graph["bit_accesses"]:
        raise ValueError("bit_access_replay_disagreement")
    if json.loads(json.dumps(build_bit_dependency_graph(replay,index)))!=graph["bit_dependency_graph"]:
        raise ValueError("flat_replay_disagreement")
    if len(trace)!=replay["counts"]["assignments_seen"]:
        raise ValueError("trace_count_disagreement")
    rows=reconcile(sites,trace,reconcile_capture(replay,captured),budget)
    counts=Counter(r["classification"] for r in rows)
    if counts["captured"]!=replay["counts"]["captured"] or counts["unsupported_target"]!=replay["counts"]["unsupported_targets"]:
        raise ValueError("historical_count_disagreement")
    if sum(counts.values())!=len(sites) or len({r["ast_path"] for r in rows})!=len(rows):
        raise ValueError("occurrence_partition_disagreement")
    by_instance={}
    for row in rows:
        by_instance.setdefault(row["instance"] or "<unattributed>",Counter())[row["classification"]]+=1
    return {"schema_version":1,"scope":"active_process_continuous_ast_occurrences_pr67",
            "counts":{"ast_occurrences":len(rows),"historical_rows":counts["captured"],
                      "historical_attempts":len(trace),"classification":dict(counts),
                      "missed_with_call_argument_selection":sum(r["classification"]=="selection_gate_missed_syntax" and r["call_argument_selection"] for r in rows)},
            "by_instance":{k:dict(v) for k,v in by_instance.items()},
            "visits":budget.visits,"selection_occurrences":budget.selections,
            "complete_within_scope":True,"historical_replay_exact":True,"items":rows,
            "design_coverage":"not_measured","functional_influence":"not_proven",
            "caveat":"Syntax occurrences, not execution or unsupported semantics. Call bodies, declarations and inactive generates outside scope. No graph promotion."}

"""Reconciled observed analyzer inventories; no inferred design coverage."""
from collections import Counter
from rtlprep.analysis_budgets import ANALYZERS, nested_truncated, inspect_ast
from rtlprep.complex_constructs import LOOPS, METADATA

UNKNOWN="<unattributed>"

def owner_for(path, instances):
    if isinstance(path,str):
        for name in sorted(instances,key=lambda p:(-len(p),p)):
            if path==name or path.startswith(name+"."):
                return name
    return UNKNOWN

def location(row):
    for key in ("source_location","source"):
        loc=row.get(key)
        if isinstance(loc,dict) and isinstance(loc.get("file"),str):
            return {"file":loc["file"],"line":loc.get("line")}
    return None

def ast_inventory(ast,instances):
    """Independent syntax census of active process/continuous subtrees.

    Assignment occurrences include expression assignments, including ones
    that an analyzer would exclude. No one-to-one matching with rows.
    Declaration bodies/initializers are outside this census. No execution.
    """
    inspect_ast(ast)
    counts={p:Counter() for p in [*instances,UNKNOWN]}
    assignment_sites=[]
    def walk(node,owner=None,context=None):
        if isinstance(node,list):
            for item in node:
                yield from walk(item,owner,context)
            return
        if not isinstance(node,dict):
            return
        kind=node.get("kind")
        if node.get("isUninstantiated") is True:
            return
        if kind=="Instance":
            path=(owner+"." if owner else "")+node["name"]
            yield from walk(node["body"]["members"],path,None)
            return
        if kind in ("GenerateBlock","GenerateBlockArray","Scope"):
            yield from walk(node.get("members"),owner,context)
            return
        if kind=="ProceduralBlock":
            counts[owner if owner in instances else UNKNOWN]["procedural_block"]+=1
            yield from walk(node.get("body"),owner,node.get("procedureKind") or "procedural_unknown")
            return
        if kind=="ContinuousAssign":
            counts[owner if owner in instances else UNKNOWN]["continuous_block"]+=1
            yield from walk(node.get("assignment"),owner,"continuous")
            return
        if context is None or kind in ("Function","Task","Subroutine","Variable","Net","Parameter","TypeAlias"):
            return
        bucket=owner if owner in instances else UNKNOWN
        if kind=="Assignment":
            lhs=node.get("left")
            rhs=node.get("right")
            entry={"instance":bucket,"context":context,
                   "lhs_kind":lhs.get("kind") if isinstance(lhs,dict) else None,
                   "rhs_kind":rhs.get("kind") if isinstance(rhs,dict) else None,
                   "source":{"file":node.get("source_file_start") or node.get("source_file"),
                             "line":node.get("source_line_start") or node.get("source_line")}}
            counts[bucket]["assignment_ast"]+=1
            yield entry
        elif kind in LOOPS or kind in ("Call","ElementSelect","RangeSelect","Conditional","Case"):
            counts[bucket][kind]+=1
        for key,child in node.items():
            if key not in METADATA and isinstance(child,(dict,list)):
                yield from walk(child,owner,context)
    assignment_sites.extend(walk(ast["design"]["members"]))
    return {"scope":"active_procedural_and_continuous_syntax_occurrences_not_analyzer_denominator",
            "by_instance":{p:dict(c) for p,c in counts.items()},
            "assignment_sites":assignment_sites,"assignment_count":len(assignment_sites),
            "design_coverage":"not_measured"}

def summarize_rows(graph,index):
    instances={r["path"]:r["module"] for r in index["instances"]}
    if len(instances)!=len(index["instances"]):
        raise ValueError("duplicate instance paths")
    limits=graph["analysis_limits"]["analyzers"]
    result={}
    for name,(_,counter,_) in ANALYZERS.items():
        if name in ("bitwise_dependencies","mux_dependencies","dynamic_dependencies","selector_recovery","typed_layout") and name not in graph:
            continue
        data=graph[name]
        rows=data["items"]
        if len(rows)!=data["counts"][counter] or len(rows)!=limits[name]["captured"]:
            raise ValueError("captured count mismatch: "+name)
        buckets={p:{"status_counts":Counter(),"partial_reasons":Counter(),"captured":0,
                    "nested_truncation":0} for p in [*instances,UNKNOWN]}
        details=[]
        for ordinal,row in enumerate(rows):
            owner=row.get("instance")
            if owner is None:
                owner=owner_for(row.get("target"),instances)
            elif owner not in instances:
                owner=UNKNOWN
            bucket=buckets[owner]
            status=row.get("coverage") or "unknown"
            reason=str(row.get("reason") or "partial_record") if status=="partial" else None
            bucket["captured"]+=1
            bucket["status_counts"][status]+=1
            nested=nested_truncated(row)
            bucket["nested_truncation"]+=int(nested)
            if reason:
                bucket["partial_reasons"][reason]+=1
            if status in ("partial","unknown") or nested:
                details.append({"row_index":ordinal,"instance":owner,"target":row.get("target"),
                    "source":location(row),"coverage":status,"reason":reason,
                    "nested_truncation":nested})
        status_total=Counter()
        reasons_total=Counter()
        for bucket in buckets.values():
            status_total.update(bucket["status_counts"])
            reasons_total.update(bucket["partial_reasons"])
        if dict(status_total)!=limits[name]["status_counts"] or sum(b["captured"] for b in buckets.values())!=len(rows):
            raise ValueError("status count mismatch: "+name)
        # PR62 truncates reason strings for its summary, not raw rows.
        clipped=Counter()
        for reason,n in reasons_total.items():
            clipped[reason[:160]]+=n
        if dict(clipped)!=limits[name]["partial_reasons"]:
            raise ValueError("partial reason count mismatch: "+name)
        if sum(b["nested_truncation"] for b in buckets.values())!=limits[name]["rows_with_nested_truncation"]:
            raise ValueError("nested truncation mismatch: "+name)
        result[name]={"counts":data["counts"],"limits":limits[name],"by_instance":buckets,
                      "partial_or_unknown_or_nested_rows":details,
                      "truncation_events":data.get("truncation_events")}
    return result

def bit_inventory(graph,instances):
    access=graph["bit_accesses"]["items"]
    bits=graph["bit_dependency_graph"]
    rows=bits["items"]
    if len(access)!=len(rows):
        raise ValueError("bit assignment/access mismatch")
    edges=Counter()
    for e in bits["edges"]:
        ordinal=e.get("assignment_id")
        if type(ordinal) is not int or not 0<=ordinal<len(rows):
            raise ValueError("invalid bit edge assignment ID")
        if e["target"]!=rows[ordinal]["target"]:
            raise ValueError("bit edge target mismatch")
        edges[ordinal]+=1
    by={p:Counter() for p in [*instances,UNKNOWN]}
    details=[]
    for ordinal,(a,b) in enumerate(zip(access,rows)):
        if b["assignment_id"]!=ordinal or a["target"]!=b["target"] or b["edge_count"]!=edges[ordinal]:
            raise ValueError("bit row reconciliation failed")
        owner=owner_for(b["target"],instances)
        status="partial" if b["coverage"]=="partial" else "supported"
        by[owner]["assignments"]+=1
        by[owner][status]+=1
        by[owner]["edges"]+=edges[ordinal]
        by[owner]["constant_target_bits"]+=len(b.get("constant_target_bits",[]))
        if status=="partial":
            details.append({"assignment_id":ordinal,"instance":owner,"target":b["target"],
                            "source":location(b) or location(a),"assignment_kind":b.get("assignment_kind"),
                            "procedure_kind":b.get("procedure_kind"),"bit_access_coverage":a.get("coverage"),
                            "bit_access_reason":a.get("reason"),"bit_graph_reason":b.get("reason"),
                            "reason":a.get("reason") if b.get("reason")=="partial_bit_access" and a.get("reason") else b.get("reason") or "unknown"})
    total=Counter()
    for bucket in by.values():
        total.update(bucket)
    for key in ("assignments","supported","partial","edges"):
        if total[key]!=bits["counts"][key]:
            raise ValueError("bit total mismatch: "+key)
    return {"counts":bits["counts"],"by_instance":{p:dict(c) for p,c in by.items()},
            "partial_reasons":dict(Counter(r["reason"] for r in details)),
            "partial_assignments":details,"constant_target_bits":total["constant_target_bits"]}

def diagnose(graph,index,ast):
    instances={r["path"]:r["module"] for r in index["instances"]}
    if graph["top"]!=index["top"]:
        raise ValueError("top mismatch")
    warnings=[{"instance":owner_for(w.get("context"),instances),**w,
               "source":location(w)} for w in graph["warnings"]]
    if len(warnings)!=graph["counts"]["warnings"]:
        raise ValueError("warning count mismatch")
    analyzers=summarize_rows(graph,index)
    bits=bit_inventory(graph,instances)
    census=ast_inventory(ast,instances)
    return {"top":graph["top"],"source_fingerprint":graph["source_fingerprint"],
            "instances":instances,"graph_counts":graph["counts"],"analyzers":analyzers,
            "bit_inventory":bits,"syntax_census":census,"warnings":warnings,
            "warning_reasons":dict(Counter(w["reason"] for w in warnings)),
            "warning_instances":dict(Counter(w["instance"] for w in warnings)),
            "analysis_limits":graph["analysis_limits"],
            "design_coverage":"not_measured","functional_influence":"not_proven",
            "caveat":"Rows, bit assignments, AST occurrences and warning records have different denominators. No cross-analyzer subtraction or whole-design coverage. Unattributed and missing source locations remain explicit."}

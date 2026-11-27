"""PR95: exact residual flat-row audit; syntax, not semantic promotion."""
from collections import Counter, defaultdict
from .analysis_budgets import inspect_ast
from .bitaccess import build_bit_access_index, MAX_RECORDS
from .bitgraph import build_bit_dependency_graph
from .complex_constructs import METADATA

CHANNELS=("array_dependencies","bitwise_dependencies","mux_dependencies",
          "dynamic_dependencies","selector_recovery","typed_layout")
MAX_SCAN=4096
MAX_DEPTH=64
MAX_LINKS=32768


def natural(x):
    return type(x) is int and x>=0


def tag(x):
    return x if isinstance(x,str) and x else "<unknown>"


def syntax(node):
    """Bounded census of operator nodes; counts by occurrence, not influence."""
    kinds=Counter()
    ops=Counter()
    stack=[(node,0)]
    visited=0
    limited=None
    while stack:
        obj,depth=stack.pop()
        visited+=1
        if visited>MAX_SCAN or depth>MAX_DEPTH:
            limited="syntax_scan_budget"
            break
        if isinstance(obj,dict):
            kind=tag(obj.get("kind"))
            kinds[kind]+=1
            if kind in ("BinaryOp","UnaryOp"):
                ops[kind+":"+tag(obj.get("op"))]+=1
            children=[v for k,v in obj.items() if k not in METADATA and isinstance(v,(dict,list))]
        elif isinstance(obj,list):
            children=[v for v in obj if isinstance(v,(dict,list))]
        else:
            children=[]
        if len(stack)+len(children)+visited>MAX_SCAN:
            limited="syntax_scan_budget"
            break
        stack.extend((v,depth+1) for v in reversed(children))
    root=node
    conversions=0
    while isinstance(root,dict) and root.get("kind")=="Conversion" and conversions<MAX_DEPTH:
        root=root.get("operand")
        conversions+=1
    root=root if isinstance(root,dict) else {}
    return {"root_kind":tag(node.get("kind")) if isinstance(node,dict) else "<unknown>",
            "root_after_conversions":tag(root.get("kind")),
            "root_operator":root.get("op") if root.get("kind") in ("BinaryOp","UnaryOp") else None,
            "leading_conversions":conversions,"node_kinds":dict(sorted(kinds.items())),
            "operators":dict(sorted(ops.items())),"scan_complete":limited is None,
            "scan_limitation":limited}


def exact_links(graph):
    """Only explicit IDs, never target/line matching as a substitute."""
    flat=graph["bit_dependency_graph"]
    access=graph["bit_accesses"]
    rows=flat["items"]
    ar=access["items"]
    n=len(rows)
    if n>MAX_RECORDS or len(ar)!=n or flat["counts"]["assignments"]!=n or access["counts"]["captured"]!=n:
        raise ValueError("flat_access_count_disagreement")
    if flat["counts"]["truncated"] is not False or access["counts"]["truncated"] is not False:
        raise ValueError("truncated_flat_access")
    supported=set()
    for i,(f,a) in enumerate(zip(rows,ar)):
        if (not natural(f.get("assignment_id")) or f["assignment_id"]!=i
                or f["target"]!=a["target"] or f.get("source_location")!=a.get("source")
                or f.get("assignment_kind")!=a.get("assignment_kind","continuous")
                or f.get("procedure_kind")!=a.get("procedure_kind")
                or f.get("nonblocking")!=a.get("nonblocking")
                or f.get("guards")!=a.get("guards",[]) or f.get("events")!=a.get("events",[])):
            raise ValueError("flat_access_identity_disagreement")
        if f["coverage"]=="assignment_local_position_candidates":
            supported.add(i)
        elif f["coverage"]!="partial":
            raise ValueError("unknown_flat_coverage")
    if len(supported)!=flat["counts"]["supported"] or n-len(supported)!=flat["counts"]["partial"]:
        raise ValueError("flat_support_count_disagreement")
    links=defaultdict(list)
    recovered=set()
    unlinked={}
    per_channel={}
    total=0
    for channel in CHANNELS:
        data=graph[channel]
        if data["counts"]["truncated"] is not False or len(data["items"])!=data["counts"]["captured"]:
            raise ValueError("invalid_linked_channel")
        ids=set()
        missing=Counter()
        for j,row in enumerate(data["items"]):
            total+=1
            if total>MAX_LINKS:
                raise ValueError("linked_row_budget")
            coverage=tag(row.get("coverage"))
            if "flat_assignment_id" not in row:
                missing[coverage]+=1
                continue
            i=row["flat_assignment_id"]
            if not natural(i) or i>=n:
                raise ValueError("invalid_linked_flat_id")
            f=rows[i]
            if row["target"]!=f["target"] or row.get("source_location")!=f.get("source_location"):
                raise ValueError("linked_flat_metadata_disagreement")
            links[i].append({"channel":channel,"row_index":j,"coverage":coverage,
                             "reason":row.get("reason")})
            if coverage=="<unknown>":
                raise ValueError("unknown_linked_coverage")
            if coverage!="partial" and i not in supported:
                ids.add(i)
        per_channel[channel]={"unique_recovered_ids":len(ids),"new_ids":len(ids-recovered)}
        recovered.update(ids)
        unlinked[channel]=dict(missing)
    residual=set(range(n))-supported-recovered
    return supported,recovered,residual,links,per_channel,unlinked


def reconcile_capture(access,captured):
    rows=access["items"]
    result={}
    for ordinal,row,node,owner,constants,context_partial in captured:
        if (not natural(ordinal) or ordinal>=len(rows) or ordinal in result
                or row is not rows[ordinal] or not isinstance(node,dict)
                or node.get("kind")!="Assignment" or not isinstance(owner,str)
                or not row["target"].startswith(owner+".") or type(context_partial) is not bool):
            raise ValueError("capture_identity_disagreement")
        result[ordinal]=(node,owner,context_partial)
    if set(result)!=set(range(len(rows))):
        raise ValueError("capture_inventory_incomplete")
    return result


def detailed_reason(flat,access):
    reason=tag(flat.get("reason"))
    if reason=="partial_bit_access":
        if access["coverage"]!="partial" or tag(access.get("reason"))=="<unknown>":
            raise ValueError("missing_bit_access_reason")
        return access["reason"]
    return reason


def audit_residuals(ast,index,graph):
    inspect_ast(ast)
    if graph["analysis_limits"]["truncated_analyzers"]:
        raise ValueError("truncated_historical_analyzers")
    supported,recovered,residual,links,channels,unlinked=exact_links(graph)
    captured=[]
    replay=build_bit_access_index(ast,expected_top=index["top"],index=index,
                                  captured_assignments=captured)
    # Reproduce the actual rows and their ordered construction, including same-line
    # occurrences. JSON round-trip normalizes tuples in serialized reports.
    import json
    if json.loads(json.dumps(replay))!=graph["bit_accesses"]:
        raise ValueError("bit_access_replay_disagreement")
    if json.loads(json.dumps(build_bit_dependency_graph(replay,index)))!=graph["bit_dependency_graph"]:
        raise ValueError("flat_replay_disagreement")
    capture=reconcile_capture(replay,captured)
    modules={i["path"]:i["module"] for i in index["instances"]}
    rows=[]
    op_rows=Counter()
    detailed=Counter()
    root_groups=Counter()
    by_instance=Counter()
    by_module=Counter()
    by_context=Counter()
    refusals=defaultdict(Counter)
    for i in sorted(residual):
        f=graph["bit_dependency_graph"]["items"][i]
        a=replay["items"][i]
        node,owner,partial=capture[i]
        if owner not in modules:
            raise ValueError("unknown_capture_owner")
        if any(l["coverage"]!="partial" for l in links[i]):
            raise ValueError("residual_with_linked_support")
        reason=detailed_reason(f,a)
        rhs=syntax(node.get("right"))
        lhs=node.get("left")
        lhs=lhs if isinstance(lhs,dict) else {}
        detailed[reason]+=1
        root_groups[rhs["root_after_conversions"]+(":"+rhs["root_operator"] if isinstance(rhs["root_operator"],str) else "")]+=1
        by_instance[owner]+=1
        by_module[modules[owner]]+=1
        context=f.get("procedure_kind") or f["assignment_kind"]
        by_context[context]+=1
        op_rows.update(rhs["operators"].keys())
        for channel in CHANNELS:
            subset=[l for l in links[i] if l["channel"]==channel]
            if not subset:
                refusals[channel]["<no_explicit_link>"]+=1
            else:
                # One count per row/reason; multiple reasons may overlap.
                refusals[channel].update({tag(l["reason"]) for l in subset})
        rows.append({"assignment_id":i,"instance":owner,"module":modules[owner],"target":f["target"],
                     "source_location":f.get("source_location"),"assignment_kind":f["assignment_kind"],
                     "procedure_kind":f.get("procedure_kind"),"nonblocking":f.get("nonblocking"),
                     "context_partial":partial,"flat_reason":f["reason"],"bit_access_reason":a.get("reason"),
                     "bit_access_coverage":a["coverage"],"detailed_reason":reason,
                     "lhs_kind":tag(lhs.get("kind")),"lhs_type":lhs.get("type"),
                     "rhs_type":node.get("right",{}).get("type") if isinstance(node.get("right"),dict) else None,
                     "assignment_operator":node.get("op"),"rhs_syntax":rhs,"linked_partial_rows":links[i]})
    def ordered(c):
        return dict(sorted(c.items(),key=lambda x:(-x[1],x[0])))
    return {"scope":"historical_flat_residual_ids_same_ast_only",
            "flat_assignments":len(capture),"flat_supported":len(supported),
            "recovered_unique_ids":len(recovered),"minimum_combined_supported":len(supported|recovered),
            "residual_count":len(residual),"recovered_ids":sorted(recovered),"residual_ids":sorted(residual),
            "coarse_reasons":ordered(Counter(r["flat_reason"] for r in rows)),
            "detailed_reasons":ordered(detailed),"rhs_root_groups":ordered(root_groups),
            "rhs_operator_row_counts_overlapping":ordered(op_rows),
            "by_instance":ordered(by_instance),"by_module":ordered(by_module),"by_context":ordered(by_context),
            "linked_refusal_row_counts_overlapping":{k:ordered(v) for k,v in refusals.items()},
            "recovery_by_channel":channels,"unlinked_rows_by_coverage":unlinked,
            "syntax_scan_limited_rows":sum(not r["rhs_syntax"]["scan_complete"] for r in rows),
            "exact_replay":True,"rows":rows,"member_occurrences_added":False,
            "design_coverage":"not_measured","functional_influence":"not_proven","formal_proof":"not_performed"}

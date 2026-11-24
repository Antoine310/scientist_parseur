"""Bounded hierarchical dependency candidates; no timing or CDC proof."""
from collections import defaultdict


def trace_hierarchical(graph, target, *, max_hops=16, max_paths=128, max_event_steps=4):
    """Walk backward through observed port/data links and last-NBA candidates.

    Event identity may follow only direct scalar input bindings, never
    arbitrary combinational expressions. Keep every binding as provenance.
    """
    if any(type(n) is not int or not 1 <= n <= cap for n,cap in
           ((max_hops,32),(max_paths,256),(max_event_steps,8))):
        raise ValueError("invalid trace bounds")
    if graph.get("schema_version")!=1:
        raise ValueError("graph v1 required")
    nodes=set(graph["nodes"])
    if target not in nodes:
        raise KeyError(target)
    bindings=graph.get("hierarchical_event_bindings")
    temporal=graph.get("intercycle_dependencies")
    if not isinstance(bindings,dict) or bindings.get("schema_version")!=1 or not isinstance(temporal,dict) or temporal.get("schema_version")!=1:
        raise ValueError("regenerate graph with hierarchical event bindings")
    incoming=defaultdict(list)
    for edge in graph["edges"]:
        if edge["kind"] in ("data","port_input","port_output"):
            incoming[edge["target"]].append(edge)
    aliases=defaultdict(list)
    for b in bindings["items"]:
        if b["source"] in nodes and b["target"] in nodes:
            aliases[b["target"]].append(b)
    rows=defaultdict(list)
    for row in temporal["items"]:
        rows[row["target"]].append(row)

    def event_identity(event):
        signal=event["signal"]
        chain=[]
        visited=set()
        while signal in aliases:
            if signal in visited or len(chain)>=max_hops:
                return None,chain
            visited.add(signal)
            choices=aliases[signal]
            edges=incoming[signal]
            if len(choices)!=1 or len(edges)!=1 or edges[0]["kind"]!="port_input" or edges[0]["sequential"] is not False or edges[0]["source"]!=choices[0]["source"] or signal in rows:
                return None,chain
            b=choices[0]
            chain.append(b)
            signal=b["source"]
        # An input connected by an unsupported expression is not a root alias.
        if any(e["kind"]=="port_input" for e in incoming[signal]):
            return None,chain
        return {"edge":event["edge"],"signal":signal},chain

    pending=[(target,[],None,0,frozenset({target}))]
    paths=[]
    truncated=False
    def finish(signal,chain,reason,steps):
        paths.append({"boundary":signal,"chain":chain,"reason":reason,"event_steps":steps})

    while pending:
        signal,chain,event,steps,seen=pending.pop()
        if len(chain)>=max_hops:
            finish(signal,chain,"hop_limit",steps)
            continue
        candidates=[]
        local=rows[signal] if signal in rows else []
        if local:
            row=local[0]
            if len(local)!=1 or row["coverage"]!="syntactic_event_candidates_supported" or temporal["counts"]["truncated"]:
                finish(signal,chain,"partial_sequential_boundary",steps)
                continue
            if row["event_scope"]!="single_edge_event":
                finish(signal,chain,"event_boundary",steps)
                continue
            identity,bindings_used=event_identity(row["events"][0])
            if identity is None or (event is not None and identity!=event):
                finish(signal,chain,"event_boundary",steps)
                continue
            if steps>=max_event_steps:
                finish(signal,chain,"event_step_limit",steps)
                continue
            for path in row["paths"]:
                if not path["data_sources"]:
                    candidates.append((None,{"kind":"constant_rhs_candidate","target":signal,
                        "guards":path["guards"],"path_index":path["path_index"]},identity,steps+1))
                for src in path["data_sources"]:
                    candidates.append((src,{"kind":path["relation"],"source":src,"target":signal,
                        "local_event":row["events"][0],"event_identity_candidate":identity,
                        "event_bindings":bindings_used,"guards":path["guards"],
                        "path_index":path["path_index"],"location":path["write_source"]},identity,steps+1))
        else:
            edges=incoming[signal]
            # A sequential graph edge without a supported NBA row is not combinational.
            if any(e["sequential"] is not False for e in edges):
                finish(signal,chain,"unresolved_sequential_boundary",steps)
                continue
            for edge in edges:
                candidates.append((edge["source"],dict(edge),event,steps))
        if not candidates:
            finish(signal,chain,"no_observed_incoming_dependency",steps)
            continue
        for src,edge,next_event,next_steps in candidates:
            if len(paths)+len(pending)>=max_paths:
                truncated=True
                break
            next_chain=chain+[edge]
            if src is None:
                finish(signal,next_chain,"constant_rhs_candidate",next_steps)
            elif next_steps==steps and src in seen:
                finish(src,next_chain,"combinational_cycle_boundary",next_steps)
            else:
                next_seen=frozenset({src}) if next_steps!=steps else seen|{src}
                pending.append((src,next_chain,next_event,next_steps,next_seen))
    return {"schema_version":1,"target":target,"paths":paths,"truncated":truncated,
            "graph_warning_count":len(graph.get("warnings",[])),
            "guaranteed_cycles":None,"scope":"hierarchical_signal_dependency_candidates",
            "caveat":"Port/data links are syntactic references, not value equality or bit mapping. "
                     "Direct scalar input event identity is a candidate, not CDC proof; "
                     "guard feasibility, global writers and timing are not proven."}

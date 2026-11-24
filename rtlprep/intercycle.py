"""Bounded, event-local candidate dependencies, not a cycle simulator."""
from __future__ import annotations

from collections import Counter
from typing import Any

MAX_ROWS = 2000
MAX_REFERENCES = 64
MAX_DEPTH = 10


def references(node: Any, depth=0, budget=None):
    """Collect syntactically referenced signals; reject an unknown subtree."""
    if budget is None:
        budget = [MAX_REFERENCES]
    budget[0] -= 1
    if budget[0] < 0 or depth > MAX_DEPTH or not isinstance(node, dict):
        raise ValueError("unsupported_or_bounded_expression")
    kind = node.get("kind")
    if kind == "signal" and isinstance(node.get("path"), str) and node["path"]:
        return {node["path"]}
    if kind == "literal":
        return set()
    if kind in ("unary", "conversion"):
        return references(node.get("operand"), depth+1, budget)
    if kind == "binary":
        return references(node.get("left"), depth+1, budget) | references(node.get("right"), depth+1, budget)
    raise ValueError("unsupported_or_bounded_expression")


def build_intercycle_dependencies(seq: dict[str, Any]):
    """Retain last NBA data/guard references and local unwritten paths.

    No inference about which event is a clock for a multi-event process.
    A syntactic NBA step is not a guaranteed clock cycle or latency.
    """
    if seq.get("schema_version") != 1 or not isinstance(seq.get("items"), list):
        raise ValueError("sequential_candidates v1 required")
    counts = seq.get("counts")
    if not isinstance(counts, dict) or type(counts.get("truncated")) is not bool:
        raise ValueError("invalid sequential counts")
    raw = seq["items"]
    writers = Counter(r["target"] for r in raw if isinstance(r, dict) and isinstance(r.get("target"), str))
    items = []
    for row in raw[:MAX_ROWS]:
        if not isinstance(row, dict) or not isinstance(row.get("target"), str) or not isinstance(row.get("process"), str):
            raise ValueError("invalid sequential row")
        target = row["target"]
        events = row.get("events")
        result = {"target":target, "process":row["process"], "source":row.get("source"),
                  "events":events, "event_scope":"unknown", "coverage":"partial", "paths":[]}
        items.append(result)
        if counts["truncated"] or writers[target] != 1 or row.get("multiple_processes_same_target") is not False:
            result["reason"] = "truncated_or_multiple_observed_writers"
            continue
        if row.get("coverage") != "syntactic_candidates_supported":
            result["reason"] = "partial_sequential_candidates"
            continue
        if not isinstance(events,list) or not events or any(
            not isinstance(e,dict) or e.get("edge") not in ("PosEdge","NegEdge")
            or not isinstance(e.get("signal"),str) or not e["signal"] for e in events
        ):
            result["reason"] = "invalid_events"
            continue
        result["event_scope"] = "single_edge_event" if len(events)==1 else "multiple_events_no_clock_inference"
        paths = row.get("paths")
        if not isinstance(paths,list) or not 1 <= len(paths) <= 32:
            result["reason"] = "invalid_paths"
            continue
        out = []
        try:
            for path in paths:
                guards = path["guards"]
                if not isinstance(guards,list) or len(guards)>16:
                    raise ValueError("invalid_guards")
                controls = set()
                for guard in guards:
                    if guard.get("kind")!="if" or guard.get("branch") not in ("then","else"):
                        raise ValueError("invalid_guard")
                    controls |= references(guard.get("condition"))
                candidate = path["transition_candidate"]
                kind = candidate.get("kind")
                if kind == "unwritten_in_this_process":
                    data, relation = {target}, "local_hold_candidate"
                elif kind == "last_nba_rhs_syntax":
                    data, relation = references(candidate.get("rhs")), "last_nba_rhs_references"
                else:
                    raise ValueError("unknown_rhs")
                out.append({"path_index":path["path_index"], "guards":guards,
                            "data_sources":sorted(data), "control_sources":sorted(controls),
                            "relation":relation, "write_source":candidate.get("source"),
                            "write_order":candidate.get("write_order"),
                            "event_steps":1, "guaranteed_cycles":None})
        except (ValueError,KeyError,TypeError,AttributeError) as exc:
            result["reason"] = "unsupported_path"
            continue
        result["coverage"]="syntactic_event_candidates_supported"
        result["paths"]=out
    return {"schema_version":1,"scope":"local_always_ff_event_dependencies",
            "items":items,"counts":{"captured":len(items),
                "supported":sum(r["coverage"]!="partial" for r in items),
                "partial":sum(r["coverage"]=="partial" for r in items),
                "truncated":counts["truncated"] or len(raw)>MAX_ROWS},
            "caveat":"Syntactic data/control references for the final NBA or local hold, "
                     "not proven influence, clock identification, latency, CDC or global writer analysis."}


def trace_event_candidates(report, target, *, max_steps=4, max_paths=128):
    """Follow only supported same-single-edge rows, retaining conditionality.

    Stop at unknown boundaries; no traversal across multiple event domains.
    Paths can revisit a signal at a different event step (feedback).
    """
    if type(max_steps) is not int or not 1 <= max_steps <= 8 or type(max_paths) is not int or not 1 <= max_paths <= 256:
        raise ValueError("invalid trace bounds")
    if report.get("schema_version")!=1 or not isinstance(report.get("items"),list):
        raise ValueError("invalid intercycle report")
    rows = {}
    for r in report["items"]:
        rows.setdefault(r["target"],[]).append(r)
    pending=[(target,[],None)]
    output=[]
    truncated=False
    while pending:
        if len(output)>=max_paths:
            truncated=True
            break
        signal, chain, event = pending.pop()
        found=rows.get(signal,[])
        row=found[0] if len(found)==1 else None
        if len(chain)>=max_steps:
            output.append({"chain":chain,"boundary":signal,"reason":"step_limit"})
            continue
        if not row or row["coverage"]!="syntactic_event_candidates_supported":
            output.append({"chain":chain,"boundary":signal,"reason":"unresolved_or_partial"})
            continue
        if row["event_scope"]!="single_edge_event" or (event is not None and row["events"][0]!=event):
            output.append({"chain":chain,"boundary":signal,"reason":"event_boundary"})
            continue
        edges=[]
        for path in row["paths"]:
            if not path["data_sources"]:
                output.append({"chain":chain,"boundary":signal,"reason":"constant_rhs_candidate",
                               "path_index":path["path_index"],"guards":path["guards"]})
            for src in path["data_sources"]:
                step={"source":src,"target":signal,"event":row["events"][0],
                      "path_index":path["path_index"],"guards":path["guards"],"relation":path["relation"]}
                edges.append((src,chain+[step],row["events"][0]))
        if len(pending)+len(edges)+len(output)>max_paths:
            truncated=True
            break
        pending.extend(reversed(edges))
    return {"target":target,"paths":output[:max_paths],"truncated":truncated or len(output)>max_paths,
            "scope":"backward_same_single_edge_syntactic_event_steps",
            "guaranteed_cycles":None}

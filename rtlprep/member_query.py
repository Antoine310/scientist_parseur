"""Read-only views of stored member candidates, not independent verification.

No EDA execution, path traversal, proof generation or graph promotion.
The caller supplies a previously generated graph; data may be untrusted.
"""
from copy import deepcopy
import json

from .analysis_budgets import DEFAULT_BUDGET, measure_tree
from .dependencies import GRAPH_SCHEMA_VERSION
from .member_evidence import RELATIONS, natural

MAX_GRAPH_BYTES = 64 * 1024 * 1024
MAX_ITEMS = 100
MAX_RECORDS = 32768
CHANNELS = {
    "member_position_candidates": ("position",),
    "member_combinational_candidates": ("local_constant", "configuration_constant", "logical_reference"),
    "member_sequential_candidates": ("nba_sampled", "nba_constant"),
}
CATEGORIES = tuple(c for cats in CHANNELS.values() for c in cats)
SOURCES = {"position", "logical_reference", "nba_sampled"}


def load_member_graph(path):
    if not path.is_file() or path.stat().st_size > MAX_GRAPH_BYTES:
        raise ValueError("member graph absent or exceeds byte budget")
    with path.open("rb") as stream:
        raw = stream.read(MAX_GRAPH_BYTES + 1)
    if len(raw) > MAX_GRAPH_BYTES:
        raise ValueError("member graph exceeds byte budget")
    try:
        graph = json.loads(raw)
    except RecursionError as exc:
        raise ValueError("member graph decoder depth exceeded") from exc
    measure_tree(graph, stage="member_graph_read", max_values=DEFAULT_BUDGET.max_graph_values,
                 max_depth=DEFAULT_BUDGET.max_graph_depth)
    return graph


def _endpoint(value):
    if (not isinstance(value, dict) or not isinstance(value.get("signal"), str)
            or not value["signal"] or not natural(value.get("position"))
            or value.get("coordinate_kind") not in
            ("declared_index", "packed_struct_offset", "packed_vector_coordinates")):
        raise ValueError("invalid member endpoint")


def _inventory(graph):
    if not isinstance(graph, dict) or graph.get("schema_version") != GRAPH_SCHEMA_VERSION:
        raise ValueError("unsupported graph schema")
    result = {}
    summary = {}
    seen = set()
    for key, categories in CHANNELS.items():
        if key not in graph:
            summary[key] = {"status": "not_published", "categories": {c: None for c in categories}}
            continue
        channel = graph[key]
        if (not isinstance(channel, dict) or channel.get("schema_version") != 1
                or channel.get("truncated") is not False
                or not isinstance(channel.get("counts"), dict)
                or any(channel.get(k) != v for k,v in
                       (("design_coverage","not_measured"),("functional_influence","not_proven"),
                        ("formal_proof","not_performed")))):
            raise ValueError("invalid or truncated member channel: " + key)
        collections = {"position":channel.get("items")} if categories == ("position",) else channel.get("collections")
        if not isinstance(collections, dict) or set(collections) != set(categories):
            raise ValueError("invalid member categories: " + key)
        counts = {}
        total = 0
        for category in categories:
            records = collections[category]
            count = channel["counts"].get("positions" if category == "position" else category)
            if not isinstance(records, list) or not natural(count) or count != len(records):
                raise ValueError("member count disagreement")
            total += count
            if total > MAX_RECORDS:
                raise ValueError("member channel record budget")
            for record in records:
                if not isinstance(record, dict):
                    raise ValueError("invalid member record")
                rid = record.get("record_id")
                p = record.get("payload")
                if (not isinstance(rid,str) or not rid or rid in seen
                        or not isinstance(p,dict) or not isinstance(p.get("relation"),str)
                        or RELATIONS.get(p["relation"],(None,None,None))[2] != category
                        or not isinstance(record.get("row_id"),str)
                        or not natural(record.get("occurrence_ordinal"))
                        or not isinstance(record.get("instance"),str)
                        or not isinstance(record.get("context"),str)
                        or not isinstance(record.get("source_location"),dict)):
                    raise ValueError("invalid member record identity or category")
                spec = RELATIONS[p["relation"]]
                if record.get("producer") != spec[0]:
                    raise ValueError("invalid member producer")
                _endpoint(record.get("target"))
                if record["target"]["signal"] != p.get("target"):
                    raise ValueError("member target disagreement")
                if category in SOURCES:
                    _endpoint(record.get("source"))
                    if record["source"]["signal"] != p.get("source") or "value" in record:
                        raise ValueError("member source disagreement")
                elif ("source" in record or type(record.get("value")) is not int
                      or record["value"] not in (0,1) or record["value"] != p.get("value")):
                    raise ValueError("invalid member constant")
                seen.add(rid)
            counts[category] = count
            result[category] = records
        if categories != ("position",) and (not natural(channel["counts"].get("records"))
                                              or channel["counts"]["records"] != total):
            raise ValueError("member total disagreement")
        summary[key] = {"status":"published", "categories":counts, "counts":deepcopy(channel["counts"]),
                        "scope":channel.get("scope"),"caveat":channel.get("caveat")}
    return summary, result


def member_summary(graph):
    summary, _ = _inventory(graph)
    return summary


def query_members(graph, *, category=None, signal=None, limit=50, offset=0):
    if category is not None and category not in CATEGORIES:
        raise ValueError("unknown member category")
    if signal is not None and (not isinstance(signal,str) or not signal or len(signal)>1024):
        raise ValueError("invalid member signal")
    if type(limit) is not int or not 1 <= limit <= MAX_ITEMS or not natural(offset):
        raise ValueError("invalid member pagination")
    summary, records = _inventory(graph)
    total = 0
    page = []
    for cat in CATEGORIES:
        if category is not None and cat != category:
            continue
        for record in records.get(cat, []):
            if signal is not None and signal not in (record["target"]["signal"],record.get("source",{}).get("signal")):
                continue
            if offset <= total < offset+limit:
                page.append({"category":cat,**deepcopy(record)})
            total += 1
    return {"schema_version":1,"scope":"stored_member_candidates_read_only",
            "top":graph.get("top"),"source_fingerprint":graph.get("source_fingerprint"),
            "category":category,"signal":signal,"offset":offset,"limit":limit,"total":total,
            "next_offset":offset+limit if offset+limit<total else None,
            "channels":summary,"items":page,
            "category_published":None if category is None else category in records,
            "design_coverage":"not_measured","functional_influence":"not_proven","formal_proof":"not_performed",
            "caveat":"Stored candidates only, not a new verification. Missing channel is not a zero census. "
                     "Pagination is not analysis truncation. Coordinates, constants and logical/NBA semantics remain distinct; "
                     "identity is scoped to the stored elaboration. No global equality or temporal proof."}

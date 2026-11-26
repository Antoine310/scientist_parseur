"""Lossless experimental member evidence envelope (PR86).

Each row and candidate keeps its producer-local identity and payload.
No cross-producer occurrence matching, deduplication, flat-graph promotion
or functional/temporal inference is performed here.
"""
from collections import Counter
from copy import deepcopy

from .analysis_budgets import inspect_ast
from .array_dependencies import Unsupported
from .packed_members import audit_members
from .member_writes import audit_writes
from .enum_member_writes import audit_enum_writes
from .local_packed_members import audit_local_members
from .member_expressions import audit_member_expressions
from .member_patterns import audit_patterns
from .conditional_member_concat import audit_conditional_concat

PRODUCERS = (
    ("pr79", audit_members), ("pr80", audit_writes),
    ("pr81", audit_enum_writes), ("pr82", audit_local_members),
    ("pr83", audit_member_expressions), ("pr84", audit_patterns),
    ("pr85", audit_conditional_concat),
)
RELATIONS = {
    "packed_struct_position_candidate": ("pr79", "edges", "position"),
    "fixed_member_position_candidate": ("pr80", "edges", "position"),
    "local_constant_write_candidate": ("pr80", "constants", "local_constant"),
    "local_enum_constant_write_candidate": ("pr81", "constants", "local_constant"),
    "local_packed_member_read_candidate": ("pr82", "edges", "position"),
    "local_packed_zero_write_candidate": ("pr82", "constants", "local_constant"),
    "logical_member_reference_candidate": ("pr83", "edges", "logical_reference"),
    "concat_member_position_candidate": ("pr83", "edges", "position"),
    "nba_sampled_member_candidate": ("pr84", "edges", "nba_sampled"),
    "nba_local_constant_candidate": ("pr84", "constants", "nba_constant"),
    "concat_literal_position_candidate": ("pr84", "constants", "local_constant"),
    "configuration_conditional_constant_candidate": ("pr85", "constants", "configuration_constant"),
}
CATEGORIES = ("position", "logical_reference", "nba_sampled", "local_constant",
              "nba_constant", "configuration_constant")
MAX_ROWS = 14000
MAX_RECORDS = 262144


def natural(value):
    return type(value) is int and value >= 0


def nonempty(value):
    return isinstance(value, str) and bool(value)


def normalize(reports):
    """Preserve all original row/record payloads; IDs are report-local only.

    The producer reports must have been obtained from the same in-memory
    AST/index by the caller. This function alone does not establish that.
    """
    if not isinstance(reports, dict) or set(reports) != {p for p, _ in PRODUCERS}:
        raise Unsupported("incomplete_producer_set")
    producers, rows, records = [], [], []
    category_counts = Counter({c: 0 for c in CATEGORIES})
    for producer, _ in PRODUCERS:
        report = reports[producer]
        if (not isinstance(report, dict) or not nonempty(report.get("scope"))
                or not nonempty(report.get("caveat"))
                or not isinstance(report.get("counts"), dict)
                or not isinstance(report.get("items"), list)
                or report.get("functional_influence") != "not_proven"
                or report.get("formal_proof") != "not_performed"
                or report.get("design_coverage") != "not_measured"):
            raise Unsupported("invalid_producer_report")
        items = report["items"]
        if report["counts"].get("sites") != len(items):
            raise Unsupported("producer_row_count_disagreement")
        if len(rows)+len(items) > MAX_ROWS:
            raise Unsupported("unified_row_budget")
        local = {}
        for row in items:
            if (not isinstance(row, dict) or not natural(row.get("site_id"))
                    or row["site_id"] in local or not nonempty(row.get("coverage"))
                    or not isinstance(row.get("source"), dict)):
                raise Unsupported("invalid_producer_row")
            sid = row["site_id"]
            row_id = f"{producer}:{sid}"
            local[sid] = row_id
            rows.append({"row_id": row_id, "producer": producer,
                         "payload": deepcopy(row)})
        counts = {"rows": len(items), "edges": 0, "constants": 0}
        for collection in ("edges", "constants"):
            values = report.get(collection, [])
            if not isinstance(values, list):
                raise Unsupported("invalid_producer_collection")
            if len(records)+len(values) > MAX_RECORDS:
                raise Unsupported("unified_record_budget")
            if collection in report["counts"] and report["counts"][collection] != len(values):
                raise Unsupported("producer_record_count_disagreement")
            counts[collection] = len(values)
            for i, value in enumerate(values):
                if not isinstance(value, dict) or not natural(value.get("site_id")) or value["site_id"] not in local:
                    raise Unsupported("orphan_candidate")
                relation = value.get("relation")
                spec = RELATIONS.get(relation) if isinstance(relation, str) else None
                if spec is None or spec[:2] != (producer, collection):
                    raise Unsupported("unknown_or_misplaced_relation")
                if not nonempty(value.get("target")):
                    raise Unsupported("missing_target")
                # Multidimensional target offsets are NOT declaration indices.
                if relation == "local_packed_member_read_candidate":
                    if ("target_bit" in value or not natural(value.get("target_packed_offset"))
                            or not isinstance(value.get("target_coordinates"), list)
                            or len(value["target_coordinates"]) != 2
                            or not all(natural(n) for n in value["target_coordinates"])):
                        raise Unsupported("invalid_packed_coordinates")
                elif not natural(value.get("target_bit")) or "target_packed_offset" in value:
                    raise Unsupported("invalid_target_position")
                if collection == "edges":
                    if not nonempty(value.get("source")) or not natural(value.get("source_bit")) or "value" in value:
                        raise Unsupported("invalid_reference_record")
                elif type(value.get("value")) is not int or value["value"] not in (0,1) or "source" in value:
                    raise Unsupported("invalid_constant_record")
                category = spec[2]
                category_counts[category] += 1
                records.append({"record_id": f"{producer}:{collection}:{i}",
                                "row_id": local[value["site_id"]], "producer": producer,
                                "collection": collection, "category": category,
                                "payload": deepcopy(value)})
        producers.append({"producer": producer, "counts": counts,
                          "metadata": deepcopy({k:v for k,v in report.items()
                                                if k not in ("items","edges","constants")}),
                          "present_collections": [k for k in ("edges","constants") if k in report]})
    return {"schema_version": 1, "scope": "experimental_member_evidence_envelope",
            "counts": {"producer_reports":len(producers), "producer_rows":len(rows),
                       "candidate_records":len(records), **dict(category_counts)},
            "producers":producers, "rows":rows, "records":records,
            "occurrence_identity":"producer_local_only", "cross_producer_deduplication":"not_performed",
            "graph_integration":"not_performed", "design_coverage":"not_measured",
            "functional_influence":"not_proven", "formal_proof":"not_performed",
            "caveat":"Counts are producer rows and records, not unique occurrences or global graph edges. "
                     "All producer-specific coordinate systems, configuration proofs and limits are retained."}


def collect(ast,index):
    inspect_ast(ast)
    reports = {name: audit(ast,index) for name,audit in PRODUCERS}
    return normalize(reports), reports

"""Bilan conservateur de couverture des analyses RTLPrep observées.

Aucune estimation du pourcentage de RTL compris : les dénominateurs sont
uniquement les enregistrements effectivement émis par chaque analyseur.
Les avertissements, éléments exclus et limites sont conservés séparément.
"""
from __future__ import annotations

from typing import Any

COVERAGE_SCHEMA_VERSION = 1
MAX_FINDINGS = 200
MAX_TEXT = 160

SUPPORTED = {
    "expressions": ("syntax_supported", "partial"),
    "register_flow": ("syntactic_paths_supported", "partial"),
    "bit_accesses": ("explicit_target_lanes", "rhs_lanes_only", "partial"),
}
EXCLUDED_COUNTS = {
    "expressions": ("unsupported_statements", "unsupported_targets",
                    "procedural_blocks_skipped"),
    "register_flow": (),
    "bit_accesses": ("unsupported_targets",),
}


def _natural(value: Any, name: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"Compteur de couverture invalide : {name}")
    return value


def _short(value: Any) -> str:
    return str(value)[:MAX_TEXT]


def build_coverage_summary(graph: dict[str, Any]) -> dict[str, Any]:
    """Résumer les sorties stockées d'analyses v1, sans recompilation ni LLM."""
    if graph.get("schema_version") != 1:
        raise ValueError("Le résumé de couverture nécessite un graphe RTL v1")
    raw_warnings = graph.get("warnings")
    edges, nodes = graph.get("edges"), graph.get("nodes")
    if not isinstance(raw_warnings, list) or not isinstance(edges, list) or (
        not isinstance(nodes, list)
    ):
        raise ValueError("Le graphe de couverture est incomplet")
    if any(not isinstance(w, dict) for w in raw_warnings):
        raise ValueError("Avertissement de graphe malformé")

    findings: list[dict[str, Any]] = []
    findings_total = 0

    def issue(analyzer: str, reason: str, target: Any = None,
              count: int | None = None) -> None:
        nonlocal findings_total
        findings_total += 1
        if len(findings) >= MAX_FINDINGS:
            return
        row: dict[str, Any] = {
            "analyzer": analyzer, "reason": _short(reason),
        }
        if isinstance(target, str) and target:
            row["target"] = target[:256]
        if count is not None:
            row["count"] = count
        findings.append(row)

    for warning in raw_warnings:
        issue("dependencies", warning.get("reason", "unknown_graph_warning"),
              warning.get("context"))

    reports: dict[str, dict[str, Any]] = {
        "dependencies": {
            "scope": "signal_level_graph",
            "nodes": len(nodes),
            "edges": len(edges),
            "warnings": len(raw_warnings),
            "assessment": ("reported_limits" if raw_warnings
                           else "no_reported_limits_within_scope"),
            "design_coverage": "not_measured",
        }
    }
    has_limits = bool(raw_warnings)
    for analyzer, statuses in SUPPORTED.items():
        payload = graph.get(analyzer)
        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            raise ValueError(f"Rapport d'analyse manquant/incompatible : {analyzer}")
        items, counts = payload.get("items"), payload.get("counts")
        if not isinstance(items, list) or not isinstance(counts, dict):
            raise ValueError(f"Données de couverture malformées : {analyzer}")
        captured = _natural(counts.get("captured"), f"{analyzer}.captured")
        if captured != len(items):
            raise ValueError(f"Comptage de couverture incohérent : {analyzer}")
        truncated = counts.get("truncated")
        if type(truncated) is not bool:
            raise ValueError(f"Troncature de couverture invalide : {analyzer}")

        status_counts = {status: 0 for status in statuses}
        status_counts["unknown"] = 0
        for row in items:
            if not isinstance(row, dict):
                raise ValueError(f"Enregistrement de couverture invalide : {analyzer}")
            coverage = row.get("coverage")
            target = row.get("target")
            if coverage not in statuses:
                status_counts["unknown"] += 1
                issue(analyzer, "unknown_coverage_status", target)
            else:
                status_counts[coverage] += 1
                if coverage == "partial":
                    issue(analyzer, row.get("reason") or "partial_record", target)
        excluded: dict[str, int] = {}
        for counter in EXCLUDED_COUNTS[analyzer]:
            amount = _natural(counts.get(counter), f"{analyzer}.{counter}")
            excluded[counter] = amount
            if amount:
                issue(analyzer, counter, count=amount)

        related_process_limits: dict[str, int] = {}
        if analyzer == "register_flow":
            partial_processes = _natural(
                counts.get("partial_processes"), "register_flow.partial_processes"
            )
            related_process_limits["partial_processes"] = partial_processes
            if partial_processes:
                issue(analyzer, "partial_processes", count=partial_processes)
        if truncated:
            issue(analyzer, "analysis_truncated")
        observed_limits = (status_counts["partial"] > 0
                           or status_counts["unknown"] > 0
                           or any(excluded.values())
                           or any(related_process_limits.values()) or truncated)
        has_limits = has_limits or observed_limits
        reports[analyzer] = {
            "scope": _short(payload.get("scope", "unknown")),
            "captured": captured,
            "observed_status_counts": status_counts,
            "excluded_from_records": excluded,
            "related_process_limits": related_process_limits,
            "truncated": truncated,
            "assessment": ("reported_limits" if observed_limits else
                           "no_observed_records" if not captured else
                           "no_reported_limits_within_scope"),
            "design_coverage": "not_measured",
        }

    return {
        "schema_version": COVERAGE_SCHEMA_VERSION,
        "scope": "observed_analyzer_records_only",
        "assessment": ("reported_limits" if has_limits
                       else "no_reported_limits_within_scopes"),
        "design_coverage": "not_measured",
        "analyzers": reports,
        "findings": findings,
        "findings_total": findings_total,
        "findings_truncated": findings_total > MAX_FINDINGS,
        "caveat": (
            "Mesure des enregistrements observés, pas pourcentage de RTL compris. "
            "Les analyses ont des périmètres différents ; un signal sans résultat "
            "ne prouve pas l'absence de dépendance ou d'anomalie. Les avertissements, "
            "exclusions, statuts partiels et troncatures limitent la portée ; "
            "aucune faisabilité, simulation ou preuve formelle n'est déduite."
        ),
    }

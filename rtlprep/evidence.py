"""Traçabilité conservatrice : RTL du snapshot, hypothèses, validations stockées.

La seule association automatisée est par top ET empreinte source. Une preuve
du design / banc n'est jamais interprétée comme preuve d'un signal particulier.
Aucun rapport n'est exécuté, aucun fichier externe n'est ouvert par ce module.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

EVIDENCE_SCHEMA_VERSION = 1
MAX_ANCHORS = 16
MAX_HYPOTHESES = 16
MAX_LABEL = 160

VALIDATIONS = (
    ("simulation.result.json", "simulation"),
    ("formal.result.json", "formal"),
    ("equivalence.result.json", "equivalence"),
)
ANCHOR_FIELDS = ("expressions", "register_flow", "sequential_candidates",
                 "bit_accesses")


def _label(x: Any) -> str | None:
    return x[:MAX_LABEL] if isinstance(x, str) and x else None


def _relation(report: dict[str, Any], kind: str, top: str | None,
              fingerprint: str | None, snapshot_status: str) -> tuple[str, str]:
    """La relation correspond au même design, jamais à une propriété prouvée."""
    if kind == "equivalence":
        role = []
        for side in ("gold", "gate"):
            value, report_top = report.get(side + "_fingerprint"), report.get("top_" + side)
            if not isinstance(value, str) or not value or not isinstance(report_top, str):
                continue
            if fingerprint and value == fingerprint and report_top == top:
                role.append(side)
        if role:
            matched_role = "both_sides" if len(role) == 2 else role[0]
        else:
            matched_role = "none"
        # Missing fingerprint is never evidence of a relation.
        if fingerprint is None:
            return "unverifiable", "none"
        if not role:
            return "different_design_or_role", "none"
    else:
        matched_role = "single_design"
        recorded_top, recorded = report.get("top"), report.get("source_fingerprint")
        if isinstance(recorded_top, str) and isinstance(top, str) and recorded_top != top:
            return "different_top", "none"
        if (fingerprint is None or not isinstance(recorded, str) or not recorded):
            return "unverifiable", "none"
        if recorded != fingerprint:
            return "different_artifact", "none"
        if not isinstance(recorded_top, str):
            return "unverifiable", "none"

    if snapshot_status == "stale":
        return "stale_current_sources", matched_role
    if snapshot_status == "unavailable":
        return "unavailable_current_sources", matched_role
    if snapshot_status == "matching":
        return "matches_current_sources", matched_role
    return "matches_artifacts_only", matched_role


def _reported_result(kind: str, report: dict[str, Any]) -> dict[str, Any]:
    """Conserver les verdicts de sortie sans les fabriquer à partir du exit code."""
    status = _label(report.get("status")) or "unknown"
    result: dict[str, Any] = {
        "status": status, "result_criteria_met": False,
        "result_kind": kind + "_stored_report",
    }
    if kind == "simulation":
        counts = [report.get(k) for k in ("tests", "passed", "failed", "skipped")]
        valid = all(type(n) is int and n >= 0 for n in counts)
        if valid:
            tests, passed, failed, skipped = counts
            result["test_counts"] = dict(
                tests=tests, passed=passed, failed=failed, skipped=skipped
            )
            result["result_criteria_met"] = (
                status == "passed" and tests > 0 and tests == passed
                and failed == 0 and skipped == 0
            )
    elif kind == "formal":
        tasks: dict[str, Any] = {}
        for name in ("proof", "cover"):
            item = report.get(name)
            if isinstance(item, dict):
                tasks[name] = {
                    "status": _label(item.get("status")) or "unknown",
                    "sby_status": _label(item.get("sby_status")) or "unknown",
                }
            else:
                tasks[name] = {"status": "not_available", "sby_status": "not_available"}
        result["tasks"] = tasks
        result["result_criteria_met"] = (
            status == "passed" and all(
                v["status"] == "passed" and v["sby_status"] == "PASS"
                for v in tasks.values()
            )
        )
    else:
        verdict = _label(report.get("eqy_verdict")) or "unknown"
        partitions = report.get("partition_count")
        result["eqy_verdict"] = verdict
        if type(partitions) is int and partitions >= 0:
            result["partition_count"] = partitions
            result["result_criteria_met"] = (
                status == "passed" and report.get("equivalent") is True
                and verdict == "PASS" and partitions > 0
            )
    return result


def _rtl_anchors(graph: dict[str, Any], signal: str | None,
                 approved_sources: set[str] | None) -> list[dict[str, Any]]:
    """Lieux AST de la cible exacte, jamais une liste de propriétés prouvées."""
    if signal is None:
        return []
    anchors: list[dict[str, Any]] = []
    for analyzer in ANCHOR_FIELDS:
        section = graph.get(analyzer)
        if not isinstance(section, dict) or not isinstance(section.get("items"), list):
            continue
        for row in section["items"]:
            if not isinstance(row, dict) or row.get("target") != signal:
                continue
            source = row.get("source")
            if not isinstance(source, dict):
                continue
            original = source.get("file")
            line = source.get("line")
            if not isinstance(original, str) or not original or (
                type(line) is not int or line <= 0
            ):
                continue
            basename = Path(original).name
            if (not basename or approved_sources is not None
                    and basename not in approved_sources):
                continue
            anchors.append({
                "analyzer": analyzer, "source_file": basename,
                "source_line": line,
                "coverage": _label(row.get("coverage")) or "unknown",
                "provenance": "ast_reported_not_revalidated",
            })
            if len(anchors) >= MAX_ANCHORS:
                return anchors
    return anchors


def build_evidence_view(graph: dict[str, Any], reports: dict[str, dict[str, Any]],
                        *, signal: str | None, artifact_fingerprint: str | None,
                        source_snapshot_status: str,
                        approved_sources: set[str] | None = None) -> dict[str, Any]:
    """Composer un index lisible sans prétendre prouver chaque signal."""
    if not isinstance(graph, dict) or graph.get("schema_version") != 1:
        raise ValueError("Graphe v1 requis pour la traçabilité")
    top = graph.get("top")
    if not isinstance(top, str) or not top:
        raise ValueError("Top RTL invalide pour la traçabilité")
    if signal is not None and signal not in graph.get("nodes", []):
        raise KeyError(f"Signal introuvable : {signal}")
    records: list[dict[str, Any]] = []
    hypotheses: list[dict[str, Any]] = []
    for filename, kind in VALIDATIONS:
        report = reports.get(filename)
        if not isinstance(report, dict):
            records.append({
                "report": filename, "kind": kind, "available": False,
                "relation": "no_report", "role": "none",
                "result": {"status": "not_available",
                           "result_criteria_met": False},
                "usable_for_current_snapshot": False,
                "association": "no_evidence",
            })
            continue
        relation, role = _relation(
            report, kind, top, artifact_fingerprint, source_snapshot_status
        )
        available_now = relation == "matches_current_sources"
        result = _reported_result(kind, report)
        records.append({
            "report": filename, "kind": kind, "available": True,
            "relation": relation, "role": role,
            "result": result,
            "usable_for_current_snapshot": available_now and result["result_criteria_met"],
            "association": (
                "design_or_suite_only_not_signal_proof"
                if relation in ("matches_current_sources", "matches_artifacts_only")
                else "not_linked_to_current_design"
            ),
        })
        if kind == "formal":
            values = report.get("assumptions")
            if isinstance(values, list):
                for value in values[:MAX_HYPOTHESES]:
                    label = _label(value)
                    if label is not None:
                        hypotheses.append({
                            "text": label,
                            "origin": "formal_report_declared_assumption",
                            "relation": relation,
                            "status": "reported_not_validated",
                        })
    return {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "scope": "design_snapshot_report_association_only",
        "top": top, "signal": signal,
        "source_snapshot_status": source_snapshot_status,
        "rtl_anchors": _rtl_anchors(graph, signal, approved_sources),
        "hypotheses": hypotheses,
        "hypotheses_available": bool(hypotheses),
        "records": records,
        "caveat": (
            "Correspondance entre rapports stockes et empreintes RTL, pas chaine "
            "de preuve d'une propriete par signal. Les hypotheses sont declarees "
            "dans un rapport et non demontrees. Une simulation passee, une preuve "
            "SBY de suite approuvee ou une equivalence EQY de paire ne prouvent "
            "pas le comportement de chaque signal ; un rapport absent, stale ou "
            "sans empreinte ne peut soutenir une conclusion. Le MCP ne lance "
            "aucun test ni outil EDA ; les empreintes ne sont pas une "
            "attestation d'authenticite du producteur de rapports."
        ),
    }

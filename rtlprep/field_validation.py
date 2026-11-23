"""Validation conservatrice de RTL tiers épinglés, sans oracle fonctionnel.

Les cas sont issus de sources externes et distincts des fixtures historiques.
On mesure la réussite de la chaîne, les avertissements et les troncatures,
sans appeler cela un pourcentage de RTL compris ou une preuve de correction.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any

from .dependencies import trace_dependencies
from .manifest import load_design
from .runner import dependency_design, fingerprint

CASE_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}\Z")
SHA1_RE = re.compile(r"[a-f0-9]{40}\Z")
SIGNAL_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)+\Z")
MAX_CASES = 20
MAX_SOURCES = 100
MAX_PROBES = 12
QUERY_BUDGETS = (5, 100, 1000)


class ValidationError(ValueError):
    """Un fichier, une empreinte ou une description d'expérience est invalide."""


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def _under(base: Path, fragment: str, *, must_be_dir: bool) -> Path:
    if not isinstance(fragment, str) or not fragment or fragment.startswith(("/", "~")):
        raise ValidationError("Chemin relatif obligatoire et non vide")
    if any(x in fragment for x in ("\0", "\r", "\n", "$", "*", "?", "[", "]")):
        raise ValidationError("Chemin avec expansion ou caractères interdits")
    path = (base / fragment).resolve()
    if not path.is_relative_to(base):
        raise ValidationError(f"Chemin hors de la racine vérifiée : {fragment}")
    if not (path.is_dir() if must_be_dir else path.is_file()):
        raise ValidationError(f"Fichier ou dossier introuvable : {fragment}")
    return path


def validate_suite(doc: Any) -> list[dict[str, Any]]:
    if not isinstance(doc, dict) or doc.get("schema_version") != 1:
        raise ValidationError("Version de corpus inconnue")
    cases = doc.get("cases")
    if not isinstance(cases, list) or not 1 <= len(cases) <= MAX_CASES:
        raise ValidationError("Corpus vide ou trop grand")
    seen: set[str] = set()
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str):
            raise ValidationError("Cas invalide")
        name = case["id"]
        if not CASE_RE.fullmatch(name) or name in seen:
            raise ValidationError("Identifiant de cas invalide ou dupliqué")
        seen.add(name)
        top = case.get("top")
        if not isinstance(top, str) or not CASE_RE.fullmatch(top):
            raise ValidationError(f"{name} : top non pris en charge")
        upstream = case.get("upstream")
        if not isinstance(upstream, dict):
            raise ValidationError(f"{name} : provenance externe manquante")
        if not all(isinstance(upstream.get(k), str) for k in
                   ("repository", "checkout", "commit")):
            raise ValidationError(f"{name} : métadonnées upstream invalides")
        if not CASE_RE.fullmatch(upstream["checkout"]):
            raise ValidationError(f"{name} : checkout invalide")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", upstream["repository"]):
            raise ValidationError(f"{name} : repo externe invalide")
        if not SHA1_RE.fullmatch(upstream["commit"]):
            raise ValidationError(f"{name} : commit non épinglé")
        sources, includes, defines, probes = (
            case.get("sources"), case.get("include_dirs"),
            case.get("defines"), case.get("probes"),
        )
        if not isinstance(sources, list) or not 1 <= len(sources) <= MAX_SOURCES:
            raise ValidationError(f"{name} : liste de sources invalide")
        if not isinstance(includes, list) or not all(isinstance(x, str) for x in includes):
            raise ValidationError(f"{name} : include_dirs invalides")
        if not isinstance(defines, list) or not all(isinstance(x, str) for x in defines):
            raise ValidationError(f"{name} : defines invalides")
        if not isinstance(probes, list) or not 1 <= len(probes) <= MAX_PROBES:
            raise ValidationError(f"{name} : probes invalides")
        for source in sources:
            if not isinstance(source, dict) or not isinstance(source.get("path"), str):
                raise ValidationError(f"{name} : source invalide")
            if not SHA1_RE.fullmatch(str(source.get("git_blob_sha1", ""))):
                raise ValidationError(f"{name} : empreinte de source manquante")
        for probe in probes:
            if not isinstance(probe, dict) or not CASE_RE.fullmatch(str(probe.get("id", ""))):
                raise ValidationError(f"{name} : probe invalide")
            target = probe.get("signal")
            if not isinstance(target, str) or not SIGNAL_RE.fullmatch(target):
                raise ValidationError(f"{name} : cible de probe invalide")
            if probe.get("direction") not in ("fanin", "fanout"):
                raise ValidationError(f"{name} : direction de probe invalide")
    return cases


def verify_sources(case: dict[str, Any], root: Path) -> dict[str, Any]:
    checkout = _under(root, case["upstream"]["checkout"], must_be_dir=True)
    sources: list[Path] = []
    hashes: list[dict[str, str]] = []
    for row in case["sources"]:
        source = _under(checkout, row["path"], must_be_dir=False)
        data = source.read_bytes()
        actual = git_blob_sha1(data)
        if actual != row["git_blob_sha1"]:
            raise ValidationError(
                f"{case['id']}: version du RTL différente du hash épinglé : {row['path']}"
            )
        sources.append(source)
        hashes.append({
            "relative_source": row["path"],
            "git_blob_sha1": actual,
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    includes = [_under(checkout, inc, must_be_dir=True)
                for inc in case["include_dirs"]]
    return {"sources": sources, "includes": includes, "hashes": hashes}


def audit_snapshot(index: dict[str, Any], graph: dict[str, Any],
                   *, top: str, expected_fingerprint: str,
                   probes: list[dict[str, Any]]) -> dict[str, Any]:
    """Vérifie la cohérence des artefacts et expose les limites sans les masquer."""
    for label, artifact in (("index", index), ("graph", graph)):
        if not isinstance(artifact, dict) or artifact.get("schema_version") != 1:
            raise ValidationError(f"{label} non conforme au schéma v1")
        if artifact.get("top") != top or artifact.get("source_fingerprint") != expected_fingerprint:
            raise ValidationError(f"{label} ne correspond pas au snapshot analysé")
    nodes, edges, warnings = (graph.get("nodes"), graph.get("edges"),
                             graph.get("warnings"))
    coverage = graph.get("coverage")
    if not isinstance(nodes, list) or not isinstance(edges, list) or not isinstance(warnings, list):
        raise ValidationError("Graphe sans nœuds, arêtes ou avertissements exploitables")
    if not isinstance(coverage, dict) or coverage.get("schema_version") != 1:
        raise ValidationError("Couverture v1 indisponible")
    if coverage.get("design_coverage") != "not_measured":
        raise ValidationError("Couverture totale non mesurée : elle ne peut pas être inventée")
    analyzers = coverage.get("analyzers")
    if not isinstance(analyzers, dict):
        raise ValidationError("Détails de couverture indisponibles")
    observed = {}
    partial = False
    for name in ("dependencies", "expressions", "register_flow", "bit_accesses"):
        item = analyzers.get(name)
        if not isinstance(item, dict):
            raise ValidationError(f"Analyseur manquant : {name}")
        observed[name] = {
            "assessment": item.get("assessment"),
            "captured": item.get("captured"),
            "observed_status_counts": item.get("observed_status_counts"),
            "excluded_from_records": item.get("excluded_from_records"),
            "truncated": item.get("truncated"),
        }
        if item.get("assessment") == "reported_limits" or item.get("truncated") is True:
            partial = True
    output = []
    for probe in probes:
        target = probe["signal"]
        if target not in nodes:
            output.append({
                "id": probe["id"], "signal": target,
                "status": "missing_target", "budgets": [],
            })
            partial = True
            continue
        budgets = []
        for limit in QUERY_BUDGETS:
            response = trace_dependencies(
                graph, target, probe["direction"], max_depth=6, max_edges=limit,
            )
            budgets.append({
                "max_edges": limit, "returned_edges": len(response["edges"]),
                "visited_nodes": len(response["visited_nodes"]),
                "truncated": response["truncated"],
            })
        if any(x["truncated"] for x in budgets):
            partial = True
        output.append({
            "id": probe["id"], "signal": target, "status": "target_found",
            "direction": probe["direction"], "budgets": budgets,
        })
    if warnings:
        partial = True
    if not index.get("instances"):
        partial = True
    return {
        "status": "observed_with_reported_limits" if partial else "observed_within_reported_scope",
        "index_counts": index.get("counts"), "graph_counts": graph.get("counts"),
        "warning_count": len(warnings),
        "warnings_sample": [
            {"context": str(x.get("context", ""))[:120], "reason": str(x.get("reason", ""))[:180]}
            for x in warnings[:12] if isinstance(x, dict)
        ],
        "warnings_total": len(warnings),
        "coverage_scope": coverage.get("scope"),
        "design_coverage": "not_measured",
        "coverage_assessment": coverage.get("assessment"),
        "findings_total": coverage.get("findings_total"),
        "observed_analyzers": observed,
        "probes": output,
        "all_probes_present": all(p["status"] == "target_found" for p in output),
        "note": "Traces = influences possibles au niveau signal, pas preuve de causalité.",
    }


def evaluate_case(case: dict[str, Any], *, sources_root: Path,
                  output: Path, timeout: int = 180) -> dict[str, Any]:
    """Une véritable compilation slang par cas, ou un échec explicite."""
    start = time.perf_counter()
    result: dict[str, Any] = {
        "id": case["id"], "top": case["top"],
        "upstream": case["upstream"], "status": "not_run",
        "source_integrity": "not_checked",
        "execution": "not_run",
        "functional_correctness": "not_tested",
        "llm_accuracy": "not_measured",
    }
    out = output / case["id"]
    try:
        paths = verify_sources(case, sources_root)
        result["source_integrity"] = "verified_pinned_git_blobs"
        result["source_hashes"] = paths["hashes"]
        out.mkdir(parents=True, exist_ok=True)
        manifest = out / "design.json"
        payload = {
            "top": case["top"], "sources": [os.path.relpath(x, out) for x in paths["sources"]],
            "include_dirs": [os.path.relpath(x, out) for x in paths["includes"]],
            "defines": case["defines"],
        }
        manifest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        design = load_design(manifest)
        original = fingerprint(design)
        result["source_fingerprint"] = original
        run = dependency_design(design, out, timeout=timeout)
        result["execution"] = run.get("status", "unknown")
        if run.get("status") != "passed":
            result["status"] = "eda_or_analysis_failed"
            result["failure_reason"] = str(run.get("error", "no_reason"))[:260]
            return result
        # Detect source changes while slang / RTLPrep was processing.
        if fingerprint(design) != original:
            raise ValidationError("Sources modifiées pendant l'analyse")
        for row in paths["hashes"]:
            changed = _under(
                (sources_root / case["upstream"]["checkout"]).resolve(),
                row["relative_source"], must_be_dir=False,
            )
            if hashlib.sha256(changed.read_bytes()).hexdigest() != row["sha256"]:
                raise ValidationError("Sources modifiées pendant l'analyse")
        index = json.loads((out / "rtl_index.json").read_text(encoding="utf-8"))
        graph = json.loads((out / "rtl_dependencies.json").read_text(encoding="utf-8"))
        audit = audit_snapshot(
            index, graph, top=design.top, expected_fingerprint=original,
            probes=case["probes"],
        )
        result["status"] = audit["status"]
        result["audit"] = audit
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        result["status"] = "invalid_or_unverifiable"
        result["failure_reason"] = str(exc)[:260]
    finally:
        result["elapsed_ms"] = round((time.perf_counter() - start) * 1000, 3)
        out.mkdir(parents=True, exist_ok=True)
        (out / "validation.case.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8",
        )
    return result


def run_suite(suite: dict[str, Any], *, sources_root: Path,
              output: Path, timeout: int = 180,
              selected: set[str] | None = None) -> dict[str, Any]:
    cases = validate_suite(suite)
    if type(timeout) is not int or not 1 <= timeout <= 900:
        raise ValidationError("Timeout hors limites (1 à 900 s)")
    names = {case["id"] for case in cases}
    if selected is not None and (not selected or not selected <= names):
        raise ValidationError("Sélection de cas inconnue ou vide")
    root = sources_root.expanduser().resolve()
    if not root.is_dir():
        raise ValidationError("Répertoire de sources externes absent")
    out = output.expanduser().resolve()
    if out.is_relative_to(root) or root.is_relative_to(out):
        raise ValidationError("La sortie doit être séparée des sources externes")
    out.mkdir(parents=True, exist_ok=True)
    evaluated = [
        evaluate_case(case, sources_root=root, output=out, timeout=timeout)
        for case in cases if selected is None or case["id"] in selected
    ]
    successful = [x for x in evaluated if x["status"].startswith("observed_")]
    report = {
        "schema_version": 1,
        "method": "pinned_external_rtl_observation_without_functional_oracle",
        "external_cases": len(evaluated),
        "elaborated_cases": len(successful),
        "failed_cases": len(evaluated) - len(successful),
        "reported_limit_cases": sum(x["status"] == "observed_with_reported_limits"
                                    for x in evaluated),
        "all_elaborated": len(successful) == len(evaluated),
        "all_probes_present": all(x.get("audit", {}).get("all_probes_present", False)
                                  for x in evaluated),
        "cases": evaluated,
        "accuracy": "not_measured_without_independent_exhaustive_oracle",
        "functional_correctness": "not_tested",
        "benchmarked_llm": False,
        "source_of_truth": "pinned_upstream_git_blobs_and_real_slang_execution",
        "caveats": [
            "Corpus externe mais sélectionné par les développeurs : pas un échantillon aléatoire.",
            "Élaboration réussie ne prouve ni complétude ni correction fonctionnelle.",
            "Les compteurs d'analyse portent seulement sur les enregistrements observés.",
            "Les arêtes non étiquetées ne sont pas évaluées en précision/rappel.",
            "Les budgets de trace limitent la réponse ; truncated est conservé.",
            "Aucune réponse de Codex/LLM n'a été produite ou mesurée.",
            "Les hashes git-blob attestent le contenu des fichiers, pas l'identité du producteur.",
        ],
    }
    (out / "unknown_validation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    return report

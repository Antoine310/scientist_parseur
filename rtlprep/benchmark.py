"""Benchmarks reproductibles : couverture étiquetée et tailles de contexte.

Ce module ne prétend PAS mesurer la qualité d'un LLM : seules les
dépendances explicitement étiquetées, les durées mesurées et les octets
des charges utiles destinées à un agent sont évalués.
"""
from __future__ import annotations

import json
import re
import statistics
import time
from pathlib import Path
from typing import Any

from .dependencies import trace_dependencies
from .index import get_instance, get_signal_info, get_source_context
from .manifest import Design
from .runner import dependency_design, fingerprint


def compact_bytes(data: Any) -> int:
    """Taille UTF-8 d'une représentation JSON canonique, sans indentation."""
    return len(json.dumps(data, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":")).encode("utf-8"))


def whitespace_words(data: Any) -> int:
    """Simple indicateur *approximatif*, jamais un comptage de tokens LLM."""
    return len(re.findall(r"\S+", json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))))


def labelled_edge_scores(graph: dict, positive: list[list[str]],
                         negative: list[list[str]]) -> dict:
    """Métriques UNIQUEMENT sur un petit sous-ensemble annoté de triplets.

    Ne pas appeler cela précision/rappel globaux du parseur ou de l'agent.
    """
    good, bad = {tuple(e) for e in positive}, {tuple(e) for e in negative}
    if not good or not bad or good & bad:
        raise ValueError("Il faut deux jeux d'étiquettes disjoints, non vides")
    if any(len(e) != 3 or not all(isinstance(s, str) for s in e)
           for e in good | bad):
        raise ValueError("Étiquette d'arête invalide (source, cible, type)")
    observed = {(e["source"], e["target"], e["kind"])
                for e in graph["edges"]}
    tp, fn = len(good & observed), len(good - observed)
    fp, tn = len(bad & observed), len(bad - observed)
    return {
        "positive_labels": len(good), "negative_labels": len(bad),
        "tp": tp, "fn": fn, "fp": fp, "tn": tn,
        "precision_on_labels": round(tp / (tp + fp), 4)
        if tp + fp else None,
        "recall_on_labels": round(tp / (tp + fn), 4),
        "specificity_on_labels": round(tn / (tn + fp), 4),
        "missing_positive": [list(e) for e in sorted(good - observed)],
        "unexpected_negative": [list(e) for e in sorted(bad & observed)],
        "unlabelled_edges": len(observed - good - bad),
        "warning_count": len(graph.get("warnings", [])),
        "interpretation": (
            "Scores sur triplets étiquetés uniquement, PAS précision "
            "exhaustive du graphe ni exactitude d'un LLM."
        ),
    }


def _source_snippet(d: Design, target_signal: dict, radius: int = 3) -> dict | None:
    """Extrait limité par la provenance exacte d'un port/déclaration slang."""
    available = (target_signal.get("ports", []) +
                 target_signal.get("declarations", []))
    for item in available:
        loc = item.get("source") or {}
        candidate = loc.get("file")
        line = loc.get("line")
        if isinstance(candidate, str) and isinstance(line, int) and line > 0:
            try:
                return get_source_context(d.sources, candidate, line, radius)
            except (OSError, ValueError):
                pass
    return None


def context_sizes(d: Design, index: dict, graph: dict,
                  question: dict) -> dict:
    """A = RTL brut, B = index seul, C = index + trace + extrait sourcé.

    Même question et top pour les trois stratégies. Les charges utiles
    sont des données pour agent, pas des réponses générées par un modèle.
    """
    node = question["target"]
    instance_path, separator, name = node.rpartition(".")
    if not separator:
        raise ValueError("Signal cible malformé")
    ins = get_instance(index, instance_path)
    signal = get_signal_info(index, instance_path, name)
    base = {"question": question["question"], "top": d.top, "signal": node}
    raw = {**base, "sources": [{
        "file": src.name, "rtl": src.read_text(encoding="utf-8")
    } for src in d.sources]}
    indexed = {**base, "instance": {
        "path": ins["path"], "module": ins["module"],
        "parent": ins["parent"], "ports": ins["ports"],
    }, "signal_info": signal}
    trace = trace_dependencies(graph, node, "fanin",
                               max_depth=6, max_edges=100)
    if trace["truncated"]:
        raise ValueError("Trace tronquée : résultat benchmark non valide")
    hybrid = {**indexed, "trace": {
        "edges": trace["edges"], "visited_nodes": trace["visited_nodes"],
        "graph_warnings_count": len(trace["graph_warnings"]),
        "warning_examples": trace["graph_warnings"][:5],
    }, "source_excerpt": _source_snippet(d, signal)}
    expect = set(question.get("expected_reachable", []))
    reachable = set(trace["visited_nodes"])
    found = sorted(expect & reachable)
    missing = sorted(expect - reachable)
    b_raw, b_idx, b_hybrid = (compact_bytes(raw), compact_bytes(indexed),
                             compact_bytes(hybrid))
    return {
        "id": question["id"], "question": question["question"],
        "target": node,
        "expected_reachable": sorted(expect),
        "found_reachable": found, "missing_reachable": missing,
        "trace_edges": len(trace["edges"]),
        "trace_nodes": len(trace["visited_nodes"]),
        "source_excerpt_available": hybrid["source_excerpt"] is not None,
        "payload_bytes": {"A_raw": b_raw, "B_index": b_idx,
                          "C_hybrid": b_hybrid},
        "payload_whitespace_words": {
            "A_raw": whitespace_words(raw),
            "B_index": whitespace_words(indexed),
            "C_hybrid": whitespace_words(hybrid),
        },
        "relative_hybrid_bytes_vs_raw": round(b_hybrid / b_raw, 4),
        "interpretation": (
            "Octets JSON et mots séparés par espace : ce ne sont ni des "
            "tokens de modèle, ni des coûts API, ni une mesure de qualité."
        ),
    }


def evaluate_case(d: Design, out: Path, *, name: str,
                  labels: dict | None, repeat: int = 3,
                  timeout: int = 180) -> dict:
    """Répéter des exécutions réelles de slang. Aucune sortie simulée."""
    if not isinstance(repeat, int) or not 1 <= repeat <= 8:
        raise ValueError("repeat doit être compris entre 1 et 8")
    if timeout < 1:
        raise ValueError("timeout invalide")
    out.mkdir(parents=True, exist_ok=True)
    elapsed = []
    idx = graph = None
    signatures: list[list] = []
    for iteration in range(repeat):
        run_out = out / f"run-{iteration+1:02d}"
        start = time.perf_counter()
        result = dependency_design(d, run_out, timeout=timeout)
        elapsed.append(round((time.perf_counter() - start) * 1000, 3))
        if result.get("status") != "passed":
            raise RuntimeError(
                f"{name}: exécution slang n°{iteration+1} échouée: {result}"
            )
        idx = json.loads((run_out / "rtl_index.json").read_text(encoding="utf-8"))
        graph = json.loads((run_out / "rtl_dependencies.json").read_text(encoding="utf-8"))
        if idx["top"] != d.top or graph["top"] != d.top:
            raise AssertionError("Top différent dans les artefacts générés")
        if idx["source_fingerprint"] != fingerprint(d) or graph["source_fingerprint"] != fingerprint(d):
            raise AssertionError("Empreinte des sources incorrecte")
        signatures.append(sorted(
            [e["source"], e["target"], e["kind"]]
            for e in graph["edges"]
        ))
    if any(sig != signatures[0] for sig in signatures[1:]):
        raise AssertionError("Le graphe produit diffère entre les répétitions")
    assert idx is not None and graph is not None
    scored = None
    questions: list[dict] = []
    if labels:
        if labels.get("top") != d.top:
            raise ValueError(f"Labels incompatibles avec {d.top}")
        if "positive" in labels and "negative" in labels:
            scored = labelled_edge_scores(graph, labels["positive"], labels["negative"])
        questions = [context_sizes(d, idx, graph, q)
                     for q in labels.get("questions", [])]
    result = {
        "case": name, "top": d.top,
        "source_fingerprint": fingerprint(d),
        "sources_sha256": {
            src.name: __import__("hashlib").sha256(src.read_bytes()).hexdigest()
            for src in d.sources
        },
        "timing": {"unit": "milliseconds", "repetitions": repeat,
                   "runs": elapsed, "median_ms": round(statistics.median(elapsed), 3),
                   "min_ms": min(elapsed), "max_ms": max(elapsed),
                   "scope": "slang + parsing AST + index + graphe + écritures JSON"},
        "counts": {"modules": idx["counts"]["modules"],
                   "instances": idx["counts"]["instances"],
                   "signals": idx["counts"]["signals"],
                   "nodes": graph["counts"]["nodes"],
                   "edges": graph["counts"]["edges"],
                   "warnings": graph["counts"]["warnings"]},
        "labelled_edges": scored,
        "queries": questions,
        "coverage_caveat": (
            "Des arêtes non étiquetées ne sont ni fausses ni correctes par "
            "défaut. Les warnings signalent une analyse potentiellement partielle."
        ),
    }
    (out / "benchmark.case.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result

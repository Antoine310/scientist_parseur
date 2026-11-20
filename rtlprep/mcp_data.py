"""Backend MCP lecture seule : interrogation de rapports RTLPrep préexistants.

Aucun outil EDA ni sous-processus n'est lancé. Les chemins sont *fixés au
démarrage par l'opérateur*, pas fournis par les appels MCP. La session
contient un snapshot et ne recalcule aucune preuve.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .dependencies import GRAPH_SCHEMA_VERSION, trace_dependencies
from .index import (
    SCHEMA_VERSION, get_instance, get_instance_tree, get_module_summary,
    get_signal_info, get_source_context, list_modules,
)
from .manifest import load_design

MAX_INDEX_BYTES = 12 * 1024 * 1024
MAX_GRAPH_BYTES = 32 * 1024 * 1024
MAX_REPORT_BYTES = 1024 * 1024
MAX_ITEMS = 100
REPORT_NAMES = (
    "analyze.result.json", "index.result.json", "deps.result.json",
    "simulation.result.json", "formal.result.json",
    "equivalence.result.json", "lint.result.json", "synth.result.json",
)
REPORT_FIELDS = frozenset({
    "task", "status", "error", "top", "tests", "passed", "failed",
    "skipped", "returncode", "elapsed_seconds", "proof", "cover",
    "equivalent", "eqy_verdict", "partition_count", "graph_warnings",
    "edges", "index", "dependencies", "cell_count", "source_fingerprint",
})


def _load_json(path: Path, *, max_bytes: int) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size > max_bytes:
        raise ValueError(f"Rapport absent ou trop volumineux : {path.name}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Rapport JSON invalide (objet attendu) : {path.name}")
    return value


def _page(items: list[Any], limit: int, offset: int) -> dict[str, Any]:
    if (type(limit) is not int or type(offset) is not int
            or not 1 <= limit <= MAX_ITEMS or offset < 0):
        raise ValueError(f"Pagination : 1 <= limit <= {MAX_ITEMS} et offset >= 0")
    selected = items[offset: offset + limit]
    return {
        "total": len(items), "offset": offset, "items": selected,
        "next_offset": offset + limit if offset + limit < len(items) else None,
    }


class ReadOnlyRtl:
    """Vue d'un ensemble *explicitement fourni* d'artefacts et du manifeste.

    Sans argument fichier dans les méthodes exposées, un agent ne peut pas
    explorer librement le disque. Les fichiers lus sont des données non fiables.
    """

    def __init__(self, *, index_file: Path | None = None,
                 graph_file: Path | None = None,
                 manifest_file: Path | None = None,
                 reports_dir: Path | None = None) -> None:
        if not any((index_file, graph_file, reports_dir)):
            raise ValueError("Fournir --index, --graph ou --reports-dir")
        self.index = (_load_json(Path(index_file), max_bytes=MAX_INDEX_BYTES)
                      if index_file is not None else None)
        self.graph = (_load_json(Path(graph_file), max_bytes=MAX_GRAPH_BYTES)
                      if graph_file is not None else None)
        if self.index is not None and self.index.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("Index RTL non compatible (attendu : v1)")
        if self.graph is not None and self.graph.get("schema_version") != GRAPH_SCHEMA_VERSION:
            raise ValueError("Graphe RTL non compatible (attendu : v1)")
        if self.index is not None and self.graph is not None:
            if self.index.get("top") != self.graph.get("top"):
                raise ValueError("Index et graphe : modules top différents")
        self.design = load_design(manifest_file) if manifest_file is not None else None
        tops = [item["top"] for item in (self.index, self.graph) if item is not None]
        if self.design is not None and tops and any(top != self.design.top for top in tops):
            raise ValueError("Le top du manifeste diffère des rapports")
        self.reports: dict[str, dict[str, Any]] = {}
        if reports_dir is not None:
            folder = Path(reports_dir).expanduser().resolve()
            if not folder.is_dir():
                raise ValueError("Dossier des rapports absent")
            for basename in REPORT_NAMES:
                report = folder / basename
                if not report.is_file():
                    continue
                if not report.resolve().is_relative_to(folder):
                    raise ValueError("Lien symbolique de rapport hors du dossier autorisé")
                stored = _load_json(report, max_bytes=MAX_REPORT_BYTES)
                self.reports[basename] = {
                    k: v for k, v in stored.items() if k in REPORT_FIELDS
                }

    def capabilities(self) -> dict[str, Any]:
        """Portée exacte du snapshot ; **aucun** outil de compilation exposé."""
        return {
            "mode": "read_only_snapshot",
            "runs_eda": False, "edits_files": False, "uses_paid_llm_api": False,
            "index_available": self.index is not None,
            "graph_available": self.graph is not None,
            "source_available": self.design is not None,
            "report_names": sorted(self.reports),
            "top": self.index.get("top") if self.index else (
                self.graph.get("top") if self.graph else (
                    self.design.top if self.design else None)),
            "graph_warnings_count": len(self.graph.get("warnings", []))
            if self.graph else None,
            "caveat": "Rapports existants, non recalculés ; graphe partiel et non preuve formelle.",
        }

    def modules(self, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        return _page(list_modules(self._index()), limit, offset)

    def instances(self, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        return _page(get_instance_tree(self._index()), limit, offset)

    def module(self, name: str, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        value = get_module_summary(self._index(), name)
        page = _page(value["instances"], limit, offset)
        return {"name": value["name"], "instance_paths": _page(
            value["instance_paths"], limit, offset), "instances": page}

    def instance(self, path: str) -> dict[str, Any]:
        return get_instance(self._index(), path)

    def signal(self, instance_path: str, name: str) -> dict[str, Any]:
        return get_signal_info(self._index(), instance_path, name)

    def trace(self, signal: str, direction: str = "fanin", depth: int = 3,
              max_edges: int = 50) -> dict[str, Any]:
        if not 0 <= depth <= 6 or not 1 <= max_edges <= MAX_ITEMS:
            raise ValueError("Trace MCP : profondeur 0..6 et max_edges 1..100")
        result = trace_dependencies(self._graph(), signal, direction,
                                    max_depth=depth, max_edges=max_edges)
        # Le moteur original renvoie TOUS les warnings. Ne jamais les
        # transmettre en bloc (limites de contexte, sortie non bornée).
        warnings = result.pop("graph_warnings", [])
        result["graph_warnings_count"] = len(warnings)
        result["coverage"] = "partial" if warnings else "within_supported_scope"
        result["caveat"] = "Influence possible au niveau signal, pas preuve causale."
        return result

    def warnings(self, limit: int = 20, offset: int = 0) -> dict[str, Any]:
        return _page(self._graph().get("warnings", []), limit, offset)

    def source(self, filename: str, line: int, radius: int = 3) -> dict[str, Any]:
        if self.design is None:
            raise ValueError("Aucun manifeste autorisé fourni au serveur")
        # Un nom de base uniquement, jamais ../secret ou un chemin absolu.
        if filename != Path(filename).name or filename in (".", "..") or "\\" in filename:
            raise ValueError("Utiliser uniquement le nom d'un fichier du manifeste")
        if type(line) is not int or type(radius) is not int or not 1 <= line or not 0 <= radius <= 10:
            raise ValueError("Ligne >= 1 ; rayon limité à 0..10")
        return get_source_context(self.design.sources, filename, line, radius)

    def validations(self, limit: int = 20, offset: int = 0) -> dict[str, Any]:
        items = [{
            "file": name, "data": report, "origin": "stored_report_not_reexecuted",
        } for name, report in sorted(self.reports.items())]
        return _page(items, limit, offset)

    def _index(self) -> dict[str, Any]:
        if self.index is None:
            raise ValueError("Index non configuré : lancer RTLPrep index au préalable")
        return self.index

    def _graph(self) -> dict[str, Any]:
        if self.graph is None:
            raise ValueError("Graphe non configuré : lancer RTLPrep deps au préalable")
        return self.graph

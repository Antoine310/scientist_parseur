"""Serveur MCP local (stdio) basé sur le SDK *officiel* mcp 2.x.

Aucun des outils exposés n'exécute slang, Verilator, Yosys, SBY ou EQY.
L'opérateur sélectionne explicitement les artefacts au démarrage.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .mcp_data import ReadOnlyRtl


def create_server(snapshot: ReadOnlyRtl):
    """Construire un MCPServer officiel sans rendre mcp obligatoire ailleurs."""
    try:
        from mcp.server import MCPServer
    except ImportError as exc:
        raise RuntimeError(
            "MCP absent : utiliser Python >=3.11 et pip install -e '.[mcp]'"
        ) from exc

    server = MCPServer("RTLPrep")

    @server.tool(structured_output=True)
    def rtl_capabilities() -> dict[str, Any]:
        """Décrire les sources disponibles, limites et absence d'exécution EDA."""
        return snapshot.capabilities()

    @server.tool(structured_output=True)
    def rtl_modules(limit: int = 50, offset: int = 0) -> dict[str, Any]:
        """Lister les modules depuis un index RTLPrep v1, avec pagination."""
        return snapshot.modules(limit, offset)

    @server.tool(structured_output=True)
    def rtl_instances(limit: int = 50, offset: int = 0) -> dict[str, Any]:
        """Lister les chemins d'instances élaborées, de façon paginée."""
        return snapshot.instances(limit, offset)

    @server.tool(structured_output=True)
    def rtl_module(name: str, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        """Afficher la définition et les occurrences d'un module."""
        return snapshot.module(name, limit, offset)

    @server.tool(structured_output=True)
    def rtl_instance(path: str) -> dict[str, Any]:
        """Afficher les ports et la provenance d'une instance exacte."""
        return snapshot.instance(path)

    @server.tool(structured_output=True)
    def rtl_signal(instance_path: str, name: str) -> dict[str, Any]:
        """Lire les déclarations et les ports d'un signal de l'index."""
        return snapshot.signal(instance_path, name)

    @server.tool(structured_output=True)
    def rtl_find_signals(query: str, limit: int = 20,
                         offset: int = 0) -> dict[str, Any]:
        """Rechercher par sous-chaîne dans les noms de signaux et ports."""
        return snapshot.find_signals(query, limit, offset)

    @server.tool(structured_output=True)
    def rtl_trace(signal: str, direction: str = "fanin", depth: int = 3,
                  max_edges: int = 50) -> dict[str, Any]:
        """Parcours borné des influences possibles, PAS preuve de causalité."""
        return snapshot.trace(signal, direction, depth, max_edges)

    @server.tool(structured_output=True)
    def rtl_expressions(signal: str, limit: int = 20,
                        offset: int = 0) -> dict[str, Any]:
        """Lire les expressions continues et procédurales d'un signal exact."""
        return snapshot.expressions(signal, limit, offset)

    @server.tool(structured_output=True)
    def rtl_register_flow(signal: str, limit: int = 20,
                          offset: int = 0) -> dict[str, Any]:
        """Lire les chemins syntaxiques always_ff et le dernier NBA par chemin.

        Ne prouve ni la faisabilité d'un chemin ni le maintien d'un registre.
        """
        return snapshot.register_flow(signal, limit, offset)

    @server.tool(structured_output=True)
    def rtl_bit_accesses(signal: str, limit: int = 20,
                         offset: int = 0) -> dict[str, Any]:
        """Lire les sélections de bits et positions de concaténations connues.

        Ces correspondances syntaxiques ne prouvent pas une influence fonctionnelle.
        """
        return snapshot.bit_accesses(signal, limit, offset)

    @server.tool(structured_output=True)
    def rtl_warnings(limit: int = 20, offset: int = 0) -> dict[str, Any]:
        """Lire les limitations explicites du graphe (pagination obligatoire)."""
        return snapshot.warnings(limit, offset)

    @server.tool(structured_output=True)
    def rtl_source(filename: str, line: int, radius: int = 3) -> dict[str, Any]:
        """Lire un extrait d'un fichier expressément autorisé par le manifeste."""
        return snapshot.source(filename, line, radius)

    @server.tool(structured_output=True)
    def rtl_validations(limit: int = 20, offset: int = 0) -> dict[str, Any]:
        """Lire les statuts de rapports existants, sans exécuter de validation."""
        return snapshot.validations(limit, offset)

    return server


def serve(*, index_file: Path | None = None, graph_file: Path | None = None,
          manifest_file: Path | None = None,
          reports_dir: Path | None = None) -> None:
    """Lancer un serveur stdio : aucune écoute HTTP, stdout réservé à MCP."""
    snapshot = ReadOnlyRtl(index_file=index_file, graph_file=graph_file,
                           manifest_file=manifest_file, reports_dir=reports_dir)
    create_server(snapshot).run(transport="stdio")

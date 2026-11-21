"""Index syntaxique borné des affectations continues depuis l'AST élaboré slang.

Ce module ne lit pas les fichiers RTL : il préserve les noms d'opérateurs
émis par slang et la structure de l'expression, sans évaluer le matériel.
Les affectations procédurales et les cas complexes restent hors du périmètre.
"""
from __future__ import annotations

from typing import Any

from .index import build_index

EXPRESSION_SCHEMA_VERSION = 1
MAX_EXPRESSIONS = 2000
MAX_TREE_NODES = 96
MAX_DEPTH = 12
MAX_ATOM_LENGTH = 96

LITERAL_KINDS = frozenset({
    "IntegerLiteral", "RealLiteral", "StringLiteral",
    "UnbasedUnsizedIntegerLiteral", "Null",
})


def _atom(value: Any) -> str:
    """N'exposer aucun pointeur d'AST, texte illimité ou objet brut."""
    return str(value)[:MAX_ATOM_LENGTH]


def _source(node: dict[str, Any]) -> dict[str, Any] | None:
    filename = node.get("source_file_start") or node.get("source_file")
    line = node.get("source_line_start") or node.get("source_line")
    if not isinstance(filename, str) or not filename:
        return None
    return {
        "file": filename,
        "line": line if isinstance(line, int) and not isinstance(line, bool)
        and line > 0 else None,
    }


def build_expression_index(ast: dict[str, Any], *, expected_top: str,
                           index: dict[str, Any] | None = None) -> dict[str, Any]:
    """Extraire uniquement les RHS de ContinuousAssign, par instance élaborée.

    Chaque opérateur provient du champ 'op' de slang, et non du RTL textuel.
    Une expression partiellement comprise est explicitement marquée.
    """
    structural = index if index is not None else build_index(ast, expected_top=expected_top)
    if structural.get("schema_version") != 1 or structural.get("top") != expected_top:
        raise ValueError("Index RTL v1 / top incohérent pour les expressions")

    instances = {i["path"]: i for i in structural["instances"]}
    known: dict[str, set[str]] = {
        p: {port["name"] for port in inst["ports"]}
        for p, inst in instances.items()
    }
    for sig in structural["signals"]:
        known[sig["instance_path"]].add(sig["name"])

    # Only explicit semantic declaration IDs distinguish shadowed constants
    # from ordinary signals. Do not use identifier-prefix heuristics.
    constant_ids: set[str] = set()

    def constants(obj: Any) -> None:
        if isinstance(obj, list):
            for item in obj:
                constants(item)
        elif isinstance(obj, dict):
            if obj.get("kind") in ("Parameter", "EnumValue") and obj.get("addr") is not None:
                constant_ids.add(str(obj["addr"]))
            for key, item in obj.items():
                if key not in ("definition", "internalSymbol", "type") and isinstance(item, (dict, list)):
                    constants(item)

    constants(ast.get("design", {}))

    results: list[dict[str, Any]] = []
    stats = {
        "procedural_blocks_skipped": 0,
        "unsupported_targets": 0,
        "partial_expressions": 0,
        "truncated": False,
    }

    def symbol(expr: Any) -> tuple[str | None, str | None]:
        if not isinstance(expr, dict) or expr.get("kind") != "NamedValue":
            return None, None
        raw = expr.get("symbol")
        if not isinstance(raw, str):
            return None, None
        parts = raw.split(maxsplit=1)
        if len(parts) != 2:
            return None, None
        return parts[0], parts[1]

    def expression(path: str, node: Any, state: dict[str, Any],
                   depth: int = 0) -> dict[str, Any]:
        state["nodes"] += 1
        if depth > MAX_DEPTH or state["nodes"] > MAX_TREE_NODES:
            state["partial"] = True
            return {"kind": "unsupported", "ast_kind": "limit_exceeded"}
        if not isinstance(node, dict):
            state["partial"] = True
            return {"kind": "unsupported", "ast_kind": "malformed"}
        kind = node.get("kind")
        if kind == "NamedValue":
            address, name = symbol(node)
            if not name:
                state["partial"] = True
                return {"kind": "unsupported", "ast_kind": "unresolved_symbol"}
            if address in constant_ids:
                return {"kind": "constant_reference", "name": _atom(name)}
            if name in known.get(path, set()):
                return {"kind": "signal", "name": name, "path": f"{path}.{name}"}
            state["partial"] = True
            return {"kind": "unsupported", "ast_kind": "unknown_symbol"}
        if kind in LITERAL_KINDS:
            val = node.get("value")
            return {"kind": "literal", "literal_kind": kind,
                    "value": _atom(val) if val is not None else None}
        if kind == "BinaryOp":
            op = node.get("op")
            if not isinstance(op, str) or not op or len(op) > 64:
                state["partial"] = True
                return {"kind": "unsupported", "ast_kind": "BinaryOp_without_op"}
            return {
                "kind": "binary", "operator": op,
                "left": expression(path, node.get("left"), state, depth + 1),
                "right": expression(path, node.get("right"), state, depth + 1),
            }
        if kind == "UnaryOp":
            op = node.get("op")
            if not isinstance(op, str) or not op or len(op) > 64:
                state["partial"] = True
                return {"kind": "unsupported", "ast_kind": "UnaryOp_without_op"}
            return {"kind": "unary", "operator": op,
                    "operand": expression(path, node.get("operand"), state, depth + 1)}
        if kind in ("Conversion", "SignedConversion"):
            return {"kind": "conversion", "ast_kind": kind,
                    "operand": expression(path, node.get("operand"), state, depth + 1)}
        # Do not silently flatten ternaries, selectors, calls, or concatenations:
        # their exact behavior and bit mapping is outside this first increment.
        state["partial"] = True
        return {"kind": "unsupported", "ast_kind": _atom(kind)}

    def visit(members: Any, parent: str | None = None) -> None:
        if not isinstance(members, list):
            return
        for node in members:
            if not isinstance(node, dict):
                continue
            kind = node.get("kind")
            if kind in ("GenerateBlock", "GenerateBlockArray", "Scope"):
                if node.get("isUninstantiated") is not True:
                    visit(node.get("members"), parent)
                continue
            if kind == "ProceduralBlock" and parent is not None:
                stats["procedural_blocks_skipped"] += 1
                continue
            if kind == "ContinuousAssign" and parent is not None:
                if len(results) >= MAX_EXPRESSIONS:
                    stats["truncated"] = True
                    continue
                assignment = node.get("assignment")
                if not isinstance(assignment, dict) or assignment.get("kind") != "Assignment":
                    stats["unsupported_targets"] += 1
                    continue
                lhs = assignment.get("left")
                _, name = symbol(lhs)
                if name not in known.get(parent, set()):
                    stats["unsupported_targets"] += 1
                    continue
                # A selected bit/range is a different destination from the
                # whole signal: do not pretend to know its write semantics.
                if not isinstance(lhs, dict) or lhs.get("kind") != "NamedValue":
                    stats["unsupported_targets"] += 1
                    continue
                state: dict[str, Any] = {"nodes": 0, "partial": False}
                tree = expression(parent, assignment.get("right"), state)
                if state["partial"]:
                    stats["partial_expressions"] += 1
                results.append({
                    "target": f"{parent}.{name}",
                    "expression": tree,
                    "source": _source(assignment) or _source(node),
                    "coverage": "partial" if state["partial"] else "syntax_supported",
                })
                continue
            if kind == "Instance":
                path = f"{parent}.{node['name']}" if parent else node["name"]
                if path not in instances:
                    raise ValueError(f"Instance non indexée pour expressions : {path}")
                body = node.get("body")
                if not isinstance(body, dict):
                    raise ValueError(f"Corps d'instance absent : {path}")
                visit(body.get("members"), path)

    design = ast.get("design", {})
    visit(design.get("members"))
    results.sort(key=lambda r: (r["target"], (r["source"] or {}).get("line") or 0))
    return {
        "schema_version": EXPRESSION_SCHEMA_VERSION,
        "scope": "continuous_assign_rhs_only",
        "items": results,
        "counts": {"captured": len(results), **stats},
        "caveat": (
            "Structure syntaxique de slang, pas évaluation du matériel ; "
            "procédures, conditions de branche, sélections de bits et "
            "opérateurs inconnus non couverts complètement."
        ),
    }

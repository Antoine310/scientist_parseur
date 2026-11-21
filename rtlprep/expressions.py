"""Index borné des expressions et chemins procéduraux de l'AST slang.

Aucune analyse de texte RTL, exécution ou preuve de matériel. Les arbres,
les conditions de branche et les événements proviennent du JSON élaboré.
Les constructions non couvertes restent explicitement partielles.
"""
from __future__ import annotations

from typing import Any

from .index import build_index

EXPRESSION_SCHEMA_VERSION = 1
MAX_EXPRESSIONS = 2000
MAX_TREE_NODES = 96
MAX_DEPTH = 12
MAX_ATOM_LENGTH = 96
MAX_STATEMENT_DEPTH = 32
MAX_GUARDS = 16
MAX_EVENTS = 16

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
    """Extraire RHS, gardes et événements d'affectations RTL élaborées.

    Les gardes décrivent le chemin syntaxique de chaque affectation, pas
    l'équivalence logique, la priorité des nonblocking assignments ni
    la valeur calculée par un processus complet.
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
        "procedural_blocks_visited": 0,
        "unsupported_statements": 0,
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

    def add_assignment(path: str, node: Any, *, procedure_kind: str | None = None,
                       guards: tuple[dict[str, Any], ...] = (),
                       events: tuple[dict[str, Any], ...] = (),
                       context_partial: bool = False,
                       source_fallback: dict[str, Any] | None = None) -> None:
        if len(results) >= MAX_EXPRESSIONS:
            stats["truncated"] = True
            return
        if not isinstance(node, dict) or node.get("kind") != "Assignment":
            stats["unsupported_statements"] += 1
            return
        lhs = node.get("left")
        _, name = symbol(lhs)
        if not isinstance(lhs, dict) or lhs.get("kind") != "NamedValue" or (
            name not in known.get(path, set())
        ):
            stats["unsupported_targets"] += 1
            return
        state: dict[str, Any] = {"nodes": 0, "partial": context_partial}
        tree = expression(path, node.get("right"), state)
        row: dict[str, Any] = {
            "target": f"{path}.{name}",
            "expression": tree,
            "source": _source(node) or _source(source_fallback or {}),
        }
        if procedure_kind is not None:
            rendered_guards: list[dict[str, Any]] = []
            for g in guards[:MAX_GUARDS]:
                if g["kind"] == "if":
                    rendered_guards.append({
                        "kind": "if", "branch": g["branch"],
                        "expression": expression(path, g["expr"], state),
                    })
                elif g["kind"] == "case":
                    rendered_guards.append({
                        "kind": "case", "branch": g["branch"],
                        "comparison": g["comparison"],
                        "selector": expression(path, g["selector"], state),
                        "labels": [
                            expression(path, label, state)
                            for label in g["labels"][:MAX_GUARDS]
                        ],
                    })
                    if len(g["labels"]) > MAX_GUARDS:
                        state["partial"] = True
                else:
                    rendered_guards.append({"kind": "unsupported_guard"})
                    state["partial"] = True
            if len(guards) > MAX_GUARDS:
                rendered_guards.append({"kind": "unsupported_guard", "reason": "limit_exceeded"})
                state["partial"] = True
            rendered_events: list[dict[str, Any]] = []
            for event in events[:MAX_EVENTS]:
                detail: dict[str, Any] = {
                    "edge": event["edge"],
                    "expression": expression(path, event["expr"], state),
                }
                if detail["expression"]["kind"] != "signal" or (
                    detail["edge"] not in ("PosEdge", "NegEdge", "BothEdges")
                ):
                    state["partial"] = True
                rendered_events.append(detail)
            if len(events) > MAX_EVENTS:
                state["partial"] = True
            is_nb = node.get("isNonBlocking")
            if type(is_nb) is not bool:
                state["partial"] = True
            row.update({
                "assignment_kind": "procedural",
                "procedure_kind": procedure_kind,
                "nonblocking": is_nb if type(is_nb) is bool else None,
                "guards": rendered_guards,
                "events": rendered_events,
            })
        else:
            row["assignment_kind"] = "continuous"
        row["coverage"] = "partial" if state["partial"] else "syntax_supported"
        if state["partial"]:
            stats["partial_expressions"] += 1
        results.append(row)

    def statements(path: str, node: Any, *, procedure_kind: str,
                   guards: tuple[dict[str, Any], ...] = (),
                   events: tuple[dict[str, Any], ...] = (),
                   partial: bool = False, depth: int = 0) -> None:
        if depth > MAX_STATEMENT_DEPTH:
            stats["unsupported_statements"] += 1
            return
        if isinstance(node, list):
            for child in node:
                statements(path, child, procedure_kind=procedure_kind,
                           guards=guards, events=events, partial=partial, depth=depth + 1)
            return
        if not isinstance(node, dict):
            if node is not None:
                stats["unsupported_statements"] += 1
            return
        kind = node.get("kind")
        if kind == "ExpressionStatement":
            add_assignment(path, node.get("expr"), procedure_kind=procedure_kind,
                           guards=guards, events=events, context_partial=partial,
                           source_fallback=node)
        elif kind in ("List", "StatementList", "Block"):
            field = {"List": "list", "StatementList": "statements",
                     "Block": "body"}[kind]
            nested = node.get(field)
            if not isinstance(nested, (list, dict)):
                stats["unsupported_statements"] += 1
            else:
                statements(path, nested, procedure_kind=procedure_kind,
                           guards=guards, events=events, partial=partial, depth=depth + 1)
        elif kind == "Timed":
            timing = node.get("timing")
            local_events = list(events)
            local_partial = partial
            if isinstance(timing, dict) and timing.get("kind") == "EventList":
                sequence = timing.get("events")
                if not isinstance(sequence, list):
                    local_partial = True
                else:
                    for event in sequence:
                        if isinstance(event, dict) and event.get("kind") == "SignalEvent":
                            local_events.append({
                                "expr": event.get("expr"),
                                "edge": _atom(event.get("edge", "Unknown")),
                            })
                        else:
                            local_partial = True
            else:
                # Implicit timing, event expressions and other constructs must
                # never be presented as known edges.
                local_partial = True
            statements(path, node.get("stmt"), procedure_kind=procedure_kind,
                       guards=guards, events=tuple(local_events), partial=local_partial,
                       depth=depth + 1)
        elif kind == "Conditional":
            conditions = node.get("conditions")
            if (isinstance(conditions, list) and len(conditions) == 1
                    and isinstance(conditions[0], dict)
                    and isinstance(conditions[0].get("expr"), dict)):
                cond = conditions[0]["expr"]
                for branch, field in (("then", "ifTrue"), ("else", "ifFalse")):
                    child = node.get(field)
                    if child is not None:
                        spec = {"kind": "if", "branch": branch, "expr": cond}
                        statements(path, child, procedure_kind=procedure_kind,
                                   guards=guards + (spec,), events=events,
                                   partial=partial, depth=depth + 1)
            else:
                # Conditions with pattern matching or multiple operands cannot
                # be approximated by a single boolean conjunction.
                for field in ("ifTrue", "ifFalse"):
                    if node.get(field) is not None:
                        statements(path, node[field], procedure_kind=procedure_kind,
                                   guards=guards + ({"kind": "unsupported"},),
                                   events=events, partial=True, depth=depth + 1)
        elif kind == "Case":
            mode = node.get("condition")
            select = node.get("expr")
            local_partial = partial or mode != "Normal"
            items = node.get("items")
            if not isinstance(items, list):
                stats["unsupported_statements"] += 1
                return
            for item in items:
                if not isinstance(item, dict) or not isinstance(item.get("expressions"), list):
                    stats["unsupported_statements"] += 1
                    continue
                labels = item["expressions"]
                spec = {
                    "kind": "case", "branch": "item",
                    "comparison": _atom(mode),
                    "selector": select, "labels": labels,
                }
                statements(path, item.get("stmt"), procedure_kind=procedure_kind,
                           guards=guards + (spec,), events=events,
                           partial=local_partial or not labels, depth=depth + 1)
            default = node.get("defaultCase")
            if default is not None:
                spec = {
                    "kind": "case", "branch": "default",
                    "comparison": _atom(mode),
                    "selector": select, "labels": [],
                }
                statements(path, default, procedure_kind=procedure_kind,
                           guards=guards + (spec,), events=events, partial=local_partial,
                           depth=depth + 1)
        elif kind not in ("Empty", "EmptyStatement"):
            stats["unsupported_statements"] += 1

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
                procedure_kind = node.get("procedureKind")
                if procedure_kind in ("AlwaysFF", "AlwaysComb", "AlwaysLatch", "Always"):
                    stats["procedural_blocks_visited"] += 1
                    statements(parent, node.get("body"), procedure_kind=procedure_kind)
                else:
                    stats["procedural_blocks_skipped"] += 1
                continue
            if kind == "ContinuousAssign" and parent is not None:
                add_assignment(parent, node.get("assignment"), source_fallback=node)
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
        "scope": "continuous_and_supported_procedural_assignments",
        "items": results,
        "counts": {"captured": len(results), **stats},
        "caveat": (
            "AST syntaxique, chemins de branche et événements potentiels ; "
            "pas de preuve du comportement, priorité NBA, cycle ni reset "
            "déduit. Les constructions non reconnues restent partielles."
        ),
    }

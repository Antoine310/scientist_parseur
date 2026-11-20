"""Graphe de dépendances RTL conservateur, dérivé de l'AST élaboré slang.

Portée MVP : affectations simples, expressions de base, conditions if/ternaires,
événements always_ff et liaisons de ports In/Out. Aucune interprétation de
netlists, de fonctions, de tâches ou de generate complexes. Les cas non
reconnus sont signalés, jamais inférés à partir de texte source.
"""
from __future__ import annotations

from collections import deque
from typing import Any

from .index import build_index

GRAPH_SCHEMA_VERSION = 1
LITERALS = frozenset({"IntegerLiteral", "RealLiteral", "StringLiteral",
                      "Null", "EmptyArgument", "UnbasedUnsizedIntegerLiteral"})
BINARY = frozenset({"BinaryOp"})
UNARY = frozenset({"UnaryOp", "Conversion", "SignedConversion"})


def _location(node: dict[str, Any]) -> dict[str, Any] | None:
    path = node.get("source_file_start") or node.get("source_file")
    line = node.get("source_line_start") or node.get("source_line")
    if not isinstance(path, str) or not path:
        return None
    return {"file": path, "line": line if isinstance(line, int) and line > 0 else None}


def _symbol_name(node: dict[str, Any]) -> str | None:
    """slang 12.1 écrit 'adresse nom' : ignorer l'adresse instable."""
    value = node.get("symbol")
    if not isinstance(value, str):
        return None
    parts = value.split(maxsplit=1)
    return parts[1] if len(parts) == 2 and parts[1] else None


def build_dependency_graph(ast: dict[str, Any], *, expected_top: str,
                           index: dict[str, Any] | None = None) -> dict[str, Any]:
    """Bâtir des liens orientés source -> destination, à granularité signal.

    Les détails de sélection de bits et les effets combinatoires de primitives
    non reconnues ne sont pas déduits. Les avertissements explicitent ces limites.
    """
    structural = index if index is not None else build_index(ast, expected_top=expected_top)
    if structural.get("schema_version") != 1 or structural.get("top") != expected_top:
        raise ValueError("Index RTL v1 / top incohérent avec le graphe demandé")
    instances = {i["path"]: i for i in structural["instances"]}
    known: dict[str, set[str]] = {
        path: {p["name"] for p in inst["ports"]}
        for path, inst in instances.items()
    }
    for sig in structural["signals"]:
        known[sig["instance_path"]].add(sig["name"])
    nodes = sorted(f"{path}.{name}" for path, names in known.items() for name in names)
    node_set = set(nodes)
    edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str, str, bool, str]] = set()
    warnings: list[dict[str, Any]] = []
    warning_keys: set[tuple[str, str]] = set()

    # slang encodes references as "symbol-address symbol-name". The address
    # refers to the *exact* semantic declaration in the same exported AST.
    # Unlike ignoring names such as OPCODE_*, this is safe with shadowing.
    constant_declarations: dict[str, str] = {}
    def collect_parameter_declarations(obj: Any) -> None:
        if isinstance(obj, list):
            for entry in obj:
                collect_parameter_declarations(entry)
        elif isinstance(obj, dict):
            if obj.get("kind") == "Parameter" and obj.get("addr") is not None:
                constant_declarations[str(obj["addr"])] = str(obj.get("name", ""))
            for key, value in obj.items():
                if key not in ("definition", "internalSymbol", "type") and isinstance(value, (dict, list)):
                    collect_parameter_declarations(value)

    collect_parameter_declarations(ast.get("design", {}))
    constant_refs_seen: set[str] = set()

    def warn(path: str, reason: str) -> None:
        key = (path, reason)
        if key not in warning_keys:
            warning_keys.add(key)
            warnings.append({"context": path, "reason": reason})

    def resolve(path: str, expr: Any) -> str | None:
        if not isinstance(expr, dict) or expr.get("kind") != "NamedValue":
            return None
        name = _symbol_name(expr)
        symbol = expr.get("symbol")
        reference_id = symbol.split(maxsplit=1)[0] if isinstance(symbol, str) else None
        if reference_id in constant_declarations:
            constant_refs_seen.add(reference_id)
            return None
        # slang explicitly marks some already evaluated parameters as constant;
        # use that semantic tag, never a name prefix or regex.
        if "constant" in expr and name not in known.get(path, set()):
            return None
        if name not in known.get(path, set()):
            warn(path, f"Référence NamedValue inconnue : {name!r}")
            return None
        return f"{path}.{name}"

    def target(path: str, expr: Any) -> str | None:
        if not isinstance(expr, dict):
            warn(path, "Cible d'affectation non structurée")
            return None
        kind = expr.get("kind")
        if kind == "NamedValue":
            return resolve(path, expr)
        if kind in ("ElementSelect", "RangeSelect"):
            warn(path, "Sélection de bits : dépendance au signal entier (approximation)")
            return target(path, expr.get("value"))
        warn(path, f"Cible non prise en charge : {kind}")
        return None

    def reads(path: str, expr: Any) -> tuple[set[str], set[str]]:
        """(données, contrôle). Ne jamais chercher du RTL à l'aide de regex."""
        if not isinstance(expr, dict):
            return set(), set()
        kind = expr.get("kind")
        if kind == "NamedValue":
            ref = resolve(path, expr)
            return ({ref} if ref else set()), set()
        if kind in LITERALS:
            return set(), set()
        if kind in BINARY:
            left = reads(path, expr.get("left"))
            right = reads(path, expr.get("right"))
            return left[0] | right[0], left[1] | right[1]
        if kind in UNARY:
            return reads(path, expr.get("operand"))
        if kind in ("ElementSelect", "RangeSelect"):
            # Granularité signal entier : les indices sont des sources de données
            # potentielles (quel bit est lu), pas des signaux à indexer.
            base = reads(path, expr.get("value"))
            selectors = [expr.get("selector")] if kind == "ElementSelect" else [
                expr.get("left"), expr.get("right")
            ]
            data, control = set(base[0]), set(base[1])
            for selector_expr in selectors:
                sel_data, sel_control = reads(path, selector_expr)
                data.update(sel_data | sel_control)
            warn(path, "Sélection de bits/plage : dépendance au signal entier")
            return data, control
        if kind == "Replication":
            # slang v12.1: {N{expression}} -> Replication(count, concat).
            # Le nombre de répétitions est normalement une constante
            # d'élaboration ; conserver une dépendance si l'AST en indique une.
            content = expr.get("concat")
            if not isinstance(content, dict):
                warn(path, "Replication sans concaténation valide")
                return set(), set()
            data, control = reads(path, content)
            number_data, number_control = reads(path, expr.get("count"))
            return data | number_data, control | number_control
        if kind == "Concatenation":
            operands = expr.get("operands")
            if not isinstance(operands, list):
                warn(path, "Concatenation sans liste d'opérandes")
                return set(), set()
            data: set[str] = set()
            control: set[str] = set()
            for operand in operands:
                operand_data, operand_control = reads(path, operand)
                data.update(operand_data)
                control.update(operand_control)
            return data, control
        if kind == "ConditionalOp":
            cond_refs: set[str] = set()
            for condition in expr.get("conditions", []):
                if isinstance(condition, dict):
                    d, c = reads(path, condition.get("expr"))
                    cond_refs.update(d | c)
            a = reads(path, expr.get("left"))
            b = reads(path, expr.get("right"))
            return a[0] | b[0], cond_refs | a[1] | b[1]
        warn(path, f"Expression non prise en charge : {kind}")
        return set(), set()

    def add(source: str, dest: str, kind: str, context: dict[str, Any],
            *, sequential: bool = False, detail: str = "") -> None:
        if source not in node_set or dest not in node_set:
            warn(dest, f"Arête ignorée : symbole inconnu {source} -> {dest}")
            return
        key = (source, dest, kind, sequential, detail)
        if key not in seen_edges:
            seen_edges.add(key)
            edges.append({"source": source, "target": dest, "kind": kind,
                          "sequential": sequential, "detail": detail,
                          "location": _location(context)})

    def assignment(path: str, obj: Any, *, controls: frozenset[str] = frozenset(),
                   events: tuple[tuple[str, str], ...] = (), sequential: bool = False) -> None:
        if not isinstance(obj, dict) or obj.get("kind") != "Assignment":
            warn(path, "Affectation non reconnue")
            return
        dst = target(path, obj.get("left"))
        if dst is None:
            return
        values, expression_controls = reads(path, obj.get("right"))
        for source in sorted(values):
            add(source, dst, "data", obj, sequential=sequential)
        for source in sorted(set(controls) | expression_controls):
            add(source, dst, "control", obj, sequential=sequential)
        for source, edge in events:
            add(source, dst, "event", obj, sequential=sequential, detail=edge)

    def statements(path: str, obj: Any, *, controls: frozenset[str] = frozenset(),
                   events: tuple[tuple[str, str], ...] = (), sequential: bool = False) -> None:
        if isinstance(obj, list):
            for child in obj:
                statements(path, child, controls=controls, events=events,
                           sequential=sequential)
            return
        if not isinstance(obj, dict):
            return
        kind = obj.get("kind")
        if kind == "ExpressionStatement":
            assignment(path, obj.get("expr"), controls=controls,
                       events=events, sequential=sequential)
        elif kind == "Block":
            stmts = obj.get("body")
            if isinstance(stmts, list):
                for child in stmts:
                    statements(path, child, controls=controls, events=events,
                               sequential=sequential)
            else:
                statements(path, stmts, controls=controls, events=events,
                           sequential=sequential)
        elif kind == "List":
            # Vrai slang v12.1 : les séquences begin/end contenant plusieurs
            # instructions sont exportées avec kind=List et une clé "list".
            children = obj.get("list")
            if not isinstance(children, list):
                warn(path, "List sans liste d'instructions valide")
            else:
                statements(path, children, controls=controls, events=events,
                           sequential=sequential)
        elif kind == "StatementList":
            for child in obj.get("statements", []):
                statements(path, child, controls=controls, events=events,
                           sequential=sequential)
        elif kind == "Conditional":
            control = set(controls)
            for cond in obj.get("conditions", []):
                if isinstance(cond, dict):
                    d, c = reads(path, cond.get("expr"))
                    control.update(d | c)
            nested = frozenset(control)
            statements(path, obj.get("ifTrue"), controls=nested,
                       events=events, sequential=sequential)
            statements(path, obj.get("ifFalse"), controls=nested,
                       events=events, sequential=sequential)
        elif kind == "Case":
            if obj.get("condition") != "Normal":
                warn(path, f"Case à comparaisons spéciales non couvert : {obj.get('condition')}")
            control = set(controls)
            expr_data, expr_control = reads(path, obj.get("expr"))
            control.update(expr_data | expr_control)
            items = obj.get("items")
            if not isinstance(items, list):
                warn(path, "Case sans liste de branches")
                return
            # Une expression d'étiquette peut elle-même dépendre de variables.
            # Elles participent à la décision de sélection de branche.
            all_label_refs: set[str] = set()
            for item in items:
                if not isinstance(item, dict):
                    warn(path, "Branche case malformée")
                    continue
                labels = item.get("expressions")
                if not isinstance(labels, list):
                    warn(path, "Étiquettes case malformées")
                    continue
                for label in labels:
                    d, c = reads(path, label)
                    all_label_refs.update(d | c)
            case_controls = frozenset(control | all_label_refs)
            for item in items:
                if isinstance(item, dict):
                    statements(path, item.get("stmt"), controls=case_controls,
                               events=events, sequential=sequential)
            statements(path, obj.get("defaultCase"), controls=case_controls,
                       events=events, sequential=sequential)
        elif kind == "Timed":
            extracted: list[tuple[str, str]] = list(events)
            timing = obj.get("timing")
            if isinstance(timing, dict) and timing.get("kind") == "EventList":
                for event in timing.get("events", []):
                    if isinstance(event, dict) and event.get("kind") == "SignalEvent":
                        expr = event.get("expr")
                        ref = resolve(path, expr)
                        if ref:
                            extracted.append((ref, str(event.get("edge", "Unknown"))))
                    else:
                        warn(path, "Événement temporel non pris en charge")
            elif timing is not None:
                warn(path, f"Timing non pris en charge : {timing.get('kind') if isinstance(timing, dict) else type(timing).__name__}")
            statements(path, obj.get("stmt"), controls=controls,
                       events=tuple(extracted), sequential=sequential)
        elif kind in ("Empty", "EmptyStatement"):
            pass
        else:
            warn(path, f"Instruction non prise en charge : {kind}")

    def connections(node: dict[str, Any], path: str, parent: str | None) -> None:
        if parent is None:
            return
        for connection in node.get("connections", []):
            if not isinstance(connection, dict):
                continue
            port = connection.get("port")
            expr = connection.get("expr")
            if not isinstance(port, dict) or not isinstance(port.get("name"), str):
                warn(path, "Connexion sans port identifiable")
                continue
            local = f"{path}.{port['name']}"
            direction = port.get("direction")
            if direction == "In":
                data, control = reads(parent, expr)
                for source in sorted(data | control):
                    add(source, local, "port_input", expr if isinstance(expr, dict) else port)
            elif direction == "Out":
                # slang fournit habituellement un Assignment(left=<lvalue>, right=EmptyArgument)
                lhs = expr.get("left") if isinstance(expr, dict) and expr.get("kind") == "Assignment" else expr
                dest = target(parent, lhs)
                if dest:
                    add(local, dest, "port_output", expr if isinstance(expr, dict) else port)
            else:
                warn(path, f"Port {port['name']} direction {direction} non prise en charge")

    visited_instances: set[str] = set()

    def visit(members: list[Any], parent: str | None = None) -> None:
        for node in members:
            if not isinstance(node, dict):
                continue
            if node.get("kind") in ("GenerateBlock", "GenerateBlockArray", "Scope"):
                # Les branches inactives ne font pas partie du matériel élaboré.
                if node.get("isUninstantiated") is True:
                    continue
                nested = node.get("members")
                if isinstance(nested, list):
                    visit(nested, parent)
                else:
                    warn(parent or expected_top, "Scope non indexable dans le graphe")
                continue
            if node.get("kind") == "ContinuousAssign" and parent is not None:
                assignment(parent, node.get("assignment"))
                continue
            if node.get("kind") == "ProceduralBlock" and parent is not None:
                procedure_kind = node.get("procedureKind")
                if procedure_kind not in ("AlwaysFF", "AlwaysComb", "AlwaysLatch", "Always"):
                    warn(parent, f"Procédure non prise en charge : {procedure_kind}")
                else:
                    statements(parent, node.get("body"),
                               sequential=(procedure_kind == "AlwaysFF"))
                continue
            if node.get("kind") != "Instance":
                continue
            path = f"{parent}.{node['name']}" if parent else node["name"]
            if path not in instances:
                raise ValueError(f"Instance non indexée : {path}")
            visited_instances.add(path)
            connections(node, path, parent)
            body = node["body"]
            visit(body["members"], path)

    visit(ast["design"]["members"])
    for missing_path in sorted(set(instances) - visited_instances):
        warn(missing_path, "Instance connue de l'index mais absente du graphe")
    edges.sort(key=lambda x: (x["target"], x["source"], x["kind"], x["detail"]))
    warnings.sort(key=lambda x: (x["context"], x["reason"]))
    return {
        "schema_version": GRAPH_SCHEMA_VERSION, "backend": "slang-ast-json",
        "top": expected_top, "nodes": nodes, "edges": edges,
        "counts": {"nodes": len(nodes), "edges": len(edges), "warnings": len(warnings)},
        "warnings": warnings,
        "resolved_parameter_symbols": sorted(
            constant_declarations[addr] for addr in constant_refs_seen
        ),
        "limitations": [
            "Dépendances conservatrices au niveau signal, sans granularité bit",
            "Case normal, concaténations, sélections et generate if simples seulement",
            "Pas de résolution des fonctions, tâches, casez/casex, generate complexes",
            "Événements toujours classés event : horloge versus reset non inférés",
            "Le graphe peut être incomplet si des avertissements sont présents",
            "Pas de preuve fonctionnelle, timing ou CDC",
        ],
    }


def trace_dependencies(graph: dict[str, Any], node: str, direction: str = "fanin",
                       *, max_depth: int = 3, max_edges: int = 200) -> dict[str, Any]:
    """Parcours en largeur borné et robuste aux cycles ; zéro inférence LLM."""
    if graph.get("schema_version") != GRAPH_SCHEMA_VERSION:
        raise ValueError("Version de graphe inconnue")
    if direction not in ("fanin", "fanout"):
        raise ValueError("Direction attendue : fanin ou fanout")
    if not 0 <= max_depth <= 15 or not 1 <= max_edges <= 5000:
        raise ValueError("Limites de recherche invalides")
    if node not in set(graph["nodes"]):
        raise KeyError(f"Signal inconnu dans le graphe : {node}")
    adjacency: dict[str, list[dict[str, Any]]] = {}
    lookup = "target" if direction == "fanin" else "source"
    next_key = "source" if direction == "fanin" else "target"
    for edge in graph["edges"]:
        adjacency.setdefault(edge[lookup], []).append(edge)
    queue = deque([(node, 0)])
    visited = {node}
    used_edges: set[tuple[str, str, str, str]] = set()
    found: list[dict[str, Any]] = []
    truncated = False
    while queue:
        current, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for edge in adjacency.get(current, []):
            key = (edge["source"], edge["target"], edge["kind"], edge.get("detail", ""))
            if key not in used_edges:
                if len(found) >= max_edges:
                    truncated = True
                    break
                used_edges.add(key)
                found.append({**edge, "depth": depth + 1})
            neighbor = edge[next_key]
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, depth + 1))
        if truncated:
            break
    return {"query": node, "direction": direction, "max_depth": max_depth,
            "edges": found, "visited_nodes": sorted(visited), "truncated": truncated,
            "graph_warnings": graph.get("warnings", [])}

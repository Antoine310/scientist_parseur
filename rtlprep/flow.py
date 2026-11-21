"""Parcours syntaxiques bornés des mises à jour always_ff depuis l'AST slang.

Ne simule ni les expressions, ni X/Z, ni les transitions temporelles.
L'analyse est *fail-closed* : un noeud inconnu ne devient jamais un
chemin sans écriture ou une priorité présumée.
"""
from __future__ import annotations

from typing import Any

from .index import build_index

FLOW_SCHEMA_VERSION = 1
MAX_PROCESSES = 512
MAX_TARGETS = 2000
MAX_PATHS = 32
MAX_STATEMENTS = 512
MAX_DEPTH = 32
MAX_GUARDS = 16
MAX_WRITES_PER_PATH = 32
MAX_CONDITION_DEPTH = 10
MAX_CONDITION_NODES = 64
MAX_PROBE_NODES = 2048
ATOM_LIMIT = 96
LITERALS = frozenset({
    "IntegerLiteral", "RealLiteral", "StringLiteral",
    "UnbasedUnsizedIntegerLiteral", "Null",
})


class _Unknown(Exception):
    """Une structure non couverte interdit toute conclusion sur le maintien."""


def _source(node: Any) -> dict[str, Any] | None:
    if not isinstance(node, dict):
        return None
    file = node.get("source_file_start") or node.get("source_file")
    line = node.get("source_line_start") or node.get("source_line")
    if not isinstance(file, str) or not file:
        return None
    return {"file": file, "line": line if type(line) is int and line > 0 else None}


def _name(node: Any) -> str | None:
    if not isinstance(node, dict) or node.get("kind") != "NamedValue":
        return None
    raw = node.get("symbol")
    if not isinstance(raw, str):
        return None
    tokens = raw.split(maxsplit=1)
    return tokens[1] if len(tokens) == 2 and tokens[1] else None


def _condition(node: Any, path: str, known: set[str], budget: list[int],
               depth: int = 0) -> dict[str, Any]:
    budget[0] += 1
    if budget[0] > MAX_CONDITION_NODES or depth > MAX_CONDITION_DEPTH:
        raise _Unknown("condition_too_large")
    if not isinstance(node, dict):
        raise _Unknown("condition_not_ast")
    kind = node.get("kind")
    if kind == "NamedValue":
        name = _name(node)
        if name in known:
            return {"kind": "signal", "path": f"{path}.{name}"}
        raise _Unknown("condition_unresolved_symbol")
    if kind in LITERALS:
        value = node.get("value")
        return {"kind": "literal", "value": str(value)[:ATOM_LIMIT]
                if value is not None else None}
    if kind == "UnaryOp":
        op = node.get("op")
        if not isinstance(op, str) or not op or len(op) > 64:
            raise _Unknown("invalid_unary_operator")
        return {"kind": "unary", "operator": op,
                "operand": _condition(node.get("operand"), path, known,
                                      budget, depth + 1)}
    if kind == "BinaryOp":
        op = node.get("op")
        if not isinstance(op, str) or not op or len(op) > 64:
            raise _Unknown("invalid_binary_operator")
        return {"kind": "binary", "operator": op,
                "left": _condition(node.get("left"), path, known,
                                    budget, depth + 1),
                "right": _condition(node.get("right"), path, known,
                                     budget, depth + 1)}
    if kind in ("Conversion", "SignedConversion"):
        return {"kind": "conversion", "ast_kind": kind,
                "operand": _condition(node.get("operand"), path, known,
                                      budget, depth + 1)}
    raise _Unknown("condition_unsupported_" + str(kind)[:64])


def _simple_rhs(node: Any, depth: int = 0) -> bool:
    """Écarter fonctions / assignations imbriquées et effets de bord possibles."""
    if depth > MAX_CONDITION_DEPTH or not isinstance(node, dict):
        return False
    kind = node.get("kind")
    if kind in LITERALS or kind == "NamedValue":
        return True
    if kind in ("UnaryOp", "Conversion", "SignedConversion"):
        return _simple_rhs(node.get("operand"), depth + 1)
    if kind == "BinaryOp":
        return (_simple_rhs(node.get("left"), depth + 1)
                and _simple_rhs(node.get("right"), depth + 1))
    return False


def _candidate_targets(body: Any, known: set[str]) -> set[str]:
    """Conserver les cibles évidentes même lorsque le bloc est partiel."""
    result: set[str] = set()
    pending = [body]
    seen = 0
    while pending and seen < MAX_PROBE_NODES:
        node = pending.pop()
        seen += 1
        if isinstance(node, list):
            pending.extend(node[:MAX_PROBE_NODES])
        elif isinstance(node, dict):
            if node.get("kind") == "Assignment":
                name = _name(node.get("left"))
                if name in known:
                    result.add(name)
            # Ignore metadata and serialized declaration subgraphs.
            for key, value in node.items():
                if key not in ("type", "definition", "internalSymbol") and isinstance(value, (dict, list)):
                    pending.append(value)
    return result


def build_register_flow(ast: dict[str, Any], *, expected_top: str,
                        index: dict[str, Any] | None = None) -> dict[str, Any]:
    """Énumérer les chemins syntaxiques vers chaque registre always_ff.

    Les branches sont des alternatives syntaxiques, non des contraintes
    satisfiables. La dernière NBA sur un même chemin est notée sans
    déduire sa valeur finale ni sa portée inter-processus.
    """
    structural = index if index is not None else build_index(ast, expected_top=expected_top)
    if structural.get("schema_version") != 1 or structural.get("top") != expected_top:
        raise ValueError("Index RTL v1/top incohérent pour register_flow")
    instances = {x["path"]: x for x in structural["instances"]}
    known_by_path = {p: {port["name"] for port in inst["ports"]}
                     for p, inst in instances.items()}
    for sig in structural["signals"]:
        known_by_path[sig["instance_path"]].add(sig["name"])

    items: list[dict[str, Any]] = []
    stats: dict[str, Any] = {
        "always_ff_seen": 0, "complete_processes": 0,
        "partial_processes": 0, "truncated": False,
    }

    def analyze(path: str, block: dict[str, Any]) -> None:
        if stats["always_ff_seen"] >= MAX_PROCESSES or len(items) >= MAX_TARGETS:
            stats["truncated"] = True
            return
        stats["always_ff_seen"] += 1
        process = f"{path}#ff{stats['always_ff_seen']}"
        known = known_by_path[path]
        source = _source(block)
        body = block.get("body")
        targets = _candidate_targets(body, known)
        if not targets:
            return

        statements_seen = [0]
        order_by_ast_id: dict[int, int] = {}
        events: list[dict[str, Any]] = []
        event_seen = [False]
        State = tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]

        def walk(node: Any, states: list[State], depth: int = 0,
                 inside_timed: bool = False) -> list[State]:
            statements_seen[0] += 1
            if statements_seen[0] > MAX_STATEMENTS or depth > MAX_DEPTH:
                raise _Unknown("statement_limit")
            if len(states) > MAX_PATHS:
                raise _Unknown("path_limit")
            if node is None:
                return states
            if not isinstance(node, dict):
                raise _Unknown("statement_malformed")
            kind = node.get("kind")
            if kind in ("Empty", "EmptyStatement"):
                return states
            if kind in ("List", "StatementList", "Block"):
                key = {"List": "list", "StatementList": "statements", "Block": "body"}[kind]
                children = node.get(key)
                if isinstance(children, dict):
                    # slang may serialize a one-statement List/Block as an AST
                    # object instead of an array, including for real counters.
                    return walk(children, states, depth + 1, inside_timed)
                if not isinstance(children, list):
                    raise _Unknown("statement_list_malformed")
                for child in children:
                    states = walk(child, states, depth + 1, inside_timed)
                return states
            if kind == "Timed":
                if depth > 1 or inside_timed or event_seen[0]:
                    raise _Unknown("nested_or_ambiguous_timing")
                event_seen[0] = True
                timing = node.get("timing")
                if not isinstance(timing, dict) or timing.get("kind") != "EventList":
                    raise _Unknown("unsupported_timing")
                raw = timing.get("events")
                if not isinstance(raw, list) or not 1 <= len(raw) <= 16:
                    raise _Unknown("invalid_event_list")
                for event in raw:
                    if not isinstance(event, dict) or event.get("kind") != "SignalEvent":
                        raise _Unknown("unsupported_event")
                    edge, name = event.get("edge"), _name(event.get("expr"))
                    if edge not in ("PosEdge", "NegEdge") or name not in known:
                        raise _Unknown("unsupported_event_expression")
                    events.append({"edge": edge, "signal": f"{path}.{name}"})
                return walk(node.get("stmt"), states, depth + 1, True)
            if kind == "Conditional":
                conditions = node.get("conditions")
                if not (isinstance(conditions, list) and len(conditions) == 1
                        and isinstance(conditions[0], dict)):
                    raise _Unknown("unsupported_conditional")
                cond = _condition(conditions[0].get("expr"), path, known, [0])
                fork: list[State] = []
                for branch, field in (("then", "ifTrue"), ("else", "ifFalse")):
                    expanded: list[State] = []
                    for guards, writes in states:
                        if len(guards) >= MAX_GUARDS:
                            raise _Unknown("guards_limit")
                        expanded.append((
                            guards + ({"kind": "if", "branch": branch, "condition": cond},),
                            writes,
                        ))
                    fork.extend(walk(node.get(field), expanded, depth + 1,
                                     inside_timed))
                    if len(fork) > MAX_PATHS:
                        raise _Unknown("path_limit")
                return fork
            if kind == "ExpressionStatement":
                assignment = node.get("expr")
                if not isinstance(assignment, dict) or assignment.get("kind") != "Assignment":
                    raise _Unknown("unsupported_expression_statement")
                target = _name(assignment.get("left"))
                if target not in known or assignment.get("isNonBlocking") is not True:
                    raise _Unknown("unsupported_assignment_target_or_kind")
                if not _simple_rhs(assignment.get("right")):
                    raise _Unknown("rhs_may_have_unsupported_side_effect")
                marker = id(assignment)
                if marker not in order_by_ast_id:
                    order_by_ast_id[marker] = len(order_by_ast_id) + 1
                write = {
                    "order": order_by_ast_id[marker],
                    "source": _source(assignment) or _source(node),
                }
                out: list[State] = []
                for guards, writes in states:
                    if len(writes) >= MAX_WRITES_PER_PATH:
                        raise _Unknown("writes_limit")
                    out.append((guards, writes + ({"target": f"{path}.{target}", **write},)))
                return out
            raise _Unknown("unsupported_statement_" + str(kind)[:64])

        if not isinstance(body, dict):
            failure = "missing_procedural_body"
            states = []
        else:
            try:
                states = walk(body, [((), ())])
                if not event_seen[0] or not events:
                    raise _Unknown("missing_event_list")
                failure = None
            except _Unknown as exc:
                states = []
                failure = str(exc)

        if failure is not None:
            stats["partial_processes"] += 1
            for name in sorted(targets):
                if len(items) >= MAX_TARGETS:
                    stats["truncated"] = True
                    return
                items.append({
                    "target": f"{path}.{name}", "process": process,
                    "coverage": "partial", "reason": failure,
                    "source": source, "events": events,
                    "hold_candidate": "unknown", "paths": [],
                })
            return

        stats["complete_processes"] += 1
        for name in sorted(targets):
            if len(items) >= MAX_TARGETS:
                stats["truncated"] = True
                return
            target = f"{path}.{name}"
            paths: list[dict[str, Any]] = []
            for guards, writes in states:
                active = [{"order": w["order"], "source": w["source"]}
                          for w in writes if w["target"] == target]
                paths.append({
                    "guards": list(guards),
                    "write_count": len(active),
                    "writes_in_execution_order": active,
                    "last_nonblocking_write": active[-1] if active else None,
                })
            items.append({
                "target": target,
                "process": process,
                "coverage": "syntactic_paths_supported",
                "source": source,
                "events": events,
                "path_count": len(paths),
                "hold_candidate": ("syntactic_unwritten_path"
                                   if any(p["write_count"] == 0 for p in paths)
                                   else "no_unwritten_path_in_enumerated_paths"),
                "same_path_multiple_nba": any(p["write_count"] > 1 for p in paths),
                "paths": paths,
            })

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
            elif kind == "Instance":
                name = node.get("name")
                if not isinstance(name, str):
                    raise ValueError("Instance non nommée dans register_flow")
                path = f"{parent}.{name}" if parent else name
                if path not in instances:
                    raise ValueError("Instance non indexée dans register_flow")
                body = node.get("body")
                if not isinstance(body, dict):
                    raise ValueError("Instance sans corps dans register_flow")
                visit(body.get("members"), path)
            elif kind == "ProceduralBlock" and parent is not None:
                if node.get("procedureKind") == "AlwaysFF":
                    analyze(parent, node)

    visit(ast.get("design", {}).get("members"))
    items.sort(key=lambda item: (item["target"], item["process"]))
    return {
        "schema_version": FLOW_SCHEMA_VERSION,
        "scope": "always_ff_syntactic_paths_only",
        "items": items,
        "counts": {"captured": len(items), **stats},
        "caveat": (
            "Chemins de contrôle syntaxiques, sans test de faisabilité des gardes. "
            "Un chemin sans écriture est un candidat de maintien local au processus, "
            "pas une preuve de maintien du signal. La dernière NBA est un ordre "
            "local au même chemin, sans simulation, X/Z ni analyse inter-processus. "
            "Les procédures partielles ne permettent aucune conclusion."
        ),
    }

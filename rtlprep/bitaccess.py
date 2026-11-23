"""Accès RTL aux bits : segments syntaxiques de RHS issus de l'AST slang.

Périmètre : assign continus et instructions d'affectation dans les procédures
always_ff / always_comb / always_latch / always, uniquement pour des sélections
et concaténations de segments de largeur connue. Les gardes et événements
sont des métadonnées syntaxiques, jamais des preuves temporelles.
Aucune équivalence, simulation ou preuve de dépendance fonctionnelle.
"""
from __future__ import annotations

import re
from typing import Any

from .index import build_index
from .symbols import SignalResolver

BIT_ACCESS_SCHEMA_VERSION = 1
MAX_RECORDS = 2000
MAX_SEGMENTS = 32
MAX_DEPTH = 12
MAX_WIDTH = 1024
MAX_NODES = 256
MAX_PROC_DEPTH = 40
MAX_PROC_STATEMENTS = 8192
MAX_PROC_GUARDS = 16
MAX_PROC_EVENTS = 16


class _Partial(Exception):
    """Une structure indéterminée interdit toute correspondance bit-à-bit."""


def _location(node: Any) -> dict[str, Any] | None:
    if not isinstance(node, dict):
        return None
    filename = node.get("source_file_start") or node.get("source_file")
    line = node.get("source_line_start") or node.get("source_line")
    if not isinstance(filename, str) or not filename:
        return None
    return {"file": filename, "line": line if type(line) is int and line > 0 else None}


def _number(value: Any) -> int | None:
    """Lire un nombre fourni par slang, jamais du code SystemVerilog brut."""
    if type(value) is int:
        return value if 0 <= value <= MAX_WIDTH else None
    if not isinstance(value, str) or len(value) > 64:
        return None
    raw = value.strip().replace("_", "")
    if raw.isdecimal():
        result = int(raw)
        return result if result <= MAX_WIDTH else None
    matched = re.fullmatch(r"(?:(\d+))?'[sS]?([bBoOdDhH])([0-9a-fA-F]+)", raw)
    if not matched:
        return None
    declared_width, base, digits = matched.groups()
    if declared_width and int(declared_width) > MAX_WIDTH:
        return None
    radix = {"b": 2, "o": 8, "d": 10, "h": 16}[base.lower()]
    try:
        result = int(digits, radix)
    except ValueError:
        return None
    return result if 0 <= result <= MAX_WIDTH else None


def _constant(node: Any, depth: int = 0, *,
              known: set[str] | None = None) -> int | None:
    """Decode bounded compile-time positions; reject runtime-signal names.

    slang generates constant-valued n/l indices and folded Multiply/Add for
    generate loops. A 'constant' tag on a known runtime signal is not proof.
    These values are indices only, never evaluated RTL data values.
    """
    if not isinstance(node, dict) or depth > 8:
        return None
    kind = node.get("kind")
    if kind == "IntegerLiteral":
        return _number(node.get("value"))
    if kind == "NamedValue" and "constant" in node:
        if known is not None and _name(node) in known:
            return None
        return _number(node.get("constant"))
    if kind in ("Conversion", "SignedConversion"):
        return _constant(node.get("operand"), depth + 1, known=known)
    if kind == "BinaryOp" and node.get("op") in ("Add", "Subtract", "Multiply"):
        left = _constant(node.get("left"), depth + 1, known=known)
        right = _constant(node.get("right"), depth + 1, known=known)
        if left is None or right is None:
            return None
        op = node["op"]
        val = (left + right if op == "Add"
               else left - right if op == "Subtract" else left * right)
        return val if 0 <= val <= MAX_WIDTH else None
    return None


def _name(node: Any) -> str | None:
    if not isinstance(node, dict) or node.get("kind") != "NamedValue":
        return None
    symbol = node.get("symbol")
    if not isinstance(symbol, str):
        return None
    parts = symbol.split(maxsplit=1)
    return parts[1] if len(parts) == 2 and parts[1] else None


def _base(node: Any, known: set[str], path: str,
          resolver: SignalResolver | None = None) -> str:
    name = _name(node)
    if name not in known:
        raise _Partial("unknown_or_non_signal_base")
    full = f"{path}.{name}"
    if resolver is not None and resolver.resolve(path, node) != full:
        # Never map a shadowed / wrong-ID AST reference by name alone.
        raise _Partial("unresolved_symbol_identity")
    return full


def _selection(node: Any, known: set[str], path: str,
               resolver: SignalResolver | None = None
               ) -> tuple[str, dict[str, Any], int | None]:
    """Trace nested static selectors without flattening array dimensions.

    A nested index such as arr[0][3] is not a flat bit index. Its final
    selected width is known, but it has no justified target_lsb/target_msb.
    """
    if not isinstance(node, dict):
        raise _Partial("malformed_selection")
    current = node
    reversed_parts: list[dict[str, Any]] = []
    widths: list[int] = []
    for _ in range(MAX_DEPTH):
        kind = current.get("kind")
        if kind == "NamedValue":
            base = _base(current, known, path, resolver)
            if not reversed_parts:
                return base, {"kind": "whole"}, None
            parts = list(reversed(reversed_parts))
            width = widths[0]  # outermost / final selector determines width
            if len(parts) == 1:
                return base, parts[0], width
            return base, {"kind": "nested", "selectors": parts}, width
        if kind == "ElementSelect":
            index = _constant(current.get("selector"), known=known)
            if index is None:
                raise _Partial("dynamic_or_unknown_index")
            reversed_parts.append({"kind": "bit", "index": index})
            widths.append(1)
        elif kind == "RangeSelect":
            msb = _constant(current.get("left"), known=known)
            lsb = _constant(current.get("right"), known=known)
            if msb is None or lsb is None:
                raise _Partial("dynamic_or_unknown_range")
            if msb < lsb:
                raise _Partial("ascending_or_unsupported_range")
            width = msb - lsb + 1
            if width > MAX_WIDTH:
                raise _Partial("range_too_wide")
            reversed_parts.append({"kind": "range", "msb": msb, "lsb": lsb})
            widths.append(width)
        else:
            raise _Partial("unsupported_selection_" + str(kind)[:48])
        current = current.get("value")
        if not isinstance(current, dict):
            raise _Partial("malformed_selection")
    raise _Partial("selection_depth_exceeded")


def _literal_width(node: dict[str, Any]) -> int | None:
    value = node.get("value")
    if not isinstance(value, str) or len(value) > 96:
        return None
    match = re.fullmatch(r"(\d+)'[sS]?[bBoOdDhH][0-9a-fA-F_xXzZ?]+", value)
    if match:
        width = int(match.group(1))
        return width if 1 <= width <= MAX_WIDTH else None
    return None



def _packed_width(type_string: Any) -> int | None:
    """Width only from slang's explicit one-dimensional scalar/packed type.

    Typedef aliases, arrays and multidimensional types are not flattened.
    No bit-offset is inferred from width alone.
    """
    if not isinstance(type_string, str) or len(type_string) > 96:
        return None
    if type_string in ("logic", "bit"):
        return 1
    match = re.fullmatch(r"(?:logic|bit)\[(\d+):(\d+)\]", type_string)
    if match is None:
        return None
    upper, lower = (int(x) for x in match.groups())
    width = abs(upper - lower) + 1
    return width if 1 <= width <= MAX_WIDTH else None


def _semantic_constant_ids(ast: dict[str, Any]) -> set[tuple[str, str]]:
    """Require exact address + name for Parameter/EnumValue declarations."""
    result: set[tuple[str, str]] = set()

    def visit(obj: Any) -> None:
        if isinstance(obj, list):
            for child in obj:
                visit(child)
        elif isinstance(obj, dict):
            if (obj.get("kind") in ("Parameter", "EnumValue")
                    and obj.get("addr") is not None
                    and isinstance(obj.get("name"), str)):
                result.add((str(obj["addr"]), obj["name"]))
            for key, value in obj.items():
                if key not in ("definition", "internalSymbol", "type") and isinstance(value, (list, dict)):
                    visit(value)

    visit(ast.get("design", {}))
    return result


def _segments(node: Any, known: set[str], path: str, depth: int = 0,
              resolver: SignalResolver | None = None,
              constant_ids: frozenset[tuple[str, str]] = frozenset()
              ) -> list[tuple[str | None, dict[str, Any], int]]:
    if depth > MAX_DEPTH or not isinstance(node, dict):
        raise _Partial("rhs_depth_or_shape")
    kind = node.get("kind")
    if kind in ("RangeSelect", "ElementSelect"):
        source, selected, width = _selection(node, known, path, resolver)
        assert width is not None
        return [(source, selected, width)]
    if kind == "Concatenation":
        operands = node.get("operands")
        if not isinstance(operands, list) or not 1 <= len(operands) <= MAX_SEGMENTS:
            raise _Partial("malformed_or_large_concatenation")
        output: list[tuple[str | None, dict[str, Any], int]] = []
        for operand in operands:
            output.extend(_segments(operand, known, path, depth + 1, resolver, constant_ids))
            if len(output) > MAX_SEGMENTS:
                raise _Partial("too_many_segments")
        return output
    if kind == "IntegerLiteral":
        width = _literal_width(node)
        if width is None:
            raise _Partial("literal_width_unknown")
        return [(None, {"kind": "literal", "width": width}, width)]
    if kind == "NamedValue":
        # A runtime source's 'constant' field does not prove it is a
        # compile-time value. Require an exact semantic declaration.
        width = _packed_width(node.get("type"))
        if width is None:
            raise _Partial("source_width_unknown")
        raw = node.get("symbol")
        parts = raw.split(maxsplit=1) if isinstance(raw, str) else []
        if len(parts) != 2:
            raise _Partial("unresolved_symbol_identity")
        if (parts[0], parts[1]) in constant_ids:
            return [(None, {"kind": "constant_reference", "width": width}, width)]
        source = _base(node, known, path, resolver)
        # This is deliberately opaque: no source sub-lane offsets inferred.
        return [(source, {"kind": "whole"}, width)]
    if kind == "Replication":
        count_node, concat = node.get("count"), node.get("concat")
        if (not isinstance(count_node, dict)
                or count_node.get("kind") != "IntegerLiteral"
                or not isinstance(concat, dict)
                or concat.get("kind") != "Concatenation"):
            raise _Partial("replication_count_or_concat_unproven")
        count = _number(count_node.get("value"))
        if count is None or count < 1 or count > MAX_SEGMENTS:
            raise _Partial("replication_count_out_of_bounds")
        unit = _segments(concat, known, path, depth + 1,
                         resolver, constant_ids)
        if not unit or len(unit) * count > MAX_SEGMENTS:
            raise _Partial("replication_segments_exceed_limit")
        if sum(part[2] for part in unit) * count > MAX_WIDTH:
            raise _Partial("replication_width_exceed_limit")
        return [(source, dict(selection), width)
                for _ in range(count)
                for source, selection, width in unit]
    if kind in ("Conversion", "SignedConversion"):
        operand = node.get("operand")
        if not isinstance(operand, dict):
            raise _Partial("conversion_operand_missing")
        dest_width = _packed_width(node.get("type"))
        source_width = _packed_width(operand.get("type"))
        if dest_width is None or dest_width != source_width:
            raise _Partial("conversion_width_unproven_or_changed")
        segments = _segments(operand, known, path, depth + 1,
                             resolver, constant_ids)
        if sum(part[2] for part in segments) != dest_width:
            raise _Partial("conversion_width_mismatch")
        return segments
    raise _Partial("unsupported_rhs_" + str(kind)[:48])


def _contains_selection(node: Any, budget: list[int], depth: int = 0) -> bool:
    budget[0] += 1
    if budget[0] > MAX_NODES or depth > MAX_DEPTH:
        return True  # analyse partielle plutôt qu'ignorance silencieuse
    if not isinstance(node, dict):
        return False
    if node.get("kind") in ("ElementSelect", "RangeSelect", "Concatenation"):
        return True
    for field in ("left", "right", "operand", "value", "operands", "expr",
                  "concat", "count", "selector"):
        child = node.get(field)
        if isinstance(child, list):
            for item in child:
                if _contains_selection(item, budget, depth + 1):
                    return True
        elif isinstance(child, dict) and _contains_selection(child, budget, depth + 1):
            return True
    return False


def _target_name(node: Any, known: set[str], path: str,
                 resolver: SignalResolver | None = None) -> str | None:
    current = node
    for _ in range(MAX_DEPTH):
        if not isinstance(current, dict):
            return None
        if current.get("kind") == "NamedValue":
            try:
                return _base(current, known, path, resolver)
            except _Partial:
                return None
        if current.get("kind") not in ("ElementSelect", "RangeSelect"):
            return None
        current = current.get("value")
    return None


def build_bit_access_index(ast: dict[str, Any], *, expected_top: str,
                           index: dict[str, Any] | None = None) -> dict[str, Any]:
    """Décrire les positions sur la RHS, et sur la LHS si explicitement sélectionnée."""
    structural = index if index is not None else build_index(ast, expected_top=expected_top)
    if structural.get("schema_version") != 1 or structural.get("top") != expected_top:
        raise ValueError("Index RTL v1/top incompatible avec bit_accesses")
    instances = {x["path"]: x for x in structural["instances"]}
    known = {path: {port["name"] for port in inst["ports"]}
             for path, inst in instances.items()}
    # Les accès bit-à-bit de scopes generate restent hors du périmètre :
    # ne pas les fusionner silencieusement avec les signaux directs.
    for signal in structural["signals"]:
        if not signal.get("scope"):
            known[signal["instance_path"]].add(signal["name"])

    resolver = SignalResolver(ast, structural)
    constant_ids = frozenset(_semantic_constant_ids(ast))

    rows: list[dict[str, Any]] = []
    counts = {"assignments_seen": 0, "precise": 0, "partial": 0,
              "unsupported_targets": 0, "truncated": False,
              "procedural_blocks_visited": 0, "procedural_blocks_skipped": 0,
              "unsupported_statements": 0}
    statement_budget = [0]

    def extract(path: str, node: Any, *,
                procedure_kind: str | None = None,
                guards: tuple[dict[str, Any], ...] = (),
                events: tuple[dict[str, str], ...] = (),
                timing_scope: str = "not_procedural",
                context_partial: bool = False) -> None:
        counts["assignments_seen"] += 1
        if not isinstance(node, dict) or node.get("kind") != "Assignment":
            return
        lhs, rhs = node.get("left"), node.get("right")
        if not (_contains_selection(lhs, [0]) or _contains_selection(rhs, [0])):
            return
        target = _target_name(lhs, known[path], path, resolver)
        if target is None:
            counts["unsupported_targets"] += 1
            return
        if len(rows) >= MAX_RECORDS:
            counts["truncated"] = True
            return
        item: dict[str, Any] = {
            "target": target, "source": _location(node),
            "coverage": "partial", "target_selection": None,
            "rhs_width": None, "source_segments": [],
        }
        if procedure_kind is not None:
            nonblocking = node.get("isNonBlocking")
            if type(nonblocking) is not bool:
                context_partial = True
            item.update({
                "assignment_kind": "procedural",
                "procedure_kind": procedure_kind,
                "nonblocking": nonblocking if type(nonblocking) is bool else None,
                "guards": list(guards), "events": list(events),
                "timing_scope": timing_scope,
            })
        try:
            dest, select, dest_width = _selection(lhs, known[path], path, resolver)
            assert dest == target
            item["target_selection"] = select
            parts = _segments(rhs, known[path], path, resolver=resolver,
                              constant_ids=constant_ids)
            width = sum(part[2] for part in parts)
            if width > MAX_WIDTH:
                raise _Partial("rhs_too_wide")
            if dest_width is not None and dest_width != width:
                raise _Partial("target_rhs_width_mismatch")
            rhs_lsb = 0
            positioned: list[dict[str, Any]] = []
            for source, selection, span in reversed(parts):
                seg: dict[str, Any] = {
                    "source": source, "selection": selection,
                    "rhs_lsb": rhs_lsb, "rhs_msb": rhs_lsb + span - 1,
                }
                if dest_width is not None and select["kind"] in ("bit", "range"):
                    start = select["lsb"] if select["kind"] == "range" else select["index"]
                    seg["target_lsb"] = start + rhs_lsb
                    seg["target_msb"] = start + rhs_lsb + span - 1
                positioned.append(seg)
                rhs_lsb += span
            item["source_segments"] = list(reversed(positioned))
            item["rhs_width"] = width
            item["coverage"] = (
                "explicit_target_lanes"
                if dest_width is not None and select["kind"] in ("bit", "range")
                else "rhs_lanes_only"
            )
            if context_partial:
                # Position metadata may be syntactically useful, but a
                # malformed/unsupported guard or event cannot be complete.
                item["coverage"] = "partial"
                item["reason"] = "unsupported_procedural_context"
                counts["partial"] += 1
            else:
                counts["precise"] += 1
        except _Partial as exc:
            item["reason"] = str(exc)
            counts["partial"] += 1
        rows.append(item)

    def _timing(path: str, node: Any
                ) -> tuple[tuple[dict[str, str], ...], str, bool]:
        """Capture explicit event identities without inventing sensitivity."""
        if not isinstance(node, dict):
            return (), "unknown_timing", True
        if node.get("kind") == "ImplicitEvent":
            return (), "implicit_not_expanded", False
        if node.get("kind") == "SignalEvent":
            raw = [node]
        elif node.get("kind") == "EventList":
            raw = node.get("events")
        else:
            return (), "unsupported_timing", True
        if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_PROC_EVENTS:
            return (), "unsupported_timing", True
        events: list[dict[str, str]] = []
        for event in raw:
            if not isinstance(event, dict) or event.get("kind") != "SignalEvent":
                return (), "unsupported_timing", True
            edge = event.get("edge")
            signal = resolver.resolve(path, event.get("expr"))
            if edge not in ("PosEdge", "NegEdge") or signal is None:
                return (), "unsupported_timing", True
            events.append({"edge": edge, "signal": signal})
        return tuple(events), "explicit_event_syntax", False

    def statements(path: str, node: Any, *,
                   procedure_kind: str,
                   guards: tuple[dict[str, Any], ...] = (),
                   events: tuple[dict[str, str], ...] = (),
                   timing_scope: str = "no_explicit_timing",
                   partial: bool = False, depth: int = 0) -> None:
        if counts["truncated"]:
            return
        statement_budget[0] += 1
        if statement_budget[0] > MAX_PROC_STATEMENTS or depth > MAX_PROC_DEPTH:
            counts["unsupported_statements"] += 1
            counts["truncated"] = True
            return
        if isinstance(node, list):
            for child in node:
                statements(path, child, procedure_kind=procedure_kind,
                           guards=guards, events=events,
                           timing_scope=timing_scope,
                           partial=partial, depth=depth + 1)
            return
        if not isinstance(node, dict):
            if node is not None:
                counts["unsupported_statements"] += 1
            return
        kind = node.get("kind")
        if kind == "ExpressionStatement":
            assignment = node.get("expr")
            if not isinstance(assignment, dict) or assignment.get("kind") != "Assignment":
                counts["unsupported_statements"] += 1
                return
            extract(path, assignment, procedure_kind=procedure_kind,
                    guards=guards, events=events, timing_scope=timing_scope,
                    context_partial=partial)
            return
        if kind in ("List", "StatementList", "Block"):
            field = {"List": "list", "StatementList": "statements",
                     "Block": "body"}[kind]
            children = node.get(field)
            if not isinstance(children, (dict, list)):
                counts["unsupported_statements"] += 1
                return
            statements(path, children, procedure_kind=procedure_kind,
                       guards=guards, events=events, timing_scope=timing_scope,
                       partial=partial, depth=depth + 1)
            return
        if kind == "Timed":
            timed_events, timing, timing_partial = _timing(path, node.get("timing"))
            if timing_partial:
                counts["unsupported_statements"] += 1
            child = node.get("stmt")
            if not isinstance(child, (list, dict)):
                counts["unsupported_statements"] += 1
                return
            # This index records the syntax of selected lanes. Event lists
            # are not a cycle/latency model and implicit sensitivity is not
            # expanded into hypothetical event dependencies.
            statements(path, child, procedure_kind=procedure_kind,
                       guards=guards, events=events + timed_events,
                       timing_scope=timing, partial=partial or timing_partial,
                       depth=depth + 1)
            return
        if kind == "Conditional":
            conds = node.get("conditions")
            valid = (isinstance(conds, list) and len(conds) == 1
                     and isinstance(conds[0], dict)
                     and set(conds[0]) == {"expr"}
                     and isinstance(conds[0]["expr"], dict)
                     and isinstance(node.get("ifTrue"), (dict, list)))
            if not valid:
                counts["unsupported_statements"] += 1
            for branch, name in (("then", "ifTrue"), ("else", "ifFalse")):
                child = node.get(name)
                if child is None:
                    continue
                if not isinstance(child, (dict, list)):
                    counts["unsupported_statements"] += 1
                    continue
                spec = ({"kind": "if", "branch": branch,
                         "condition_ast_kind": str(conds[0]["expr"].get("kind", "unknown"))[:64]}
                        if valid else {"kind": "unsupported_guard", "branch": branch})
                if len(guards) >= MAX_PROC_GUARDS:
                    counts["unsupported_statements"] += 1
                statements(path, child, procedure_kind=procedure_kind,
                           guards=guards + (spec,) if len(guards) < MAX_PROC_GUARDS else guards,
                           events=events, timing_scope=timing_scope,
                           partial=partial or not valid or len(guards) >= MAX_PROC_GUARDS,
                           depth=depth + 1)
            return
        if kind == "Case":
            mode = node.get("condition")
            selector = node.get("expr")
            items = node.get("items")
            valid = (mode == "Normal" and isinstance(selector, dict)
                     and isinstance(items, list))
            if not valid:
                counts["unsupported_statements"] += 1
            for entry in items if isinstance(items, list) else []:
                if not isinstance(entry, dict):
                    counts["unsupported_statements"] += 1
                    continue
                labels = entry.get("expressions")
                valid_entry = valid and isinstance(labels, list)
                spec = {
                    "kind": "case", "branch": "item",
                    "selector_ast_kind": str(selector.get("kind", "unknown"))[:64]
                                         if isinstance(selector, dict) else "unknown",
                    "label_count": len(labels) if isinstance(labels, list) else 0,
                } if valid_entry else {"kind": "unsupported_guard", "branch": "case_item"}
                child = entry.get("stmt")
                if isinstance(child, (list, dict)):
                    statements(path, child, procedure_kind=procedure_kind,
                               guards=guards + (spec,) if len(guards) < MAX_PROC_GUARDS else guards,
                               events=events, timing_scope=timing_scope,
                               partial=partial or not valid_entry or not labels
                                       or len(guards) >= MAX_PROC_GUARDS, depth=depth + 1)
                elif child is not None:
                    counts["unsupported_statements"] += 1
            default = node.get("defaultCase")
            if default is not None:
                if isinstance(default, (dict, list)):
                    spec = {"kind": "case", "branch": "default",
                            "selector_ast_kind": str(selector.get("kind", "unknown"))[:64]
                                                 if isinstance(selector, dict) else "unknown",
                            "label_count": 0} if valid else {"kind": "unsupported_guard",
                                                            "branch": "case_default"}
                    statements(path, default, procedure_kind=procedure_kind,
                               guards=guards + (spec,) if len(guards) < MAX_PROC_GUARDS else guards,
                               events=events, timing_scope=timing_scope,
                               partial=partial or not valid or len(guards) >= MAX_PROC_GUARDS,
                               depth=depth + 1)
                else:
                    counts["unsupported_statements"] += 1
            return
        if kind not in ("Empty", "EmptyStatement"):
            # Loops, task calls and opaque statement kinds are NOT silently
            # analyzed by descending through their children.
            counts["unsupported_statements"] += 1

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
                    raise ValueError("Instance non nommée dans bit_accesses")
                path = f"{parent}.{name}" if parent else name
                if path not in instances:
                    raise ValueError("Instance non indexée dans bit_accesses")
                body = node.get("body")
                if not isinstance(body, dict):
                    raise ValueError("Instance sans corps dans bit_accesses")
                visit(body.get("members"), path)
            elif kind == "ContinuousAssign" and parent is not None:
                extract(parent, node.get("assignment"))
            elif kind == "ProceduralBlock" and parent is not None:
                procedure_kind = node.get("procedureKind")
                if procedure_kind in ("AlwaysFF", "AlwaysComb", "AlwaysLatch", "Always"):
                    counts["procedural_blocks_visited"] += 1
                    statements(parent, node.get("body"),
                               procedure_kind=procedure_kind)
                else:
                    counts["procedural_blocks_skipped"] += 1

    visit(ast.get("design", {}).get("members"))
    rows.sort(key=lambda item: (item["target"], str(item.get("source"))))
    return {
        "schema_version": BIT_ACCESS_SCHEMA_VERSION,
        "scope": "continuous_and_supported_procedural_static_select_concat",
        "items": rows,
        "counts": {"captured": len(rows), **counts},
        "caveat": (
            "Correspondances syntaxiques des positions de la RHS. "
            "Sans largeur élaborée du signal cible entier, ses bits de sortie "
            "ne sont pas inférés. Types scalaires/packed unidimensionnels "
            "explicitement reconnus et constantes Parameter/EnumValue "
            "validées par identité et nom ; source entière opaque sans "
            "sous-indices garantis. Réplications de nombre littéral "
            "bornées ; conversions uniquement si largeur inchangée et "
            "explicitement prouvée. Alias de types, indices dynamiques, "
            "opérations arithmétiques/non positionnelles restent partiels ; "
            "sélections imbriquées sans indices cibles aplatis. "
            "Aucune preuve fonctionnelle. "
            "Les affectations procédurales enregistrent le type de processus, "
            "les gardes de branches syntaxiques et les événements explicites "
            "sans inférer la priorité, la latence ou la sémantique des NBA. "
            "Les sensibilité implicites ne sont pas reconstruites ; les "
            "instructions opaques sont signalées comme exclues. "
            "Ne couvre pas les connexions de ports ni les champs MemberAccess "
            "sans offsets prouvés."
        ),
    }

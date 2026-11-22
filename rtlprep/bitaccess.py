"""Accès RTL aux bits : segments syntaxiques de RHS issus de l'AST slang.

Périmètre volontairement restreint : assign continus, sélections statiques et
concaténations de segments de largeur connue. Aucune équivalence, simulation,
propagation de constantes ou preuve de dépendance fonctionnelle.
"""
from __future__ import annotations

import re
from typing import Any

from .index import build_index

BIT_ACCESS_SCHEMA_VERSION = 1
MAX_RECORDS = 2000
MAX_SEGMENTS = 32
MAX_DEPTH = 12
MAX_WIDTH = 1024
MAX_NODES = 256


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


def _constant(node: Any, depth: int = 0) -> int | None:
    if not isinstance(node, dict) or depth > 5:
        return None
    kind = node.get("kind")
    if kind == "IntegerLiteral":
        return _number(node.get("value"))
    if kind == "NamedValue" and "constant" in node:
        return _number(node.get("constant"))
    if kind in ("Conversion", "SignedConversion"):
        return _constant(node.get("operand"), depth + 1)
    if kind == "BinaryOp" and node.get("op") in ("Add", "Subtract"):
        left = _constant(node.get("left"), depth + 1)
        right = _constant(node.get("right"), depth + 1)
        if left is None or right is None:
            return None
        val = left + right if node["op"] == "Add" else left - right
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


def _base(node: Any, known: set[str], path: str) -> str:
    name = _name(node)
    if name not in known:
        raise _Partial("unknown_or_non_signal_base")
    return f"{path}.{name}"


def _selection(node: Any, known: set[str], path: str) -> tuple[str, dict[str, Any], int | None]:
    if not isinstance(node, dict):
        raise _Partial("malformed_selection")
    kind = node.get("kind")
    if kind == "NamedValue":
        return _base(node, known, path), {"kind": "whole"}, None
    if kind == "ElementSelect":
        source = _base(node.get("value"), known, path)
        index = _constant(node.get("selector"))
        if index is None:
            raise _Partial("dynamic_or_unknown_index")
        return source, {"kind": "bit", "index": index}, 1
    if kind == "RangeSelect":
        source = _base(node.get("value"), known, path)
        msb = _constant(node.get("left"))
        lsb = _constant(node.get("right"))
        if msb is None or lsb is None:
            raise _Partial("dynamic_or_unknown_range")
        if msb < lsb:
            raise _Partial("ascending_or_unsupported_range")
        width = msb - lsb + 1
        if width > MAX_WIDTH:
            raise _Partial("range_too_wide")
        return source, {"kind": "range", "msb": msb, "lsb": lsb}, width
    raise _Partial("unsupported_selection_" + str(kind)[:48])


def _literal_width(node: dict[str, Any]) -> int | None:
    value = node.get("value")
    if not isinstance(value, str) or len(value) > 96:
        return None
    match = re.fullmatch(r"(\d+)'[sS]?[bBoOdDhH][0-9a-fA-F_xXzZ?]+", value)
    if match:
        width = int(match.group(1))
        return width if 1 <= width <= MAX_WIDTH else None
    return None


def _segments(node: Any, known: set[str], path: str, depth: int = 0
              ) -> list[tuple[str | None, dict[str, Any], int]]:
    if depth > MAX_DEPTH or not isinstance(node, dict):
        raise _Partial("rhs_depth_or_shape")
    kind = node.get("kind")
    if kind in ("RangeSelect", "ElementSelect"):
        source, selected, width = _selection(node, known, path)
        assert width is not None
        return [(source, selected, width)]
    if kind == "Concatenation":
        operands = node.get("operands")
        if not isinstance(operands, list) or not 1 <= len(operands) <= MAX_SEGMENTS:
            raise _Partial("malformed_or_large_concatenation")
        output: list[tuple[str | None, dict[str, Any], int]] = []
        for operand in operands:
            output.extend(_segments(operand, known, path, depth + 1))
            if len(output) > MAX_SEGMENTS:
                raise _Partial("too_many_segments")
        return output
    if kind == "IntegerLiteral":
        width = _literal_width(node)
        if width is None:
            raise _Partial("literal_width_unknown")
        return [(None, {"kind": "literal", "width": width}, width)]
    # Un signal entier ou une conversion peut changer la largeur : ne pas
    # inventer de position dans la concaténation sans largeur élaborée.
    if kind == "NamedValue":
        raise _Partial("source_width_unknown")
    raise _Partial("unsupported_rhs_" + str(kind)[:48])


def _contains_selection(node: Any, budget: list[int], depth: int = 0) -> bool:
    budget[0] += 1
    if budget[0] > MAX_NODES or depth > MAX_DEPTH:
        return True  # analyse partielle plutôt qu'ignorance silencieuse
    if not isinstance(node, dict):
        return False
    if node.get("kind") in ("ElementSelect", "RangeSelect", "Concatenation"):
        return True
    for field in ("left", "right", "operand", "value", "operands", "expr"):
        child = node.get(field)
        if isinstance(child, list):
            for item in child:
                if _contains_selection(item, budget, depth + 1):
                    return True
        elif isinstance(child, dict) and _contains_selection(child, budget, depth + 1):
            return True
    return False


def _target_name(node: Any, known: set[str], path: str) -> str | None:
    current = node
    for _ in range(4):
        if not isinstance(current, dict):
            return None
        if current.get("kind") == "NamedValue":
            name = _name(current)
            return f"{path}.{name}" if name in known else None
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
    for signal in structural["signals"]:
        known[signal["instance_path"]].add(signal["name"])

    rows: list[dict[str, Any]] = []
    counts = {"assignments_seen": 0, "precise": 0, "partial": 0,
              "unsupported_targets": 0, "truncated": False}

    def extract(path: str, node: Any) -> None:
        counts["assignments_seen"] += 1
        if not isinstance(node, dict) or node.get("kind") != "Assignment":
            return
        lhs, rhs = node.get("left"), node.get("right")
        if not (_contains_selection(lhs, [0]) or _contains_selection(rhs, [0])):
            return
        target = _target_name(lhs, known[path], path)
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
        try:
            dest, select, dest_width = _selection(lhs, known[path], path)
            assert dest == target
            item["target_selection"] = select
            parts = _segments(rhs, known[path], path)
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
                if dest_width is not None:
                    start = select["lsb"] if select["kind"] == "range" else select["index"]
                    seg["target_lsb"] = start + rhs_lsb
                    seg["target_msb"] = start + rhs_lsb + span - 1
                positioned.append(seg)
                rhs_lsb += span
            item["source_segments"] = list(reversed(positioned))
            item["rhs_width"] = width
            item["coverage"] = ("explicit_target_lanes" if dest_width is not None
                                else "rhs_lanes_only")
            counts["precise"] += 1
        except _Partial as exc:
            item["reason"] = str(exc)
            counts["partial"] += 1
        rows.append(item)

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

    visit(ast.get("design", {}).get("members"))
    rows.sort(key=lambda item: (item["target"], str(item.get("source"))))
    return {
        "schema_version": BIT_ACCESS_SCHEMA_VERSION,
        "scope": "continuous_assign_static_select_concat_only",
        "items": rows,
        "counts": {"captured": len(rows), **counts},
        "caveat": (
            "Correspondances syntaxiques des positions de la RHS. "
            "Sans largeur élaborée du signal cible entier, ses bits de sortie "
            "ne sont pas inférés. Indices dynamiques, opérations arithmétiques "
            "et conversions donnent partial ; aucune preuve fonctionnelle. "
            "Ne couvre pas les procédures, les connexions de ports ni les écritures "
            "dans des processus."
        ),
    }

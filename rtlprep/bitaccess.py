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
from .constant_indices import normalize_positions, scope_constants
from .bit_widths import integral_shape, width as shape_width, resize_parts
from .bit_width_literals import literal_width as elaborated_literal_width, resize_constant_state
from .bitgraph import declared_bounds, selected_bounds, source_positions, expand_assignment

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
              constant_ids: frozenset[tuple[str, str]] = frozenset(),
              width_events: list[dict[str, Any]] | None = None,
              allow_literals: bool = False,
              trial_bounds: dict | None = None
              ) -> list[tuple[str | None, dict[str, Any], int]]:
    if depth > MAX_DEPTH or not isinstance(node, dict):
        raise _Partial("rhs_depth_or_shape")
    kind = node.get("kind")
    if kind in ("RangeSelect", "ElementSelect"):
        source, selected, width = _selection(node, known, path, resolver)
        assert width is not None
        if trial_bounds is not None:
            source_positions(selected,trial_bounds.get(source),width)
        return [(source, selected, width)]
    if kind == "Concatenation":
        operands = node.get("operands")
        if not isinstance(operands, list) or not 1 <= len(operands) <= MAX_SEGMENTS:
            raise _Partial("malformed_or_large_concatenation")
        output: list[tuple[str | None, dict[str, Any], int]] = []
        for operand in operands:
            output.extend(_segments(operand, known, path, depth + 1, resolver, constant_ids, width_events, allow_literals, trial_bounds))
            if len(output) > MAX_SEGMENTS:
                raise _Partial("too_many_segments")
        return output
    if kind == "IntegerLiteral" or (allow_literals and kind == "UnbasedUnsizedIntegerLiteral"):
        width = _literal_width(node) if kind == "IntegerLiteral" else None
        if width is None and allow_literals and width_events is not None:
            width=elaborated_literal_width(node)
            if width is not None:
                width_events.append({"mode":"elaborated_literal","destination_width":width,
                                     "literal_kind":kind})
        if width is None:
            raise _Partial("literal_width_unknown")
        return [(None, {"kind": "literal", "width": width}, width)]
    if kind == "NamedValue":
        # A runtime source's 'constant' field does not prove it is a
        # compile-time value. Require an exact semantic declaration.
        width = _packed_width(node.get("type"))
        if width is None and allow_literals and width_events is not None:
            shape=integral_shape(node.get("type"))
            if shape is not None:
                width=shape_width(shape)
                width_events.append({"mode":"explicit_source_width","source_width":width})
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
        if trial_bounds is not None:
            source_positions({"kind":"whole"},trial_bounds.get(source),width)
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
                         resolver, constant_ids, width_events, allow_literals, trial_bounds)
        if not unit or len(unit) * count > MAX_SEGMENTS:
            raise _Partial("replication_segments_exceed_limit")
        if sum(part[2] for part in unit) * count > MAX_WIDTH:
            raise _Partial("replication_width_exceed_limit")
        return [(source, dict(selection), width)
                for _ in range(count)
                for source, selection, width in unit]
    if kind == "UnaryOp":
        # Slang v12.1: ~x has op=BitwiseNot. It preserves each input
        # position but inverts its value. This is NOT a direct copy.
        # !x, reductions, +/- and any future unary operators do not
        # establish one-to-one bit positions, even when widths agree.
        if node.get("op") != "BitwiseNot":
            raise _Partial("unsupported_rhs_UnaryOp")
        operand = node.get("operand")
        if not isinstance(operand, dict):
            raise _Partial("bitwise_not_operand_missing")
        output_width = _packed_width(node.get("type"))
        input_width = _packed_width(operand.get("type"))
        if output_width is None or input_width is None or output_width != input_width:
            raise _Partial("bitwise_not_width_unproven_or_changed")
        parts = _segments(operand, known, path, depth + 1,
                          resolver, constant_ids, width_events, allow_literals, trial_bounds)
        if sum(part[2] for part in parts) != output_width:
            raise _Partial("bitwise_not_segment_width_mismatch")
        # Do not guess how nested transforms compose or simplify.
        if any("_value_transform" in selection
               for _, selection, _ in parts):
            raise _Partial("nested_value_transforms_unmodeled")
        return [(source, {**selection, "_value_transform": "bitwise_not"}, width)
                for source, selection, width in parts]
    if kind in ("Conversion", "SignedConversion"):
        operand = node.get("operand")
        if not isinstance(operand, dict):
            raise _Partial("conversion_operand_missing")
        dest_width = _packed_width(node.get("type"))
        source_width = _packed_width(operand.get("type"))
        if dest_width is not None and dest_width == source_width:
            segments = _segments(operand, known, path, depth + 1,
                                 resolver, constant_ids, width_events, allow_literals, trial_bounds)
            if sum(part[2] for part in segments) != dest_width:
                raise _Partial("conversion_width_mismatch")
            return segments
        if width_events is None or kind != "Conversion":
            raise _Partial("conversion_width_unproven_or_changed")
        a=integral_shape(operand.get("type"))
        b=integral_shape(node.get("type"))
        if a is None or b is None:
            raise _Partial("conversion_width_unproven_or_changed")
        # Only this conversion path extends the recognized whole-signal
        # type set. Keep the original row eligibility and legacy parser.
        if operand.get("kind") == "NamedValue":
            raw=operand.get("symbol")
            tokens=raw.split(maxsplit=1) if isinstance(raw,str) else []
            if len(tokens)!=2:
                raise _Partial("unresolved_symbol_identity")
            n=shape_width(a)
            if tuple(tokens) in constant_ids:
                segments=[(None,{"kind":"constant_reference","width":n},n)]
            else:
                source=_base(operand,known,path,resolver)
                if trial_bounds is not None:
                    source_positions({"kind":"whole"},trial_bounds.get(source),n)
                segments=[(source,{"kind":"whole"},n)]
        else:
            segments=_segments(operand,known,path,depth+1,resolver,constant_ids,width_events,allow_literals,trial_bounds)
        try:
            result,mode=(resize_constant_state(segments,a,b) if allow_literals
                         else resize_parts(segments,a,b))
        except ValueError as exc:
            raise _Partial(str(exc)) from exc
        width_events.append({"mode":mode,"source_width":shape_width(a),
                             "destination_width":shape_width(b),
                             "source_signed":a[2],"destination_signed":b[2]})
        return result
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


def _graph_literal_position(node: Any) -> bool:
    """Strict nonnegative direct literal; no conversion/overflow guessing."""
    if not isinstance(node, dict) or node.get("kind") != "IntegerLiteral":
        return False
    raw = node.get("value")
    value = _number(raw)
    if value is None:
        return False
    if type(raw) is int or (isinstance(raw, str) and raw.isdecimal()):
        return True
    if not isinstance(raw, str):
        return False
    match = re.fullmatch(r"(\d+)'([sS]?)[bBoOdDhH][0-9a-fA-F_]+", raw)
    if not match:
        return False
    width = int(match.group(1))
    return 1 <= width <= MAX_WIDTH and value < (1 << (width - bool(match.group(2))))


def _bit_graph_positions_valid(node: Any, depth: int = 0,
                               budget: list[int] | None = None, *,
                               allow_literals: bool = False) -> bool:
    """Stricter gate for bit graph than the legacy position metadata.

    In particular an indexed part select's right operand is a width,
    not an endpoint. Reject nested/dynamic selections and nonliteral
    positions rather than applying legacy approximations.
    """
    if budget is None:
        budget = [MAX_NODES]
    budget[0] -= 1
    if budget[0] < 0 or depth > MAX_DEPTH or not isinstance(node, dict):
        return False
    kind = node.get("kind")
    if kind in ("NamedValue", "IntegerLiteral"):
        return True
    if allow_literals and kind == "UnbasedUnsizedIntegerLiteral":
        return elaborated_literal_width(node) is not None
    if kind in ("ElementSelect", "RangeSelect"):
        base = node.get("value")
        if not isinstance(base, dict) or base.get("kind") != "NamedValue":
            return False
        if kind == "ElementSelect":
            return _graph_literal_position(node.get("selector"))
        return (node.get("selectionKind") == "Simple"
                and _graph_literal_position(node.get("left"))
                and _graph_literal_position(node.get("right")))
    if kind == "Concatenation":
        parts = node.get("operands")
        return (isinstance(parts, list) and 1 <= len(parts) <= MAX_SEGMENTS
                and all(_bit_graph_positions_valid(p, depth + 1, budget, allow_literals=allow_literals) for p in parts))
    if kind == "Replication":
        return (_graph_literal_position(node.get("count"))
                and _bit_graph_positions_valid(node.get("concat"), depth + 1, budget, allow_literals=allow_literals))
    if kind in ("Conversion", "SignedConversion") or (
            kind == "UnaryOp" and node.get("op") == "BitwiseNot"):
        return _bit_graph_positions_valid(node.get("operand"), depth + 1, budget, allow_literals=allow_literals)
    return False


def build_bit_access_index(ast: dict[str, Any], *, expected_top: str,
                           index: dict[str, Any] | None = None,
                           enable_width_conversions: bool = True,
                           enable_width_literals: bool = True,
                           captured_assignments: list | None = None,
                           capture_trace: list | None = None) -> dict[str, Any]:
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
    basic_bounds=declared_bounds(structural)
    extended_bounds=declared_bounds(structural,extended=True)

    def trace(path, node, status):
        # Opt-in audit only: no change to historical graph or counts.
        if capture_trace is not None:
            if len(capture_trace) >= 20000:
                raise ValueError("capture_trace_budget")
            capture_trace.append((path,node,status))

    def extract(path: str, node: Any, *,
                procedure_kind: str | None = None,
                guards: tuple[dict[str, Any], ...] = (),
                events: tuple[dict[str, str], ...] = (),
                timing_scope: str = "not_procedural",
                context_partial: bool = False,
                selector_constants: dict | None = None,
                procedural_constants: dict | None = None) -> None:
        counts["assignments_seen"] += 1
        if not isinstance(node, dict) or node.get("kind") != "Assignment":
            trace(path,node,"not_assignment")
            return
        lhs, rhs = node.get("left"), node.get("right")
        if not (_contains_selection(lhs, [0]) or _contains_selection(rhs, [0])):
            trace(path,node,"selection_gate_negative")
            return
        target = _target_name(lhs, known[path], path, resolver)
        if target is None:
            counts["unsupported_targets"] += 1
            trace(path,node,"unsupported_target")
            return
        if len(rows) >= MAX_RECORDS:
            counts["truncated"] = True
            trace(path,node,"row_budget")
            return
        # Only continuous assignments use lexical constant normalization in
        # this phase. Keep the legacy extraction untouched if the strict
        # bit-position gate still rejects either side.
        if selector_constants:
            normalized_lhs = normalize_positions(lhs, selector_constants)
            normalized_rhs = normalize_positions(rhs, selector_constants)
            if (_bit_graph_positions_valid(normalized_lhs)
                    and _bit_graph_positions_valid(normalized_rhs)):
                lhs, rhs = normalized_lhs, normalized_rhs
        item: dict[str, Any] = {
            "target": target, "source": _location(node),
            "coverage": "partial", "target_selection": None,
            "rhs_width": None, "source_segments": [],
            "bit_graph_eligible": (_bit_graph_positions_valid(lhs)
                                   and _bit_graph_positions_valid(rhs)),
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
        def populate(candidate, *, additional=False, lhs=lhs, rhs=rhs):
            dest, select, dest_width = _selection(lhs, known[path], path, resolver)
            assert dest == target
            candidate["target_selection"] = select
            if additional and procedural_constants:
                # Resolve only lexically visible elaborated parameters.
                lhs=normalize_positions(lhs,procedural_constants)
                rhs=normalize_positions(rhs,procedural_constants)
                dest,select,dest_width=_selection(lhs,known[path],path,resolver)
                assert dest==target
                candidate["target_selection"]=select
            if additional:
                candidate["bit_graph_eligible"]=(_bit_graph_positions_valid(lhs)
                    and _bit_graph_positions_valid(rhs,allow_literals=True))
                if not candidate["bit_graph_eligible"]:
                    raise _Partial("unvalidated_ast_positions")
            width_events=[] if enable_width_conversions and candidate["bit_graph_eligible"] else None
            parts = _segments(rhs, known[path], path, resolver=resolver,
                              constant_ids=constant_ids,width_events=width_events,
                              allow_literals=additional,
                              trial_bounds=extended_bounds if additional else None)
            width = sum(part[2] for part in parts)
            if width > MAX_WIDTH:
                raise _Partial("rhs_too_wide")
            if additional:
                # Validate complete source segments before dropping any
                # high positions. An array element is not a flat bit.
                for source,selection,span in parts:
                    if source is not None:
                        source_positions(selection,extended_bounds.get(source),span)
                hi,lo=selected_bounds(select,extended_bounds.get(target))
                actual_width=hi-lo+1
                if actual_width!=width:
                    a=integral_shape(rhs.get("type"))
                    b=integral_shape(lhs.get("type"))
                    assignment_shape=integral_shape(node.get("type"))
                    if (a is None or b is None or assignment_shape is None
                            or assignment_shape!=b or shape_width(a)!=width
                            or shape_width(b)!=actual_width
                            or any("_value_transform" in sel for _,sel,_ in parts)
                            or node.get("op") is not None or node.get("timingControl") is not None):
                        raise _Partial("target_rhs_width_mismatch")
                    parts,mode=resize_constant_state(parts,a,b)
                    width_events.append({"mode":"assignment_"+mode,"source_width":width,
                                         "destination_width":actual_width,
                                         "source_signed":a[2],"destination_signed":b[2]})
                    width=actual_width
            if dest_width is not None and dest_width != width:
                raise _Partial("target_rhs_width_mismatch")
            rhs_lsb = 0
            positioned: list[dict[str, Any]] = []
            for source, selection, span in reversed(parts):
                # Keep value-changing transforms separate from the bit
                # selector. The latter locates the input bit but does NOT
                # claim output equals that bit.
                value_transform = selection.get("_value_transform")
                public_selection = {
                    key: value for key, value in selection.items()
                    if key != "_value_transform"
                }
                seg: dict[str, Any] = {
                    "source": source, "selection": public_selection,
                    "rhs_lsb": rhs_lsb, "rhs_msb": rhs_lsb + span - 1,
                }
                if value_transform is not None:
                    seg["value_transform"] = value_transform
                if dest_width is not None and select["kind"] in ("bit", "range"):
                    start = select["lsb"] if select["kind"] == "range" else select["index"]
                    seg["target_lsb"] = start + rhs_lsb
                    seg["target_msb"] = start + rhs_lsb + span - 1
                positioned.append(seg)
                rhs_lsb += span
            if additional and procedural_constants and width_events is not None:
                if lhs!=node.get("left") or rhs!=node.get("right"):
                    width_events.append({"mode":"scoped_procedural_selectors"})
            if width_events:
                candidate["width_conversions"]=width_events
            candidate["source_segments"] = list(reversed(positioned))
            candidate["rhs_width"] = width
            candidate["coverage"] = (
                "explicit_target_lanes"
                if dest_width is not None and select["kind"] in ("bit", "range")
                else "rhs_lanes_only"
            )
            if context_partial:
                candidate["coverage"]="partial"
                candidate["reason"]="unsupported_procedural_context"

        try:
            populate(item)
        except _Partial as exc:
            item["reason"]=str(exc)

        # Preserve the PR69 mapping verbatim whenever it already expands.
        # Retry only selected width/literal failures; never broaden the
        # assignment eligibility or reinterpret an opaque target.
        if (enable_width_conversions and enable_width_literals and not context_partial
                and node.get("op") is None and node.get("timingControl") is None):
            reason=item.get("reason")
            if item["coverage"]!="partial":
                try:
                    expand_assignment(item,extended_bounds if item.get("width_conversions") else basic_bounds)
                except (ValueError,KeyError,TypeError,AttributeError) as exc:
                    reason=str(exc)
            if reason in ("conversion_state_change_unmodeled","conversion_width_unproven_or_changed",
                          "target_rhs_width_mismatch","unsupported_rhs_UnbasedUnsizedIntegerLiteral",
                          "literal_width_unknown","source_width_unknown"):
                trial={**item,"coverage":"partial","rhs_width":None,"source_segments":[]}
                trial.pop("reason",None)
                trial.pop("width_conversions",None)
                try:
                    populate(trial,additional=True)
                    if not trial.get("width_conversions"):
                        raise _Partial("no_additional_width_evidence")
                    expand_assignment(trial,extended_bounds)
                except (_Partial,ValueError,KeyError,TypeError,AttributeError):
                    pass
                else:
                    item=trial
        counts["partial" if item["coverage"]=="partial" else "precise"]+=1
        rows.append(item)
        trace(path,node,"captured")
        if captured_assignments is not None:
            captured_assignments.append((item,node,path,
                dict(procedural_constants or selector_constants or {}),context_partial))

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
                   partial: bool = False, depth: int = 0,
                   procedural_constants: dict | None = None) -> None:
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
                           partial=partial, depth=depth + 1,procedural_constants=procedural_constants)
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
                    context_partial=partial,procedural_constants=procedural_constants)
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
                       partial=partial, depth=depth + 1,procedural_constants=procedural_constants)
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
                       depth=depth + 1,procedural_constants=procedural_constants)
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
                           depth=depth + 1,procedural_constants=procedural_constants)
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
                                       or len(guards) >= MAX_PROC_GUARDS, depth=depth + 1,procedural_constants=procedural_constants)
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
                               depth=depth + 1,procedural_constants=procedural_constants)
                else:
                    counts["unsupported_statements"] += 1
            return
        if kind not in ("Empty", "EmptyStatement"):
            # Loops, task calls and opaque statement kinds are NOT silently
            # analyzed by descending through their children.
            counts["unsupported_statements"] += 1

    def visit(members: Any, parent: str | None = None,
              inherited_constants: dict | None = None, *,
              instance_parameters: bool = False) -> None:
        if not isinstance(members, list):
            return
        local_constants = scope_constants(members, inherited_constants,
                                          instance_parameters=instance_parameters)
        for node in members:
            if not isinstance(node, dict):
                continue
            kind = node.get("kind")
            if kind in ("GenerateBlock", "GenerateBlockArray", "Scope"):
                if node.get("isUninstantiated") is not True:
                    visit(node.get("members"), parent, local_constants)
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
                visit(body.get("members"), path, instance_parameters=True)
            elif kind == "ContinuousAssign" and parent is not None:
                extract(parent, node.get("assignment"), selector_constants=local_constants)
            elif kind == "ProceduralBlock" and parent is not None:
                procedure_kind = node.get("procedureKind")
                if procedure_kind in ("AlwaysFF", "AlwaysComb", "AlwaysLatch", "Always"):
                    counts["procedural_blocks_visited"] += 1
                    statements(parent, node.get("body"),
                               procedure_kind=procedure_kind,
                               procedural_constants=local_constants)
                else:
                    counts["procedural_blocks_skipped"] += 1

    visit(ast.get("design", {}).get("members"))
    rows.sort(key=lambda item: (item["target"], str(item.get("source"))))
    if captured_assignments is not None:
        ordinals={id(row):i for i,row in enumerate(rows)}
        captured_assignments[:]=[(ordinals[id(row)],row,node,path,constants,partial)
                                  for row,node,path,constants,partial in captured_assignments]
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
            "bornées ; conversions de largeur explicite, extensions de signe/zéro "
            "non ambiguës et troncatures dans le périmètre positionnel validé. "
            "Alias de types, indices dynamiques, "
            "opérations arithmétiques/non positionnelles restent partiels ; "
            "sélections imbriquées sans indices cibles aplatis. "
            "Une négation unaire BitwiseNot de largeur prouvée reste "
            "positionnelle mais chaque segment transformé est explicitement "
            "étiqueté value_transform=bitwise_not : il ne s'agit pas "
            "d'une simple copie de bit. Les autres opérateurs unaires, "
            "les combinaisons de transformations inconnues ou les largeurs "
            "non démontrées restent partiels. Aucune preuve fonctionnelle. "
            "Les affectations procédurales enregistrent le type de processus, "
            "les gardes de branches syntaxiques et les événements explicites "
            "sans inférer la priorité, la latence ou la sémantique des NBA. "
            "Les sensibilité implicites ne sont pas reconstruites ; les "
            "instructions opaques sont signalées comme exclues. "
            "Ne couvre pas les connexions de ports ni les champs MemberAccess "
            "sans offsets prouvés."
        ),
    }

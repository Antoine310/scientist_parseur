"""Direct named integral conversions, assignment-local only (PR116).

Independent active occurrence census; no legacy row admission or promotion.
"""
from collections import Counter
import re

from .array_dependencies import Unsupported
from .bit_widths import integral_shape, width, conversion_mode
from .capture_audit import audit_capture
from .residual_audit import exact_links
from .symbols import SignalResolver
from .typed_layout import raw_layouts

MAX_ROWS = 2000
MAX_COORDINATES = 32768
MAX_WIDTH = 64
LEAVES = {"NamedValue", "ElementSelect", "RangeSelect"}


def require(ok, reason):
    if not ok:
        raise Unsupported(reason)


def shape(expr):
    typ = expr.get("type") if isinstance(expr, dict) else None
    require(isinstance(typ, str) and re.fullmatch(
        r"(?:logic|bit|reg)(?: signed| unsigned)?(?:\[\d{1,5}:\d{1,5}\])?", typ),
        "unsupported_integral_type")
    sh = integral_shape(typ)
    require(sh is not None and width(sh) <= MAX_WIDTH, "conversion_layout_or_budget")
    return sh


def endpoint(expr, resolve, raw):
    require(expr.get("kind") == "NamedValue", "unsupported_endpoint_selection")
    require("constant" not in expr, "constant_tag_outside_dynamic_scope")
    sh = shape(expr)
    name = resolve(expr)
    require(name is not None and raw.get(name) == expr["type"],
            "unproven_exact_signal_identity_or_type")
    return {"signal": name, "type": expr["type"],
            "bits_lsb_first": list(range(sh[1], sh[0] + 1))}


def position_map(source, dest):
    """Map relative destination positions to source positions or literal zero."""
    try:
        mode = conversion_mode(source, dest)
    except ValueError as exc:
        raise Unsupported(str(exc)) from exc
    a, b = width(source), width(dest)
    require(a <= MAX_WIDTH and b <= MAX_WIDTH, "conversion_layout_or_budget")
    positions = list(range(min(a, b)))
    if b > a:
        positions.extend([a - 1 if mode == "sign_extend" else None] * (b - a))
    return mode, positions


def expand(node, context, resolve, raw):
    require(context in ("continuous", "AlwaysComb"), "unsupported_assignment_context")
    require(node.get("kind") == "Assignment" and node.get("isNonBlocking") is False
            and node.get("op") is None and node.get("timingControl") is None,
            "not_plain_blocking_assignment")
    lhs, rhs = node.get("left"), node.get("right")
    require(isinstance(lhs, dict) and isinstance(rhs, dict) and rhs.get("kind") == "Conversion"
            and node.get("type") == lhs.get("type") == rhs.get("type"),
            "not_exact_result_conversion")
    require("constant" not in rhs, "constant_tag_outside_dynamic_scope")
    leaf = rhs.get("operand")
    require(isinstance(leaf, dict) and leaf.get("kind") in LEAVES, "not_direct_leaf_conversion")
    src_shape, dst_shape = shape(leaf), shape(lhs)
    src, dst = endpoint(leaf, resolve, raw), endpoint(lhs, resolve, raw)
    mode, positions = position_map(src_shape, dst_shape)
    pairs = [{"target_bit": t, "source_bit": src["bits_lsb_first"][p]}
             for t, p in zip(dst["bits_lsb_first"], positions) if p is not None]
    zero = [t for t, p in zip(dst["bits_lsb_first"], positions) if p is None]
    return {"source": src, "target": dst, "mode": mode, "pairs": pairs,
            "zero_fill_bits": zero, "potential_pairs": len(pairs),
            "relation": "statement_local_dynamic_conversion_candidate",
            "model_domain": "defined_binary_inputs_only",
            "guard_feasibility": "not_proven", "timing": "not_proven",
            "permanent_constant": "not_inferred"}


def at_pointer(ast, pointer):
    obj = ast
    for key in pointer.split("/")[1:]:
        key = key.replace("~1", "/").replace("~0", "~")
        obj = obj[int(key)] if isinstance(obj, list) else obj[key]
    return obj


def audit_dynamic_conversions(ast, index, graph):
    census = audit_capture(ast, index, graph)
    _, _, residual, _, _, _ = exact_links(graph)
    resolver, raw = SignalResolver(ast, index), raw_layouts(index)
    rows, pairs, zeros = [], 0, 0
    for occurrence in census["items"]:
        node = at_pointer(ast, occurrence["ast_path"])
        rhs = node.get("right")
        if not isinstance(rhs, dict) or rhs.get("kind") != "Conversion":
            continue
        leaf = rhs.get("operand")
        if not isinstance(leaf, dict) or leaf.get("kind") not in LEAVES or "constant" in leaf:
            continue
        if len(rows) >= MAX_ROWS:
            raise ValueError("dynamic_conversion_row_budget")
        row = {k: occurrence[k] for k in ("ast_path", "instance", "context", "source",
                                          "historical_status", "flat_assignment_id")}
        row["historical_residual"] = row["flat_assignment_id"] in residual
        row["coverage"] = "partial"
        row["source_type"] = leaf.get("type")
        row["result_type"] = rhs.get("type")
        try:
            candidate = expand(node, row["context"],
                               lambda e: resolver.resolve_exact(row["instance"], e), raw)
            if row["flat_assignment_id"] is not None:
                historical = graph["bit_dependency_graph"]["items"][row["flat_assignment_id"]]
                require(historical["target"] == candidate["target"]["signal"],
                        "assignment_target_identity_mismatch")
        except Unsupported as exc:
            row["reason"] = str(exc)
        else:
            pairs += candidate["potential_pairs"]
            zeros += len(candidate["zero_fill_bits"])
            if pairs + zeros > MAX_COORDINATES:
                raise ValueError("dynamic_conversion_coordinate_budget")
            row.update(coverage="dynamic_conversion_candidates", candidate=candidate)
        rows.append(row)
    good = [r for r in rows if r["coverage"] != "partial"]
    return {"schema_version": 1, "scope": "active_direct_leaf_conversion_occurrences",
            "counts": {"ast_occurrences": census["counts"]["ast_occurrences"],
                       "historical_rows": census["counts"]["historical_rows"],
                       "roots": len(rows), "supported": len(good), "partial": len(rows)-len(good),
                       "supported_residual": sum(r["historical_residual"] for r in good),
                       "supported_without_flat_id": sum(r["flat_assignment_id"] is None for r in good),
                       "potential_pairs": pairs, "zero_fill_coordinates": zeros,
                       "stored_coordinates": pairs+zeros, "truncated": False},
            "partial_reasons": dict(Counter(r["reason"] for r in rows if "reason" in r)),
            "items": rows, "historical_replay_exact": True,
            "historical_graph_promoted": False, "new_historical_edges": 0,
            "design_coverage": "not_measured", "functional_influence": "not_proven",
            "caveat": "Direct statement candidates only; no global influence, X/Z, guards, timing or RTL proof."}

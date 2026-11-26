"""Experimental aggregate census and exact direct-concat positions.

Separate report; does not modify the historical signal/bit graphs.
Only continuous plain assignments of unsigned scalar/vector NamedValues,
with explicit declaration identity, equal width/state and no overlapping
target positions. Packed members/unions are inventoried, not flattened.
"""
from collections import Counter
import re

from .analysis_budgets import inspect_ast
from .array_dependencies import Unsupported, layout, lane_order
from .complex_constructs import METADATA
from .symbols import SignalResolver, member_name
from .typed_layout import raw_layouts

MAX_ROWS = 2000
MAX_LANES = 1024
MAX_EDGES = 32768
MAX_OPERANDS = 32
MAX_EXPR_NODES = 4096


def scalar_vector(raw):
    t = layout(raw)
    if t is None or t[2] or len(t[1]) > 1:
        raise Unsupported("unproven_scalar_vector_layout")
    return t[0], lane_order(*t[1][0]) if t[1] else [0]


def expand_concat(node, resolve, declared):
    """Exact positional candidates; LSB first, reversed concat operand order."""
    if (not isinstance(node, dict) or node.get("kind") != "Assignment"
            or node.get("isNonBlocking") is not False
            or node.get("op") is not None or node.get("timingControl") is not None):
        raise Unsupported("not_plain_blocking_assignment")
    lhs, rhs = node.get("left"), node.get("right")
    if not isinstance(lhs, dict) or lhs.get("kind") != "Concatenation":
        raise Unsupported("not_concat_lhs")

    def lanes(expr):
        if not isinstance(expr, dict):
            raise Unsupported("malformed_expression")
        state, bits = scalar_vector(expr.get("type"))
        if expr.get("kind") == "NamedValue":
            name = resolve(expr)
            if name is None or declared.get(name) != expr.get("type"):
                raise Unsupported("unproven_declaration_identity_or_type")
            return state, [(name, bit) for bit in bits]
        if expr.get("kind") != "Concatenation":
            raise Unsupported("unsupported_concat_operand")
        parts = expr.get("operands")
        if not isinstance(parts, list) or not 1 <= len(parts) <= MAX_OPERANDS:
            raise Unsupported("concat_operand_budget_or_shape")
        result = []
        for part in reversed(parts):
            if not isinstance(part, dict) or part.get("kind") != "NamedValue":
                raise Unsupported("unsupported_concat_operand")
            s, p = lanes(part)
            if s != state:
                raise Unsupported("concat_state_mismatch")
            if len(result) + len(p) > MAX_LANES:
                raise Unsupported("lane_budget_exceeded")
            result.extend(p)
        if len(result) != len(bits):
            raise Unsupported("concat_width_mismatch")
        return state, result

    ds, dst = lanes(lhs)
    ss, src = lanes(rhs)
    assignment_state, assignment_bits = scalar_vector(node.get("type"))
    if (assignment_state != ds or len(assignment_bits) != len(dst)
            or ss != ds or len(src) != len(dst)):
        raise Unsupported("assignment_width_or_state_mismatch")
    if len(set(dst)) != len(dst):
        raise Unsupported("overlapping_target_positions")
    return [{"source": s, "source_bit": sb, "target": t, "target_bit": tb,
             "relation": "concat_position_candidate"}
            for (s, sb), (t, tb) in zip(src, dst)]


def type_text(node):
    raw = node.get("type") if isinstance(node, dict) else None
    if not isinstance(raw, str):
        return None
    # Elaboration-local identity tokens are not persistent evidence.
    raw = re.sub(r"\b[0-9]+ (?=[A-Za-z_$])", "<addr> ", raw)
    return raw[:512] + ("<clipped>" if len(raw) > 512 else "")


def member_sites(expr):
    """Inventory MemberAccess descendants; nested assignments are separate sites."""
    found = []
    visited = 0
    def visit(n):
        nonlocal visited
        visited += 1
        if visited > MAX_EXPR_NODES:
            raise Unsupported("expression_scan_budget")
        if isinstance(n, list):
            for child in n:
                visit(child)
        elif isinstance(n, dict):
            if n.get("kind") == "Assignment":
                return
            if n.get("kind") == "MemberAccess":
                found.append({"member": member_name(n),
                              "base_type": type_text(n.get("value")),
                              "result_type": type_text(n)})
            for k, child in n.items():
                if k not in METADATA and isinstance(child, (dict, list)):
                    visit(child)
    visit(expr)
    return found


def assignment_sites(ast):
    """Active continuous/process syntax, not declarations/functions/initializers."""
    def walk(n, owner=None, context=None):
        if isinstance(n, list):
            for child in n:
                yield from walk(child, owner, context)
            return
        if not isinstance(n, dict) or n.get("isUninstantiated") is True:
            return
        k = n.get("kind")
        if k == "Instance":
            name, body = n.get("name"), n.get("body")
            if isinstance(name, str) and isinstance(body, dict):
                yield from walk(body.get("members"), f"{owner}.{name}" if owner else name)
            return
        if k in ("GenerateBlock", "GenerateBlockArray", "Scope"):
            yield from walk(n.get("members"), owner, context)
            return
        if k == "ContinuousAssign":
            yield from walk(n.get("assignment"), owner, "continuous")
            return
        if k == "ProceduralBlock":
            yield from walk(n.get("body"), owner, n.get("procedureKind") or "unknown_process")
            return
        if context is None or k in ("Function", "Task", "Subroutine", "Variable", "Net", "Parameter", "TypeAlias"):
            return
        if k == "Assignment":
            yield owner, context, n
        for key, child in n.items():
            if key not in METADATA and isinstance(child, (dict, list)):
                yield from walk(child, owner, context)
    yield from walk(ast["design"]["members"])


def audit(ast, index):
    inspect_ast(ast)
    resolver = SignalResolver(ast, index)
    declared = raw_layouts(index)
    instances = {i["path"] for i in index["instances"]}
    rows, edges = [], []
    total = 0
    for owner, context, node in assignment_sites(ast):
        total += 1
        lhs, rhs = node.get("left"), node.get("right")
        members_l, members_r = member_sites(lhs), member_sites(rhs)
        is_concat = isinstance(lhs, dict) and lhs.get("kind") == "Concatenation"
        if not (members_l or members_r or is_concat):
            continue
        if len(rows) >= MAX_ROWS:
            raise Unsupported("aggregate_row_budget")
        row = {"site_id": len(rows), "instance": owner if owner in instances else None,
               "context": context, "source": {
                   "file": node.get("source_file_start") or node.get("source_file"),
                   "line": node.get("source_line_start") or node.get("source_line")},
               "lhs_concat": is_concat, "lhs_type": type_text(lhs), "rhs_type": type_text(rhs),
               "lhs_members": members_l, "rhs_members": members_r,
               "coverage": "partial", "edge_count": 0}
        rows.append(row)
        try:
            if members_l or members_r:
                raise Unsupported("member_layout_not_proven")
            if context != "continuous" or owner not in instances:
                raise Unsupported("unsupported_assignment_context")
            local = expand_concat(node, lambda expr: resolver.resolve_exact(owner, expr), declared)
            if len(edges) + len(local) > MAX_EDGES:
                raise Unsupported("aggregate_edge_budget")
        except Unsupported as exc:
            # Fail closed on budgets; don't publish a complete-looking partial census.
            if "budget" in str(exc):
                raise
            row["reason"] = str(exc)
            continue
        row.update(coverage="concat_position_candidates", edge_count=len(local))
        edges.extend({**e, "site_id": row["site_id"]} for e in local)
    counts = Counter(row["coverage"] for row in rows)
    return {"scope": "active_assignment_syntax_aggregate_sites", "assignment_ast_occurrences": total,
            "counts": {"sites": len(rows), "supported": counts["concat_position_candidates"],
                       "partial": counts["partial"], "edges": len(edges),
                       "lhs_concat": sum(r["lhs_concat"] for r in rows),
                       "lhs_member": sum(bool(r["lhs_members"]) for r in rows),
                       "rhs_member": sum(bool(r["rhs_members"]) for r in rows)},
            "partial_reasons": dict(Counter(r["reason"] for r in rows if "reason" in r)),
            "items": rows, "edges": edges, "design_coverage": "not_measured",
            "functional_influence": "not_proven", "formal_proof": "not_performed",
            "caveat": "Independent AST occurrence census; not the historical flat bit denominator. "
                      "Categories overlap. Member offsets, procedural writes, conversions, "
                      "selections and nested concatenations are not proven here."}

"""Separate candidates for fixed bit reads and binary literals written to fields.

Extends the PR79 scope without changing its report or claiming temporal effects.
Only direct scalar fields, exact typed declaration and observed member tokens.
"""
from collections import Counter
import re

from .aggregate_layout import assignment_sites, member_sites
from .analysis_budgets import inspect_ast
from .array_dependencies import Unsupported
from .packed_members import fields, token, observed_members, integral
from .symbols import SignalResolver
from .typed_layout import Types, raw_layouts

MAX_ROWS = 2000


def expand(node, resolve, declared, types, observations):
    if (node.get("kind") != "Assignment" or node.get("isNonBlocking") is not False
            or node.get("op") is not None or node.get("timingControl") is not None):
        raise Unsupported("not_plain_blocking_assignment")
    lhs, rhs = node.get("left"), node.get("right")
    if not isinstance(lhs, dict) or lhs.get("kind") != "MemberAccess":
        raise Unsupported("not_direct_member_target")
    if lhs.get("type") != "logic" or node.get("type") != "logic":
        raise Unsupported("not_scalar_logic_target")
    base = lhs.get("value")
    if not isinstance(base, dict) or base.get("kind") != "NamedValue":
        raise Unsupported("unsupported_member_base")
    target = resolve(base)
    raw = base.get("type")
    if target is None or declared.get(target) != raw or not isinstance(raw, str):
        raise Unsupported("unproven_target_identity")
    state, members = fields(raw, types)
    addr, name = token(lhs)
    by_field, by_addr = observations
    if by_field.get((raw, name)) != {addr} or by_addr.get(addr) != {(raw, name)}:
        raise Unsupported("inconsistent_observed_member_token")
    if name not in members:
        raise Unsupported("field_not_in_exact_type")
    typ, bits, offset = members[name]
    if state != "logic" or typ != "logic" or bits != [0]:
        raise Unsupported("not_scalar_logic_field")
    dest = {"target": target, "target_bit": offset, "field": name,
            "field_bit": 0, "packed_type": raw.split(" ", 1)[1]}
    if not isinstance(rhs, dict) or rhs.get("type") != "logic":
        raise Unsupported("unsupported_rhs_type")
    if rhs.get("kind") == "ElementSelect":
        src, sel = rhs.get("value"), rhs.get("selector")
        if not isinstance(src, dict) or src.get("kind") != "NamedValue":
            raise Unsupported("unsupported_source_base")
        signal = resolve(src)
        srctype = src.get("type")
        if signal is None or declared.get(signal) != srctype:
            raise Unsupported("unproven_source_identity")
        if not isinstance(srctype, str) or not re.fullmatch(r"logic\[[0-9]{1,5}:[0-9]{1,5}\]", srctype):
            raise Unsupported("not_plain_logic_vector")
        source_state, source_bits = integral(srctype, types)
        if source_state != "logic" or not isinstance(sel, dict) or sel.get("kind") != "IntegerLiteral" or sel.get("type") != "int":
            raise Unsupported("unproven_fixed_selector")
        value = sel.get("value")
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,5}", value):
            raise Unsupported("unproven_fixed_selector")
        if "constant" in sel and sel["constant"] != value:
            raise Unsupported("selector_constant_disagreement")
        bit = int(value)
        if bit not in source_bits:
            raise Unsupported("selector_out_of_range")
        return {"relation": "fixed_member_position_candidate", **dest,
                "source": signal, "source_bit": bit}, None
    if rhs.get("kind") == "Conversion":
        operand = rhs.get("operand")
        if (not isinstance(operand, dict) or operand.get("kind") != "IntegerLiteral"
                or operand.get("type") != "bit[0:0]"
                or operand.get("value") not in ("1'b0", "1'b1")):
            raise Unsupported("unproven_binary_literal")
        value = operand["value"]
        if any("constant" in n and n["constant"] != value for n in (rhs, operand)):
            raise Unsupported("literal_constant_disagreement")
        return None, {"relation": "local_constant_write_candidate", **dest,
                      "value": int(value[-1])}
    raise Unsupported("unsupported_rhs")


def audit_writes(ast, index, *, include_occurrence=False, _shared=None):
    if _shared is None:
        inspect_ast(ast)
    else:
        _shared.check_inputs(ast,index)
    types = Types(ast) if _shared is None else _shared.types
    if types.truncated:
        raise Unsupported("package_inventory_budget")
    observations = observed_members(ast, types) if _shared is None else _shared.package_observations
    resolver = SignalResolver(ast, index) if _shared is None else _shared.resolver
    declared = raw_layouts(index) if _shared is None else _shared.declared
    instances = {i["path"] for i in index["instances"]} if _shared is None else _shared.instances
    rows, edges, constants = [], [], []
    for ordinal, (owner, context, node) in (enumerate(assignment_sites(ast)) if _shared is None else _shared.member_assignments):
        lhs, rhs = node.get("left"), node.get("right")
        if not isinstance(lhs, dict) or lhs.get("kind") != "MemberAccess":
            continue
        if not isinstance(rhs, dict) or rhs.get("kind") not in ("ElementSelect", "Conversion"):
            continue
        if len(rows) >= MAX_ROWS:
            raise Unsupported("member_write_row_budget")
        row = {"site_id": len(rows), "instance": owner, "context": context,
               "source": {"file": node.get("source_file_start") or node.get("source_file"),
                          "line": node.get("source_line_start") or node.get("source_line")},
               "coverage": "partial"}
        if include_occurrence:
            row["occurrence_ordinal"] = ordinal
        rows.append(row)
        try:
            if owner not in instances or context not in ("continuous", "AlwaysComb"):
                raise Unsupported("unsupported_assignment_context")
            edge, constant = expand(node, lambda e: resolver.resolve_exact(owner, e),
                                    declared, types, observations)
        except Unsupported as exc:
            if "budget" in str(exc):
                raise
            row["reason"] = str(exc)
            continue
        row["coverage"] = "position_candidate" if edge is not None else "constant_candidate"
        if edge is not None:
            edges.append({**edge, "site_id": row["site_id"]})
        if constant is not None:
            constants.append({**constant, "site_id": row["site_id"]})
    return {"scope": "scalar_package_member_writes_fixed_select_or_binary_literal",
            "counts": {"sites": len(rows), "supported": len(edges)+len(constants),
                       "partial": sum(r["coverage"] == "partial" for r in rows),
                       "edges": len(edges), "constants": len(constants)},
            "partial_reasons": dict(Counter(r["reason"] for r in rows if "reason" in r)),
            "items": rows, "edges": edges, "constants": constants,
            "design_coverage": "not_measured", "functional_influence": "not_proven",
            "formal_proof": "not_performed",
            "caveat": "Local assignment candidates only; no guard, priority, temporal or global value claim. "
                      "Field identity limitations of PR79 remain. Constants are not dependency edges."}

"""Local constant writes to package packed enum fields, distinct from edges.

Require an explicit typedef-to-EnumType token, exact EnumValue identity,
and an independently checkable binary initializer. Field offsets retain
PR79's serialized-layout/member-token limitation.
"""
from collections import Counter
import re

from .aggregate_layout import assignment_sites, scalar_vector
from .analysis_budgets import inspect_ast
from .array_dependencies import Unsupported
from .packed_members import fields, token, observed_members
from .symbols import SignalResolver
from .typed_layout import Types, raw_layouts, identity

MAX_ROWS = 2000
MAX_ENUM_VALUES = 256
MAX_BITS = 32
SYMBOL = re.compile(r"([0-9]{1,32}) ([A-Za-z_$][A-Za-z0-9_$]*)\Z")
BINARY = re.compile(r"([1-9][0-9]?)'b([01]+)\Z")


def enum_for(raw, types):
    if not isinstance(raw, str):
        return None
    alias = types.types.get(raw)
    if not alias or alias.get("kind") != "TypeAlias":
        return None
    target = alias.get("target")
    if not isinstance(target, str) or raw.split(" ", 1)[-1] != target.split(" ", 1)[-1]:
        return None
    enum = types.types.get(target)
    if not enum or enum.get("kind") != "EnumType":
        return None
    return target, enum


def value_bits(expr, enum_token, enum, resolve):
    if (not isinstance(expr, dict) or expr.get("kind") != "NamedValue"
            or expr.get("type") != enum_token or resolve(expr) is not None):
        raise Unsupported("unproven_enum_reference")
    raw = expr.get("symbol")
    match = SYMBOL.fullmatch(raw) if isinstance(raw, str) else None
    if match is None:
        raise Unsupported("malformed_enum_reference")
    address, name = match.groups()
    entries = enum.get("members")
    if not isinstance(entries, list) or not entries:
        raise Unsupported("missing_enum_values")
    if len(entries) > MAX_ENUM_VALUES:
        raise Unsupported("enum_value_budget")
    if any(not isinstance(e, dict) or e.get("kind") != "EnumValue"
           or identity(e) is None or not isinstance(e.get("name"), str) for e in entries):
        raise Unsupported("malformed_enum_values")
    addresses = [identity(e) for e in entries]
    names = [e["name"] for e in entries]
    if len(set(addresses)) != len(entries) or len(set(names)) != len(entries):
        raise Unsupported("ambiguous_enum_values")
    matches = [e for e in entries if identity(e) == address and e["name"] == name]
    if len(matches) != 1:
        raise Unsupported("unproven_enum_value_identity")
    entry = matches[0]
    base = enum.get("baseType")
    state, bits = scalar_vector(base)
    if state != "logic" or len(bits) > MAX_BITS or base != f"logic[{len(bits)-1}:0]":
        raise Unsupported("unsupported_enum_base")
    init = entry.get("initializer")
    if not isinstance(init, dict) or init.get("kind") != "Conversion" or init.get("type") != base:
        raise Unsupported("unsupported_enum_initializer")
    op = init.get("operand")
    if not isinstance(op, dict) or op.get("kind") != "IntegerLiteral" or op.get("type") != f"bit[{len(bits)-1}:0]":
        raise Unsupported("unsupported_enum_initializer")
    value = op.get("value")
    m = BINARY.fullmatch(value) if isinstance(value, str) and len(value) <= MAX_BITS+4 else None
    if m is None or int(m[1]) != len(bits) or len(m[2]) > len(bits):
        raise Unsupported("unproven_enum_encoding")
    if entry.get("value") != value or any("constant" in n and n["constant"] != value
                                            for n in (op, init, expr)):
        raise Unsupported("enum_encoding_disagreement")
    encoded = int(m[2], 2)
    return name, [(encoded >> i) & 1 for i in range(len(bits))]


def expand(node, resolve, declared, types, observations):
    if (node.get("kind") != "Assignment" or node.get("isNonBlocking") is not False
            or node.get("op") is not None or node.get("timingControl") is not None):
        raise Unsupported("not_plain_blocking_assignment")
    lhs, rhs = node.get("left"), node.get("right")
    if not isinstance(lhs, dict) or lhs.get("kind") != "MemberAccess":
        raise Unsupported("not_direct_member_target")
    base = lhs.get("value")
    if not isinstance(base, dict) or base.get("kind") != "NamedValue":
        raise Unsupported("unsupported_member_base")
    raw = base.get("type")
    dest = resolve(base)
    if not isinstance(raw, str) or dest is None or declared.get(dest) != raw:
        raise Unsupported("unproven_target_identity")
    state, members = fields(raw, types)
    addr, field = token(lhs)
    by_field, by_addr = observations
    if by_field.get((raw, field)) != {addr} or by_addr.get(addr) != {(raw, field)}:
        raise Unsupported("inconsistent_observed_member_token")
    if field not in members:
        raise Unsupported("field_not_in_exact_type")
    typ, bits, offset = members[field]
    if state != "logic" or lhs.get("type") != typ or node.get("type") != typ:
        raise Unsupported("member_type_disagreement")
    e = enum_for(typ, types)
    if e is None:
        raise Unsupported("unproven_enum_alias")
    name, values = value_bits(rhs, *e, resolve)
    if len(values) != len(bits):
        raise Unsupported("enum_width_disagreement")
    return [{"relation": "local_enum_constant_write_candidate", "target": dest,
             "target_bit": offset+i, "field": field, "field_bit": bit,
             "enum_type": typ.split(" ", 1)[1], "enum_value": name, "value": values[i]}
            for i, bit in enumerate(bits)]


def audit_enum_writes(ast, index):
    inspect_ast(ast)
    types = Types(ast)
    if types.truncated:
        raise Unsupported("package_inventory_budget")
    observations = observed_members(ast, types)
    resolver = SignalResolver(ast, index)
    declared = raw_layouts(index)
    instances = {i["path"] for i in index["instances"]}
    rows, constants = [], []
    for owner, context, node in assignment_sites(ast):
        lhs, rhs = node.get("left"), node.get("right")
        if (not isinstance(lhs, dict) or lhs.get("kind") != "MemberAccess"
                or enum_for(lhs.get("type"), types) is None
                or not isinstance(rhs, dict) or rhs.get("kind") != "NamedValue"):
            continue
        if len(rows) >= MAX_ROWS:
            raise Unsupported("enum_row_budget")
        row = {"site_id": len(rows), "instance": owner, "context": context,
               "source": {"file": node.get("source_file_start") or node.get("source_file"),
                          "line": node.get("source_line_start") or node.get("source_line")},
               "coverage": "partial", "constant_count": 0}
        rows.append(row)
        try:
            if owner not in instances or context not in ("continuous", "AlwaysComb"):
                raise Unsupported("unsupported_assignment_context")
            local = expand(node, lambda e: resolver.resolve_exact(owner, e), declared, types, observations)
        except Unsupported as exc:
            if "budget" in str(exc):
                raise
            row["reason"] = str(exc)
            continue
        row.update(coverage="constant_candidates", constant_count=len(local))
        constants.extend({**c, "site_id": row["site_id"]} for c in local)
    supported = sum(r["coverage"] == "constant_candidates" for r in rows)
    return {"scope": "direct_package_enum_constant_member_writes",
            "counts": {"sites": len(rows), "supported": supported, "partial": len(rows)-supported,
                       "edges": 0, "constants": len(constants)},
            "items": rows, "edges": [], "constants": constants,
            "partial_reasons": dict(Counter(r["reason"] for r in rows if "reason" in r)),
            "design_coverage": "not_measured", "functional_influence": "not_proven",
            "formal_proof": "not_performed",
            "caveat": "Local enum constants only; no guard, priority, reachability or temporal proof. "
                      "PR79 field declaration identity limitation remains. Constants are not edges."}

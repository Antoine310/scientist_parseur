"""Experimental package packed-struct position candidates, separate report.

Slang 12.1 prints ordered fields in TypeAlias.target, without field declaration
addresses. Require exact package type token, a unique field in that type,
matching expression type and consistent observed semantic member tokens.
This is conditional on the compiler's serialized type and member metadata,
not an independent proof of field address binding or functional influence.
"""
from collections import Counter, defaultdict
import re

from .aggregate_layout import assignment_sites, member_sites, scalar_vector
from .analysis_budgets import inspect_ast
from .array_dependencies import Unsupported
from .symbols import SignalResolver
from .typed_layout import Types, raw_layouts

MAX_FIELDS = 64
MAX_WIDTH = 1024
MAX_TYPE_TEXT = 8192
MAX_ROWS = 2000
MAX_EDGES = 32768
IDENT = r"[A-Za-z_$][A-Za-z0-9_$]*"
MEMBER = re.compile(r"([0-9]{1,32}) (" + IDENT + r")\Z")
STRUCT = re.compile(r"struct packed\{([^{}]+)\}(" + IDENT + r")::s\$[0-9]+\Z")


def integral(raw, types):
    canonical = types.resolve(raw) or raw
    return scalar_vector(canonical)


def fields(raw, types):
    node = types.types.get(raw)
    if node is None or node.get("kind") != "TypeAlias":
        raise Unsupported("unproven_package_struct_identity")
    target = node.get("target")
    if not isinstance(target, str) or len(target) > MAX_TYPE_TEXT:
        raise Unsupported("unsupported_struct_type")
    match = STRUCT.fullmatch(target)
    if match is None or raw.split(" ", 1)[1].split("::")[0] != match[2]:
        raise Unsupported("unsupported_struct_type")
    body = match[1]
    if not body.endswith(";"):
        raise Unsupported("malformed_struct_fields")
    parts = body[:-1].split(";")
    if not 1 <= len(parts) <= MAX_FIELDS:
        raise Unsupported("struct_field_budget")
    result = {}
    offset = 0
    state = None
    for item in reversed(parts):
        pair = item.rsplit(" ", 1)
        if len(pair) != 2 or not re.fullmatch(IDENT, pair[1]) or pair[1] in result:
            raise Unsupported("ambiguous_struct_field")
        typ, name = pair
        s, bits = integral(typ, types)
        if state is not None and s != state:
            raise Unsupported("mixed_struct_state")
        state = s
        result[name] = (typ, bits, offset)
        offset += len(bits)
        if offset > MAX_WIDTH:
            raise Unsupported("struct_width_budget")
    return state, result


def token(expr):
    raw = expr.get("member")
    m = MEMBER.fullmatch(raw) if isinstance(raw, str) else None
    if m is None:
        raise Unsupported("malformed_member_token")
    return m[1], m[2]


def observed_members(ast, types):
    by_field, by_addr = defaultdict(set), defaultdict(set)
    def walk(n):
        if isinstance(n, list):
            for child in n:
                walk(child)
        elif isinstance(n, dict):
            if n.get("kind") == "MemberAccess":
                base = n.get("value")
                raw = base.get("type") if isinstance(base, dict) else None
                if isinstance(raw, str) and raw in types.types:
                    try:
                        addr, name = token(n)
                    except Unsupported:
                        pass
                    else:
                        by_field[(raw, name)].add(addr)
                        by_addr[addr].add((raw, name))
            for child in n.values():
                if isinstance(child, (dict, list)):
                    walk(child)
    walk(ast)
    return by_field, by_addr


def expand(node, resolve, declared, types, observations):
    if (node.get("kind") != "Assignment" or node.get("isNonBlocking") is not False
            or node.get("op") is not None or node.get("timingControl") is not None):
        raise Unsupported("not_plain_blocking_assignment")
    by_field, by_addr = observations
    def named(n):
        if not isinstance(n, dict) or n.get("kind") != "NamedValue":
            raise Unsupported("unsupported_member_base_or_operand")
        name = resolve(n)
        if name is None or declared.get(name) != n.get("type"):
            raise Unsupported("unproven_signal_identity_or_type")
        return name
    def lanes(n):
        if not isinstance(n, dict):
            raise Unsupported("malformed_expression")
        if n.get("kind") == "NamedValue":
            s, bits = integral(n.get("type"), types)
            return s, [(named(n), bit, None) for bit in bits]
        if n.get("kind") != "MemberAccess":
            raise Unsupported("unsupported_direct_operand")
        base = n.get("value")
        signal = named(base)
        raw = base.get("type")
        state, members = fields(raw, types)
        addr, member = token(n)
        if (by_field.get((raw, member)) != {addr}
                or by_addr.get(addr) != {(raw, member)}):
            raise Unsupported("inconsistent_observed_member_token")
        if member not in members:
            raise Unsupported("field_not_in_exact_type")
        typ, bits, offset = members[member]
        if n.get("type") != typ:
            raise Unsupported("member_type_disagreement")
        return state, [(signal, offset+i, {"field": member, "field_bit": bit,
                       "packed_type": raw.split(" ", 1)[1]})
                       for i, bit in enumerate(bits)]
    lhs, rhs = node.get("left"), node.get("right")
    if not any(isinstance(n, dict) and n.get("kind") == "MemberAccess" for n in (lhs, rhs)):
        raise Unsupported("not_direct_member_assignment")
    ds, dst = lanes(lhs)
    ss, src = lanes(rhs)
    if node.get("type") != lhs.get("type") or ss != ds or len(src) != len(dst):
        raise Unsupported("assignment_type_width_or_state_mismatch")
    return [{"source": s, "source_bit": sb, "source_field": sf,
             "target": t, "target_bit": tb, "target_field": tf,
             "relation": "packed_struct_position_candidate"}
            for (s, sb, sf), (t, tb, tf) in zip(src, dst)]


def audit_members(ast, index, *, include_occurrence=False, _shared=None):
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
    rows, edges = [], []
    instances = {i["path"] for i in index["instances"]} if _shared is None else _shared.instances
    for ordinal, (owner, context, node) in (enumerate(assignment_sites(ast)) if _shared is None else _shared.member_assignments):
        lhs, rhs = node.get("left"), node.get("right")
        if not (member_sites(lhs) or member_sites(rhs)):
            continue
        if len(rows) >= MAX_ROWS:
            raise Unsupported("member_row_budget")
        row = {"site_id": len(rows), "instance": owner, "context": context,
               "source": {"file": node.get("source_file_start") or node.get("source_file"),
                          "line": node.get("source_line_start") or node.get("source_line")},
               "coverage": "partial", "edge_count": 0}
        if include_occurrence:
            row["occurrence_ordinal"] = ordinal
        rows.append(row)
        try:
            if context not in ("continuous", "AlwaysComb") or owner not in instances:
                raise Unsupported("unsupported_assignment_context")
            local = expand(node, lambda e: resolver.resolve_exact(owner, e),
                           declared, types, observations)
            if len(edges) + len(local) > MAX_EDGES:
                raise Unsupported("member_edge_budget")
        except Unsupported as exc:
            if "budget" in str(exc):
                raise
            row["reason"] = str(exc)
            continue
        row.update(coverage="position_candidates", edge_count=len(local))
        edges.extend({**e, "site_id": row["site_id"]} for e in local)
    counts = Counter(r["coverage"] for r in rows)
    return {"scope": "direct_package_packed_struct_member_assignment_sites",
            "counts": {"sites": len(rows), "supported": counts["position_candidates"],
                       "partial": counts["partial"], "edges": len(edges)},
            "partial_reasons": dict(Counter(r["reason"] for r in rows if "reason" in r)),
            "items": rows, "edges": edges, "design_coverage": "not_measured",
            "functional_influence": "not_proven", "formal_proof": "not_performed",
            "caveat": "Packed offsets are LSB-relative; vector bits are declaration indices. "
                      "Member declaration addresses are absent from TypeAlias.target; "
                      "only observed token consistency is checked. No guard, priority, "
                      "temporal or whole-design coverage claim."}

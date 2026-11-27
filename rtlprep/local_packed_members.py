"""Local multidimensional packed struct candidates, separate experimental report.

Only direct typedefs of the actual elaborated instance body, exact address
and module-qualified type, homogeneous unsigned logic packed fields.
Member declaration addresses remain absent from the printed layout.
"""
from collections import Counter, defaultdict
from itertools import product
import re

from .aggregate_layout import assignment_sites
from .analysis_budgets import inspect_ast
from .array_dependencies import Unsupported, layout, lane_order
from .packed_members import token
from .symbols import SignalResolver
from .typed_layout import raw_layouts, identity

MAX_WIDTH = 1024
MAX_FIELDS = 64
MAX_ROWS = 2000
MAX_POSITIONS = 32768
MAX_LOCAL_TYPES = 4096
IDENT = r"[A-Za-z_$][A-Za-z0-9_$]*"
TYPE = re.compile(r"([0-9]{1,32}) (" + IDENT + r")\.(" + IDENT + r")\Z")
STRUCT = re.compile(r"struct packed\{([^{}]+)\}(" + IDENT + r")\.s\$[0-9]+\Z")


def local_types(ast):
    """Do not resolve body references, inactive instances or nested typedefs."""
    candidates = defaultdict(list)
    owners = Counter()
    count = 0

    def walk(n, owner=None):
        nonlocal count
        if isinstance(n, list):
            for child in n:
                walk(child, owner)
        elif isinstance(n, dict) and n.get("isUninstantiated") is not True:
            k = n.get("kind")
            if k == "Instance":
                name, body = n.get("name"), n.get("body")
                if not isinstance(name, str) or not isinstance(body, dict):
                    return
                path = f"{owner}.{name}" if owner else name
                owners[path] += 1
                module = body.get("name")
                members = body.get("members", [])
                if body.get("kind") != "InstanceBody" or not isinstance(module, str) or not re.fullmatch(IDENT, module):
                    return
                names = Counter(x.get("name") for x in members if isinstance(x, dict)
                                and x.get("kind") == "TypeAlias" and isinstance(x.get("name"), str))
                addresses = Counter(identity(x) for x in members if isinstance(x, dict))
                for x in members:
                    if not isinstance(x, dict) or x.get("kind") != "TypeAlias":
                        continue
                    count += 1
                    if count > MAX_LOCAL_TYPES:
                        raise Unsupported("local_type_inventory_budget")
                    nm, addr = x.get("name"), identity(x)
                    if (isinstance(nm, str) and re.fullmatch(IDENT, nm) and names[nm] == 1
                            and addr is not None and addresses[addr] == 1):
                        candidates[(path, f"{addr} {module}.{nm}")].append(x)
                walk(members, path)
            elif k in ("Root", "GenerateBlock", "GenerateBlockArray", "Scope"):
                walk(n.get("members"), owner)
    walk(ast.get("design", {}).get("members", []))
    return {k: v[0] for k, v in candidates.items() if len(v) == 1 and owners[k[0]] == 1}


def coordinates(raw):
    t = layout(raw)
    if t is None or t[0] != "logic" or t[2] or not 1 <= len(t[1]) <= 2:
        raise Unsupported("unsupported_packed_field_layout")
    dims = t[1]
    width = 1
    for l, r in dims:
        width *= abs(l-r)+1
        if width > MAX_WIDTH:
            raise Unsupported("packed_field_width_budget")
    # Cartesian product, rightmost packed dimension changes fastest.
    return list(product(*(lane_order(*d) for d in dims)))


def field_layout(raw, owner, types):
    m = TYPE.fullmatch(raw) if isinstance(raw, str) else None
    node = types.get((owner, raw)) if m else None
    if node is None:
        raise Unsupported("unproven_local_typedef_identity")
    target = node.get("target")
    if not isinstance(target, str) or len(target) > 8192:
        raise Unsupported("unsupported_local_struct")
    s = STRUCT.fullmatch(target)
    if s is None or s[2] != m[2] or not s[1].endswith(";"):
        raise Unsupported("unsupported_local_struct")
    parts = s[1][:-1].split(";")
    if not 1 <= len(parts) <= MAX_FIELDS:
        raise Unsupported("local_field_budget")
    result, offset = {}, 0
    for part in reversed(parts):
        pair = part.rsplit(" ", 1)
        if len(pair) != 2 or not re.fullmatch(IDENT, pair[1]) or pair[1] in result:
            raise Unsupported("ambiguous_local_field")
        typ, name = pair
        coords = coordinates(typ)
        result[name] = (typ, coords, offset)
        offset += len(coords)
        if offset > MAX_WIDTH:
            raise Unsupported("packed_struct_width_budget")
    if not any(len(coords[0]) == 2 for _, coords, _ in result.values()):
        raise Unsupported("not_multidimensional_struct")
    return result


def observations(sites, types):
    by_field, by_addr = defaultdict(set), defaultdict(set)
    # Observe direct operands only; not independent declaration binding.
    for owner, _, node in sites:
        for side in ("left", "right"):
            e = node.get(side)
            if not isinstance(e, dict) or e.get("kind") != "MemberAccess":
                continue
            base = e.get("value")
            raw = base.get("type") if isinstance(base, dict) else None
            if not isinstance(raw, str) or (owner, raw) not in types:
                continue
            try:
                addr, name = token(e)
            except Unsupported:
                continue
            by_field[(owner, raw, name)].add(addr)
            by_addr[(owner, addr)].add((raw, name))
    return by_field, by_addr


def expand(node, owner, resolve, declared, types, observed):
    if (node.get("kind") != "Assignment" or node.get("isNonBlocking") is not False
            or node.get("op") is not None or node.get("timingControl") is not None):
        raise Unsupported("not_plain_blocking_assignment")
    lhs, rhs = node.get("left"), node.get("right")
    if not isinstance(lhs, dict) or not isinstance(rhs, dict):
        raise Unsupported("malformed_assignment")
    def named(e):
        if not isinstance(e, dict) or e.get("kind") != "NamedValue":
            raise Unsupported("not_direct_signal")
        raw = e.get("type")
        signal = resolve(e)
        if signal is None or not isinstance(raw, str) or declared.get(signal) != raw:
            raise Unsupported("unproven_signal_identity_or_type")
        return signal, raw

    def member(e):
        signal, raw = named(e.get("value"))
        members = field_layout(raw, owner, types)
        addr, field = token(e)
        by_field, by_addr = observed
        if (by_field.get((owner, raw, field)) != {addr}
                or by_addr.get((owner, addr)) != {(raw, field)}):
            raise Unsupported("inconsistent_observed_member_token")
        if field not in members:
            raise Unsupported("field_not_in_exact_local_type")
        typ, coords, offset = members[field]
        if e.get("type") != typ or node.get("type") != typ or len(coords[0]) != 2:
            raise Unsupported("member_type_disagreement")
        return signal, typ, coords, offset, field

    if lhs.get("kind") == "MemberAccess" and rhs.get("kind") == "UnbasedUnsizedIntegerLiteral":
        target, typ, coords, offset, field = member(lhs)
        value = rhs.get("value")
        # Slang v12.1 prints the elaborated zero in different bases depending
        # on width: fixture 4'b0 / 8'd0, official CSR 128'h0 / 512'h0.
        # Accept only an exact-width, unsigned, known zero in these spellings.
        zeros = {f"{len(coords)}'{radix}0" for radix in ("b", "d", "h")}
        if (rhs.get("type") != typ or not isinstance(value, str) or value not in zeros
                or ("constant" in rhs and rhs["constant"] != value)):
            raise Unsupported("unproven_exact_zero")
        return [], [{"relation": "local_packed_zero_write_candidate", "target": target,
                     "target_bit": offset+i, "field": field, "field_coordinates": list(c),
                     "value": 0} for i, c in enumerate(coords)]
    if lhs.get("kind") == "NamedValue" and rhs.get("kind") == "MemberAccess":
        source, typ, coords, offset, field = member(rhs)
        target, target_type = named(lhs)
        if target_type != typ:
            raise Unsupported("target_type_disagreement")
        return [{"relation": "local_packed_member_read_candidate", "source": source,
                 "source_bit": offset+i, "source_field": field,
                 "source_field_coordinates": list(c), "target": target,
                 "target_packed_offset": i, "target_coordinates": list(c)}
                for i, c in enumerate(coords)], []
    raise Unsupported("unsupported_local_member_assignment")


def audit_local_members(ast, index, *, include_occurrence=False, _shared=None):
    if _shared is None:
        inspect_ast(ast)
    else:
        _shared.check_inputs(ast,index)
    types = local_types(ast)
    resolver = SignalResolver(ast, index) if _shared is None else _shared.resolver
    declared = raw_layouts(index) if _shared is None else _shared.declared
    instances = {i["path"] for i in index["instances"]} if _shared is None else _shared.instances
    # Bounded by inspect_ast and the explicit report row budget.
    sites = list(assignment_sites(ast)) if _shared is None else _shared.sites
    observed = observations(sites, types)
    rows, edges, constants = [], [], []
    for ordinal, (owner, context, node) in (enumerate(sites) if _shared is None else _shared.member_assignments):
        relevant = False
        for side in ("left", "right"):
            e = node.get(side)
            if isinstance(e, dict) and e.get("kind") == "MemberAccess":
                base = e.get("value")
                raw = base.get("type") if isinstance(base, dict) else None
                if isinstance(raw, str) and TYPE.fullmatch(raw):
                    relevant = True
        if not relevant:
            continue
        if len(rows) >= MAX_ROWS:
            raise Unsupported("local_member_row_budget")
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
            local_edges, local_constants = expand(node, owner,
                lambda e: resolver.resolve_exact(owner, e), declared, types, observed)
            if len(edges)+len(constants)+len(local_edges)+len(local_constants) > MAX_POSITIONS:
                raise Unsupported("local_member_position_budget")
        except Unsupported as exc:
            if "budget" in str(exc):
                raise
            row["reason"] = str(exc)
            continue
        row["coverage"] = "position_candidates" if local_edges else "constant_candidates"
        edges.extend({**e, "site_id": row["site_id"]} for e in local_edges)
        constants.extend({**c, "site_id": row["site_id"]} for c in local_constants)
    supported = sum(r["coverage"] != "partial" for r in rows)
    return {"scope": "local_multidimensional_packed_member_sites",
            "counts": {"sites": len(rows), "supported": supported, "partial": len(rows)-supported,
                       "edges": len(edges), "constants": len(constants)},
            "items": rows, "edges": edges, "constants": constants,
            "partial_reasons": dict(Counter(r["reason"] for r in rows if "reason" in r)),
            "design_coverage": "not_measured", "functional_influence": "not_proven",
            "formal_proof": "not_performed",
            "caveat": "Local assignment positions only; packed offsets differ from declared coordinates. "
                      "No independent member-declaration binding, priority, temporal or reachability proof. "
                      "Constants are not edges."}

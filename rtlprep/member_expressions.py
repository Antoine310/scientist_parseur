"""Bounded logical member dependencies and direct member lanes of RHS concatenations.

A logical reference is not a copy/equality edge. Opaque concatenation operands
reserve their proven width but are not analyzed; such rows remain partial.
StructuredAssignmentPattern is inventoried, not expanded.
"""
from collections import Counter

from .aggregate_layout import assignment_sites, member_sites, scalar_vector
from .analysis_budgets import inspect_ast
from .array_dependencies import Unsupported
from .packed_members import fields, integral, token, observed_members
from .symbols import SignalResolver
from .typed_layout import Types, raw_layouts

MAX_NODES = 64
MAX_DEPTH = 8
MAX_OPERANDS = 32
MAX_WIDTH = 1024
MAX_ROWS = 2000
MAX_EDGES = 32768


def expand(node, resolve, declared, types, observed):
    if (node.get("kind") != "Assignment" or node.get("isNonBlocking") is not False
            or node.get("op") is not None or node.get("timingControl") is not None):
        raise Unsupported("not_plain_blocking_assignment")
    lhs, rhs = node.get("left"), node.get("right")
    if not isinstance(lhs, dict) or not isinstance(rhs, dict):
        raise Unsupported("malformed_assignment")

    def named(expr):
        if not isinstance(expr, dict) or expr.get("kind") != "NamedValue":
            raise Unsupported("unsupported_signal_operand")
        signal = resolve(expr)
        raw = expr.get("type")
        if signal is None or not isinstance(raw, str) or declared.get(signal) != raw:
            raise Unsupported("unproven_signal_identity_or_type")
        return signal, raw

    target, target_type = named(lhs)
    state, dst = scalar_vector(target_type)
    if state != "logic" or node.get("type") != target_type or rhs.get("type") != target_type:
        raise Unsupported("assignment_type_disagreement")

    def member(expr):
        if not isinstance(expr, dict) or expr.get("kind") != "MemberAccess":
            raise Unsupported("unsupported_member_operand")
        source, raw = named(expr.get("value"))
        s, members = fields(raw, types)
        addr, field = token(expr)
        by_field, by_addr = observed
        if by_field.get((raw, field)) != {addr} or by_addr.get(addr) != {(raw, field)}:
            raise Unsupported("inconsistent_observed_member_token")
        if field not in members:
            raise Unsupported("field_not_in_exact_type")
        typ, bits, offset = members[field]
        if s != "logic" or expr.get("type") != typ:
            raise Unsupported("member_type_disagreement")
        return [(source, offset+i, field, bit) for i, bit in enumerate(bits)]

    def edge(lane, bit, relation):
        source, offset, field, field_bit = lane
        return {"source":source,"source_bit":offset,"source_field":field,
                "source_field_bit":field_bit,"target":target,"target_bit":bit,
                "relation":relation}

    if rhs.get("kind") == "Concatenation":
        operands = rhs.get("operands")
        if not isinstance(operands, list) or not 1 <= len(operands) <= MAX_OPERANDS:
            raise Unsupported("concat_operand_shape_or_budget")
        at = 0
        edges, gaps = [], []
        for expr in reversed(operands):
            if not isinstance(expr, dict):
                raise Unsupported("malformed_concat_operand")
            s, bits = integral(expr.get("type"), types)
            width = len(bits)
            if s not in ("logic", "bit") or at+width > MAX_WIDTH or at+width > len(dst):
                raise Unsupported("concat_width_disagreement")
            if expr.get("kind") == "MemberAccess":
                lanes = member(expr)
                if len(lanes) != width or s != state:
                    raise Unsupported("member_width_disagreement")
                edges.extend(edge(lane,dst[at+i],"concat_member_position_candidate")
                             for i,lane in enumerate(lanes))
            else:
                # Width contributes to the position but no value/dependency
                # assertion is made for the opaque operand.
                gaps.append({"kind":expr.get("kind"),"target_bits":dst[at:at+width]})
            at += width
        if at != len(dst) or not edges:
            raise Unsupported("concat_width_or_member_disagreement")
        return edges, gaps

    if target_type != "logic" or dst != [0]:
        raise Unsupported("not_scalar_logic_assignment")
    seen = 0
    def logical(expr, depth):
        nonlocal seen
        seen += 1
        if seen > MAX_NODES or depth > MAX_DEPTH:
            raise Unsupported("logical_expression_budget")
        if not isinstance(expr, dict) or expr.get("type") != "logic":
            raise Unsupported("not_scalar_logic_operand")
        kind = expr.get("kind")
        if kind == "MemberAccess":
            lanes = member(expr)
            if len(lanes) != 1:
                raise Unsupported("not_scalar_member")
            return lanes
        if kind == "BinaryOp" and expr.get("op") == "LogicalAnd":
            return logical(expr.get("left"),depth+1)+logical(expr.get("right"),depth+1)
        if kind == "UnaryOp" and expr.get("op") == "LogicalNot":
            return logical(expr.get("operand"),depth+1)
        raise Unsupported("unsupported_logical_operator")
    lanes = logical(rhs,0)
    # Repeated references are one structural candidate, not a proof of influence.
    return [edge(lane,0,"logical_member_reference_candidate") for lane in sorted(set(lanes))], []


def audit_member_expressions(ast,index, *, include_occurrence=False):
    inspect_ast(ast)
    types=Types(ast)
    if types.truncated:
        raise Unsupported("package_inventory_budget")
    observed=observed_members(ast,types)
    resolver=SignalResolver(ast,index)
    declared=raw_layouts(index)
    instances={i["path"] for i in index["instances"]}
    rows,edges=[],[]
    for ordinal, (owner, context, node) in enumerate(assignment_sites(ast)):
        rhs=node.get("right")
        if not isinstance(rhs,dict) or rhs.get("kind") not in (
            "Concatenation","BinaryOp","UnaryOp","StructuredAssignmentPattern"):
            continue
        if not member_sites(rhs):
            continue
        if len(rows)>=MAX_ROWS:
            raise Unsupported("expression_row_budget")
        row={"site_id":len(rows),"instance":owner,"context":context,"kind":rhs["kind"],
             "source":{"file":node.get("source_file_start") or node.get("source_file"),
                       "line":node.get("source_line_start") or node.get("source_line")},
             "coverage":"partial","edge_count":0}
        if include_occurrence:
            row["occurrence_ordinal"] = ordinal
        rows.append(row)
        try:
            if rhs["kind"]=="StructuredAssignmentPattern":
                raise Unsupported("structured_pattern_temporal_not_proven")
            if owner not in instances or context not in ("continuous","AlwaysComb"):
                raise Unsupported("unsupported_assignment_context")
            local,gaps=expand(node,lambda e:resolver.resolve_exact(owner,e),declared,types,observed)
            if len(edges)+len(local)>MAX_EDGES:
                raise Unsupported("expression_edge_budget")
        except Unsupported as exc:
            if "budget" in str(exc):
                raise
            row["reason"]=str(exc)
            continue
        row.update(coverage="partial_positions" if gaps else "expression_candidates",
                   edge_count=len(local),unmodeled_operands=gaps)
        if gaps:
            row["reason"]="opaque_concat_operands"
        edges.extend({**e,"site_id":row["site_id"]} for e in local)
    counts=Counter(r["coverage"] for r in rows)
    return {"scope":"member_logic_and_rhs_concat_positions",
            "counts":{"sites":len(rows),"supported":counts["expression_candidates"],
                      "partial_with_positions":counts["partial_positions"],
                      "partial_without_positions":counts["partial"],"edges":len(edges),
                      "logical_references":sum(e["relation"]=="logical_member_reference_candidate" for e in edges),
                      "concat_positions":sum(e["relation"]=="concat_member_position_candidate" for e in edges)},
            "items":rows,"edges":edges,"partial_reasons":dict(Counter(r["reason"] for r in rows if "reason" in r)),
            "design_coverage":"not_measured","functional_influence":"not_proven","formal_proof":"not_performed",
            "caveat":"Logical references are structural, not positional equality or functional influence. "
                     "Opaque concat operands reserve widths only; partial rows are not full support. "
                     "PR79 field binding limitation remains; no temporal or priority proof."}

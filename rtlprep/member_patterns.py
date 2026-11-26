"""Assignment-local NBA struct setters and literal concat lanes.

NBA candidates describe sampled RHS values when the statement executes,
not a clock-to-clock graph, reachability or last-writer proof.
"""
from collections import Counter
import re

from .aggregate_layout import assignment_sites, member_sites, scalar_vector
from .analysis_budgets import inspect_ast
from .array_dependencies import Unsupported
from .packed_members import fields, token, observed_members, integral
from .enum_member_writes import enum_for, value_bits
from .symbols import SignalResolver
from .typed_layout import Types, raw_layouts

MAX_ROWS=2000
MAX_POSITIONS=32768
MAX_WIDTH=1024
MAX_OPERANDS=32


def binary_literal(expr, typ):
    if not isinstance(expr, dict) or expr.get("kind")!="IntegerLiteral" or expr.get("type")!=typ:
        raise Unsupported("unproven_literal")
    state,bits=scalar_vector(typ)
    width=len(bits)
    if state!="bit" or not 1<=width<=MAX_WIDTH or typ!=f"bit[{width-1}:0]":
        raise Unsupported("unproven_literal_type")
    value=expr.get("value")
    if not isinstance(value,str) or len(value)>MAX_WIDTH+8:
        raise Unsupported("unproven_literal_value")
    m=re.fullmatch(r"([1-9][0-9]{0,3})'([bdh])([0-9a-f]+)",value)
    if m is None or int(m[1])!=width:
        raise Unsupported("unproven_literal_value")
    radix={"b":2,"d":10,"h":16}[m[2]]
    try:
        number=int(m[3],radix)
    except ValueError as exc:
        raise Unsupported("unproven_literal_value") from exc
    if number.bit_length()>width or ("constant" in expr and expr["constant"]!=value):
        raise Unsupported("literal_width_or_tag_disagreement")
    return [(number>>i)&1 for i in range(width)]


def scalar_constant(expr):
    if (not isinstance(expr,dict) or expr.get("kind")!="Conversion"
            or expr.get("type")!="logic"):
        raise Unsupported("unproven_scalar_conversion")
    op=expr.get("operand")
    vals=binary_literal(op,"bit[0:0]")
    if "constant" in expr and expr["constant"]!=op["value"]:
        raise Unsupported("literal_tag_disagreement")
    return vals


def expand(node,context,resolve,declared,types,observed):
    if (node.get("kind")!="Assignment" or node.get("op") is not None
            or node.get("timingControl") is not None):
        raise Unsupported("unsupported_assignment")
    lhs,rhs=node.get("left"),node.get("right")
    if not isinstance(lhs,dict) or not isinstance(rhs,dict):
        raise Unsupported("malformed_assignment")

    def named(e):
        if not isinstance(e,dict) or e.get("kind")!="NamedValue":
            raise Unsupported("not_direct_signal")
        raw=e.get("type")
        signal=resolve(e)
        if not isinstance(raw,str) or signal is None or declared.get(signal)!=raw:
            raise Unsupported("unproven_signal_identity")
        return signal,raw

    target,raw=named(lhs)
    if node.get("type")!=raw or rhs.get("type")!=raw:
        raise Unsupported("assignment_type_disagreement")
    by_field,by_addr=observed
    def check_token(t,e):
        addr,name=token(e)
        if by_field.get((t,name))!={addr} or by_addr.get(addr)!={(t,name)}:
            raise Unsupported("unproven_setter_or_member_token")
        return name

    if rhs.get("kind")=="StructuredAssignmentPattern":
        if context!="AlwaysFF" or node.get("isNonBlocking") is not True:
            raise Unsupported("not_alwaysff_nba")
        state,members=fields(raw,types)
        setters=rhs.get("memberSetters")
        if state!="logic" or not isinstance(setters,list) or len(setters)!=len(members):
            raise Unsupported("incomplete_pattern")
        seen=set()
        edges,constants=[],[]
        for setter in setters:
            if not isinstance(setter,dict):
                raise Unsupported("malformed_setter")
            name=check_token(raw,setter)
            if name not in members or name in seen:
                raise Unsupported("duplicate_or_unknown_setter")
            seen.add(name)
            typ,bits,offset=members[name]
            expr=setter.get("expr")
            if not isinstance(expr,dict):
                raise Unsupported("malformed_setter_expression")
            if expr.get("kind")=="MemberAccess":
                source,sraw=named(expr.get("value"))
                s,sfields=fields(sraw,types)
                field=check_token(sraw,expr)
                if sraw!=raw or field not in sfields:
                    raise Unsupported("source_struct_disagreement")
                st,sbits,soffset=sfields[field]
                if s!=state or st!=typ or sbits!=bits or expr.get("type")!=typ:
                    raise Unsupported("source_field_disagreement")
                edges.extend({"relation":"nba_sampled_member_candidate","source":source,
                              "source_bit":soffset+i,"source_field":field,"target":target,
                              "target_bit":offset+i,"target_field":name}
                             for i in range(len(bits)))
            else:
                enum=enum_for(typ,types)
                if enum is not None:
                    _,vals=value_bits(expr,*enum,resolve)
                elif typ=="logic" and bits==[0]:
                    vals=scalar_constant(expr)
                else:
                    raise Unsupported("unsupported_setter_expression")
                if len(vals)!=len(bits):
                    raise Unsupported("setter_width_disagreement")
                constants.extend({"relation":"nba_local_constant_candidate","target":target,
                                  "target_bit":offset+i,"target_field":name,"value":v}
                                 for i,v in enumerate(vals))
        if seen!=set(members):
            raise Unsupported("incomplete_pattern")
        return "nba",edges,constants,[]

    if (rhs.get("kind")!="Concatenation" or context not in ("continuous","AlwaysComb")
            or node.get("isNonBlocking") is not False):
        raise Unsupported("unsupported_concat_context")
    state,dst=scalar_vector(raw)
    operands=rhs.get("operands")
    if state!="logic" or not isinstance(operands,list) or not 1<=len(operands)<=MAX_OPERANDS:
        raise Unsupported("unproven_concat_shape")
    at=0
    constants,gaps=[],[]
    for e in reversed(operands):
        if not isinstance(e,dict):
            raise Unsupported("malformed_concat_operand")
        s,bits=integral(e.get("type"),types)
        width=len(bits)
        if s not in ("logic","bit") or at+width>min(MAX_WIDTH,len(dst)):
            raise Unsupported("concat_width_disagreement")
        if e.get("kind")=="IntegerLiteral":
            vals=binary_literal(e,e.get("type"))
            constants.extend({"relation":"concat_literal_position_candidate","target":target,
                              "target_bit":dst[at+i],"value":v} for i,v in enumerate(vals))
        else:
            gaps.append({"kind":e.get("kind"),"target_bits":dst[at:at+width]})
        at+=width
    if at!=len(dst) or not constants:
        raise Unsupported("concat_width_or_literal_disagreement")
    return "concat",[],constants,gaps


def audit_patterns(ast,index):
    inspect_ast(ast)
    types=Types(ast)
    if types.truncated:
        raise Unsupported("package_inventory_budget")
    observed=observed_members(ast,types)
    resolver=SignalResolver(ast,index)
    declared=raw_layouts(index)
    instances={i["path"] for i in index["instances"]}
    rows,edges,constants=[],[],[]
    for owner,context,node in assignment_sites(ast):
        rhs=node.get("right")
        if not isinstance(rhs,dict) or rhs.get("kind") not in ("StructuredAssignmentPattern","Concatenation") or not member_sites(rhs):
            continue
        if len(rows)>=MAX_ROWS:
            raise Unsupported("pattern_row_budget")
        row={"site_id":len(rows),"instance":owner,"context":context,"kind":rhs["kind"],
             "source":{"file":node.get("source_file_start") or node.get("source_file"),
                       "line":node.get("source_line_start") or node.get("source_line")},
             "coverage":"partial"}
        rows.append(row)
        try:
            if owner not in instances:
                raise Unsupported("unproven_instance")
            kind,e,c,gaps=expand(node,context,lambda e:resolver.resolve_exact(owner,e),declared,types,observed)
            if len(edges)+len(constants)+len(e)+len(c)>MAX_POSITIONS:
                raise Unsupported("pattern_position_budget")
        except Unsupported as exc:
            if "budget" in str(exc):
                raise
            row["reason"]=str(exc)
            continue
        row.update(coverage="nba_assignment_candidates" if kind=="nba" else "partial_literal_positions",
                   unmodeled_operands=gaps,edge_count=len(e),constant_count=len(c))
        edges.extend({**x,"site_id":row["site_id"]} for x in e)
        constants.extend({**x,"site_id":row["site_id"]} for x in c)
    counts=Counter(r["coverage"] for r in rows)
    return {"scope":"member_nba_patterns_and_concat_literals",
            "counts":{"sites":len(rows),"nba_sites":counts["nba_assignment_candidates"],
                      "concat_partial_sites":counts["partial_literal_positions"],
                      "unmodeled_sites":counts["partial"],"nba_sampled_edges":len(edges),
                      "nba_constants":sum(c["relation"]=="nba_local_constant_candidate" for c in constants),
                      "concat_constants":sum(c["relation"]=="concat_literal_position_candidate" for c in constants)},
            "items":rows,"edges":edges,"constants":constants,
            "partial_reasons":dict(Counter(r["reason"] for r in rows if "reason" in r)),
            "design_coverage":"not_measured","functional_influence":"not_proven","formal_proof":"not_performed",
            "caveat":"NBA candidates apply only when this statement executes, not a global next-state or clock-domain proof. "
                     "No guard, priority, last-writer or independent field declaration binding proof. "
                     "Concat nonliteral lanes remain opaque in this report."}

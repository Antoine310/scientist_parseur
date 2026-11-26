"""Configuration-local conditional concat constants.

Prove the known two-valued parameter guard from direct elaborated instance
declarations and their initializer chains, never from expression constant tags
alone. Only the selected branch is evaluated. No general four-state folding,
runtime guard, priority or whole-design proof.
"""
from collections import Counter, defaultdict
import re

from .aggregate_layout import assignment_sites, member_sites, scalar_vector
from .analysis_budgets import inspect_ast
from .array_dependencies import Unsupported
from .packed_members import integral
from .enum_member_writes import enum_for, value_bits
from .member_patterns import binary_literal
from .symbols import SignalResolver
from .typed_layout import Types, raw_layouts, identity

PARAM_TYPE="logic signed[31:0]"
TOKEN=re.compile(r"([0-9]{1,32}) ([A-Za-z_$][A-Za-z0-9_$]*)\Z")
MAX_PARAMS=16384
MAX_DEPTH=16
MAX_ROWS=2000
MAX_POSITIONS=32768
MAX_WIDTH=1024


def parameter_inventory(ast):
    candidates=defaultdict(list)
    owners=Counter()
    count=0

    def walk(n,owner=None):
        nonlocal count
        if isinstance(n,list):
            for child in n:
                walk(child,owner)
        elif isinstance(n,dict) and n.get("isUninstantiated") is not True:
            kind=n.get("kind")
            if kind=="Instance":
                name,body=n.get("name"),n.get("body")
                if not isinstance(name,str) or not isinstance(body,dict) or body.get("kind")!="InstanceBody":
                    return
                path=f"{owner}.{name}" if owner else name
                owners[path]+=1
                members=body.get("members",[])
                addresses=Counter(identity(x) for x in members if isinstance(x,dict))
                names=Counter(x.get("name") for x in members if isinstance(x,dict) and x.get("kind")=="Parameter" and isinstance(x.get("name"),str))
                for p in members:
                    if not isinstance(p,dict) or p.get("kind")!="Parameter":
                        continue
                    count+=1
                    if count>MAX_PARAMS:
                        raise Unsupported("parameter_inventory_budget")
                    addr,name=identity(p),p.get("name")
                    if (addr is not None and addresses[addr]==1 and isinstance(name,str)
                            and names[name]==1 and TOKEN.fullmatch(f"{addr} {name}")):
                        candidates[(path,f"{addr} {name}")].append(p)
                walk(members,path)
            elif kind in ("Root","GenerateBlock","GenerateBlockArray","Scope"):
                walk(n.get("members"),owner)
    walk(ast.get("design",{}).get("members",[]))
    return {k:v[0] for k,v in candidates.items() if len(v)==1 and owners[k[0]]==1}


def agree(node,value):
    if "constant" in node and node["constant"]!=value:
        raise Unsupported("constant_tag_disagreement")


def parameter_value(expr,owner,params,resolve,proofs,seen=None,depth=0):
    if depth>MAX_DEPTH:
        raise Unsupported("parameter_chain_budget")
    if not isinstance(expr,dict) or expr.get("type")!=PARAM_TYPE:
        raise Unsupported("unsupported_parameter_type")
    if expr.get("kind")=="Conversion":
        op=expr.get("operand")
        if (not isinstance(op,dict) or op.get("kind")!="IntegerLiteral" or op.get("type")!="int"
                or op.get("value") not in ("0","1")):
            raise Unsupported("unsupported_parameter_literal")
        value=op["value"]
        agree(op,value)
        agree(expr,value)
        return int(value)
    if expr.get("kind")!="NamedValue" or resolve(owner,expr) is not None:
        raise Unsupported("not_parameter_reference")
    raw=expr.get("symbol")
    if not isinstance(raw,str) or not TOKEN.fullmatch(raw):
        raise Unsupported("malformed_parameter_reference")
    key=(owner,raw)
    p=params.get(key)
    if p is None or p.get("type")!=PARAM_TYPE or p.get("value") not in ("0","1"):
        raise Unsupported("unproven_parameter_declaration")
    seen=set() if seen is None else seen
    if key in seen:
        raise Unsupported("parameter_chain_cycle")
    init=p.get("initializer")
    if not isinstance(init,dict):
        raise Unsupported("missing_parameter_initializer")
    if init.get("kind")=="NamedValue":
        # Port bindings refer to the immediate parent, not another instance.
        if p.get("isPort") is not True or "." not in owner:
            raise Unsupported("unsupported_parameter_binding")
        parent=owner.rsplit(".",1)[0]
    else:
        parent=owner
    value=parameter_value(init,parent,params,resolve,proofs,seen|{key},depth+1)
    if p["value"]!=str(value):
        raise Unsupported("parameter_initializer_disagreement")
    agree(expr,str(value))
    proofs[(owner,p["name"])]=value
    return value


def guard(expr,owner,params,resolve,proofs,depth=0):
    if depth>MAX_DEPTH:
        raise Unsupported("guard_budget")
    if not isinstance(expr,dict) or expr.get("type")!="logic" or expr.get("kind")!="BinaryOp":
        raise Unsupported("unsupported_guard")
    if expr.get("op")=="Equality":
        v=parameter_value(expr.get("left"),owner,params,resolve,proofs)==parameter_value(
            expr.get("right"),owner,params,resolve,proofs)
    elif expr.get("op")=="LogicalAnd":
        # Both operands must be independently known; do not assume short circuit
        # eliminates unknown or runtime expressions.
        a=guard(expr.get("left"),owner,params,resolve,proofs,depth+1)
        b=guard(expr.get("right"),owner,params,resolve,proofs,depth+1)
        v=a and b
    else:
        raise Unsupported("unsupported_guard_operator")
    agree(expr,f"1'b{int(v)}")
    return v


def conditional_constant(expr,owner,params,resolve,types):
    if not isinstance(expr,dict) or expr.get("kind")!="ConditionalOp":
        raise Unsupported("not_conditional_operand")
    raw=expr.get("type")
    s,bits=integral(raw,types)
    if s!="logic":
        raise Unsupported("unsupported_conditional_type")
    conditions=expr.get("conditions")
    if not isinstance(conditions,list) or len(conditions)!=1 or not isinstance(conditions[0],dict) or set(conditions[0])!={"expr"}:
        raise Unsupported("unsupported_condition_shape")
    proofs={}
    chosen=guard(conditions[0]["expr"],owner,params,resolve,proofs)
    left,right=expr.get("left"),expr.get("right")
    enum=enum_for(raw,types)
    permitted={raw,enum[0]} if enum else {raw}
    if any(not isinstance(e,dict) or e.get("type") not in permitted for e in (left,right)):
        raise Unsupported("conditional_branch_type_disagreement")
    selected=left if chosen else right
    if enum:
        _,values=value_bits(selected,*enum,lambda e:resolve(owner,e))
        tag=selected.get("constant")
    elif raw==f"logic[{len(bits)-1}:0]" and selected.get("kind")=="Conversion":
        inner=selected.get("operand")
        values=binary_literal(inner,f"bit[{len(bits)-1}:0]")
        agree(selected,inner["value"])
        tag=inner["value"]
    else:
        raise Unsupported("selected_branch_not_proven_constant")
    if len(values)!=len(bits):
        raise Unsupported("conditional_width_disagreement")
    if "constant" in expr:
        if tag is None or expr["constant"]!=tag:
            raise Unsupported("conditional_tag_disagreement")
    return values,{"guard_value":int(chosen),"selected_branch":"left" if chosen else "right",
                   "parameters":[{"instance":p,"name":n,"value":v} for (p,n),v in sorted(proofs.items())]}


def audit_conditional_concat(ast,index, *, include_occurrence=False):
    inspect_ast(ast)
    types=Types(ast)
    if types.truncated:
        raise Unsupported("package_inventory_budget")
    params=parameter_inventory(ast)
    resolver=SignalResolver(ast,index)
    declared=raw_layouts(index)
    instances={i["path"] for i in index["instances"]}
    rows,constants=[],[]
    for ordinal, (owner, context, node) in enumerate(assignment_sites(ast)):
        rhs=node.get("right")
        if not isinstance(rhs,dict) or rhs.get("kind")!="Concatenation" or not member_sites(rhs):
            continue
        operands=rhs.get("operands")
        if not isinstance(operands,list) or not any(isinstance(e,dict) and e.get("kind")=="ConditionalOp" for e in operands):
            continue
        if len(rows)>=MAX_ROWS:
            raise Unsupported("conditional_row_budget")
        row={"site_id":len(rows),"instance":owner,"context":context,
             "source":{"file":node.get("source_file_start") or node.get("source_file"),
                       "line":node.get("source_line_start") or node.get("source_line")},
             "coverage":"partial","conditional_operands":[]}
        if include_occurrence:
            row["occurrence_ordinal"] = ordinal
        rows.append(row)
        try:
            lhs=node.get("left")
            if (owner not in instances or context not in ("continuous","AlwaysComb")
                    or node.get("isNonBlocking") is not False or node.get("op") is not None
                    or node.get("timingControl") is not None or not isinstance(lhs,dict)
                    or lhs.get("kind")!="NamedValue" or not 1<=len(operands)<=32):
                raise Unsupported("unsupported_assignment")
            target=resolver.resolve_exact(owner,lhs)
            raw=lhs.get("type")
            if target is None or not isinstance(raw,str) or declared.get(target)!=raw or node.get("type")!=raw or rhs.get("type")!=raw:
                raise Unsupported("unproven_target")
            state,dst=scalar_vector(raw)
            if state!="logic" or len(dst)>MAX_WIDTH:
                raise Unsupported("unsupported_target_layout")
            at=0
            lanes=[]
            for e in reversed(operands):
                if not isinstance(e,dict):
                    raise Unsupported("malformed_operand")
                s,bits=integral(e.get("type"),types)
                if s not in ("logic","bit") or at+len(bits)>len(dst):
                    raise Unsupported("concat_width_disagreement")
                if e.get("kind")=="ConditionalOp":
                    lanes.append((e,dst[at:at+len(bits)]))
                at+=len(bits)
            if at!=len(dst):
                raise Unsupported("concat_width_disagreement")
            local=[]
            for e,bits in lanes:
                item={"target_bits":bits,"coverage":"partial"}
                row["conditional_operands"].append(item)
                try:
                    vals,proof=conditional_constant(e,owner,params,resolver.resolve_exact,types)
                    if len(vals)!=len(bits):
                        raise Unsupported("conditional_width_disagreement")
                except Unsupported as exc:
                    if "budget" in str(exc):
                        raise
                    item["reason"]=str(exc)
                    continue
                item.update(coverage="configuration_constant",proof=proof)
                local.extend({"site_id":row["site_id"],"relation":"configuration_conditional_constant_candidate",
                              "target":target,"target_bit":bit,"value":v}
                             for bit,v in zip(bits,vals))
            if len(constants)+len(local)>MAX_POSITIONS:
                raise Unsupported("conditional_position_budget")
            constants.extend(local)
            if all(x["coverage"]=="configuration_constant" for x in row["conditional_operands"]):
                row["coverage"]="all_conditional_operands_resolved"
            elif local:
                row["coverage"]="partial_conditional_positions"
        except Unsupported as exc:
            if "budget" in str(exc):
                raise
            row["reason"]=str(exc)
    counts=Counter(r["coverage"] for r in rows)
    return {"scope":"configuration_conditional_concat_constants",
            "counts":{"sites":len(rows),"conditional_sites_resolved":counts["all_conditional_operands_resolved"],
                      "partial_sites":len(rows)-counts["all_conditional_operands_resolved"],
                      "conditional_operands":sum(len(r["conditional_operands"]) for r in rows),
                      "resolved_operands":sum(x["coverage"]=="configuration_constant" for r in rows for x in r["conditional_operands"]),
                      "constants":len(constants),"edges":0},
            "items":rows,"constants":constants,"edges":[],
            "design_coverage":"not_measured","functional_influence":"not_proven","formal_proof":"not_performed",
            "caveat":"Only selected constants under independently checked known parameter bindings in this elaboration. "
                     "No general X/Z or runtime guard evaluation, no execution/priority or global value proof."}

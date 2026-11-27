"""PR106: separate, conservative scalar-concat NBA statement candidates.

No historical row ID is invented for refused targets. No clock, guard,
writer priority, reset, initial-state, or complete transition inference.
"""
from collections import Counter
import re
from .bit_widths import integral_shape, width
from .symbols import SignalResolver
from .typed_layout import raw_layouts
from .walker_exclusion_audit import audit_walker, ancestors

MAX_OPERANDS=32
MAX_ROWS=20000
MAX_RECORDS=32768


class Refusal(ValueError):
    pass


def require(test,reason):
    if not test:
        raise Refusal(reason)


def shape(node):
    return integral_shape(node.get("type")) if isinstance(node,dict) else None


def scalar(node,resolve,declared,variables,nodes,*,target=False):
    require(isinstance(node,dict) and node.get("kind")=="NamedValue","unsupported_scalar_operand")
    typ=node.get("type")
    require(typ in ("reg","logic"),"unproven_four_state_scalar")
    sig=resolve(node)
    require(isinstance(sig,str) and sig in nodes and declared.get(sig)==typ,"unproven_symbol_or_type")
    require(not target or sig in variables,"target_not_indexed_variable")
    return sig


def concat(node):
    require(isinstance(node,dict) and node.get("kind")=="Concatenation","expected_concatenation")
    operands=node.get("operands")
    require(isinstance(operands,list) and 2<=len(operands)<=MAX_OPERANDS,"concat_operand_budget_or_arity")
    require(shape(node)==(len(operands)-1,0,False,True),"concat_type_width_mismatch")
    return operands


def zero_rhs(rhs,n):
    expected=(n-1,0,False,True)
    require(shape(rhs)==expected,"rhs_width_or_type_mismatch")
    literal=rhs
    if rhs.get("kind")=="Conversion":
        literal=rhs.get("operand")
        require(shape(literal) in (expected,(n-1,0,False,False)),"zero_conversion_width_or_signedness")
    require(isinstance(literal,dict) and literal.get("kind")=="IntegerLiteral","unsupported_rhs_expression")
    raw=literal.get("value")
    require(isinstance(raw,str) and len(raw)<=128 and re.fullmatch(str(n)+r"'[bB]0+",raw) is not None,
            "literal_not_proven_binary_zero")
    require(len(raw.split("'")[1][1:])<=n,"literal_width_mismatch")
    for obj in (rhs,literal):
        if "constant" in obj:
            require(obj["constant"]==raw,"constant_serialization_disagreement")
    return [None]*n


def expand(node,context,resolve,declared,variables,nodes):
    require(context in ("Always","AlwaysFF") and isinstance(node,dict) and node.get("kind")=="Assignment"
            and node.get("isNonBlocking") is True and node.get("op") is None
            and node.get("timingControl") is None,"unproven_nba_statement")
    lhs=node.get("left")
    rhs=node.get("right")
    targets=[scalar(x,resolve,declared,variables,nodes,target=True) for x in concat(lhs)]
    n=len(targets)
    require(len(set(targets))==n,"overlapping_target_symbols")
    require(shape(node)==shape(lhs) and shape(rhs)==shape(lhs),"assignment_type_width_mismatch")
    if rhs.get("kind")=="Concatenation":
        sources=[scalar(x,resolve,declared,variables,nodes) for x in concat(rhs)]
        require(len(sources)==n,"rhs_width_mismatch")
    else:
        sources=zero_rhs(rhs,n)
    records=[]
    for pos,(dst,src) in enumerate(zip(reversed(targets),reversed(sources))):
        row={"concat_lsb_position":pos,"target":{"signal":dst,"bit":0}}
        if src is None:
            row.update(relation="nba_constant_zero_candidate",constant=0,source=None)
        else:
            row.update(relation="nba_sampled_position_candidate",source={"signal":src,"bit":0},constant=None)
        records.append(row)
    return records


def audit_concat_targets(ast,index,graph):
    prior=audit_walker(ast,index,graph)
    resolver=SignalResolver(ast,index)
    declared=raw_layouts(index)
    variables={s.get("path") or s["instance_path"]+"."+s["name"] for s in index["signals"] if s.get("kind")=="Variable"}
    nodes=set(graph["nodes"])
    items=[]
    other=[]
    counts=Counter()
    total=0
    for row in prior["unsupported_targets"]:
        if row["lhs_kind"]!="Concatenation":
            other.append(row)
            continue
        if len(items)>=MAX_ROWS:
            raise ValueError("concat_target_row_budget")
        node=ancestors(ast,row["ast_path"])[-1][1]
        owner=row["instance"]
        item={"ast_path":row["ast_path"],"instance":owner,"source_location":row["source"],
              "context":row["context"],"historical_flat_assignment_id":None}
        try:
            records=expand(node,row["context"],lambda n:resolver.resolve_exact(owner,n),declared,variables,nodes)
        except Refusal as exc:
            item.update(coverage="partial",reason=str(exc),records=[])
            counts["partial"]+=1
        else:
            total+=len(records)
            if total>MAX_RECORDS:
                raise ValueError("concat_target_record_budget")
            item.update(coverage="scalar_concat_nba_candidates",records=records)
            counts["supported"]+=1
            counts.update(x["relation"] for x in records)
        items.append(item)
    if len(items)+len(other)!=len(prior["unsupported_targets"]):
        raise ValueError("concat_target_partition_disagreement")
    return {"schema_version":1,"scope":"historically_refused_scalar_concatenation_nba_targets",
            "counts":{"historical_unsupported_targets":len(prior["unsupported_targets"]),
                      "concat_sites":len(items),"supported":counts["supported"],"partial":counts["partial"],
                      "other_unsupported_targets":len(other),"records":total,
                      "sampled":counts["nba_sampled_position_candidate"],
                      "constant_zero":counts["nba_constant_zero_candidate"]},
            "items":items,"other_unsupported_targets":other,"historical_replay_exact":True,
            "historical_graph_promoted":False,"new_historical_edges":0,
            "design_coverage":"not_measured","functional_influence":"not_proven",
            "caveat":"Statement-local sampled RHS or literal zero only; no event, guard, priority, initial-state, CDC, global transition or RTL equivalence proof."}

"""PR110: local zero-valued blocking assignments in direct Initial bodies.

A startup assignment is not a permanent constant or a global initial-state
constraint. No declaration initializers, scheduler, races or synthesis claims.
"""
from collections import Counter
import re
from .bit_widths import integral_shape,width
from .concat_nba_targets import Refusal,require
from .generate_nba_targets import named
from .symbols import SignalResolver
from .typed_layout import raw_layouts
from .walker_exclusion_audit import audit_walker,ancestors

MAX_ROWS=20000
MAX_RECORDS=32768
MAX_CONVERSIONS=4


def zero_shape(node):
    typ=node.get("type") if isinstance(node,dict) else None
    require(isinstance(typ,str) and (typ in ("int","logic signed[31:0]") or
            re.fullmatch(r"(?:reg|logic|bit)(?:\[[0-9]{1,5}:[0-9]{1,5}\])?",typ) is not None),
            "unproven_zero_integral_type")
    layout=integral_shape(typ)
    require(layout is not None and width(layout)<=32,"zero_width_budget_or_layout")
    return layout


def serialized_zero(value,layout,typ):
    if value=="0":
        return typ in ("int","logic signed[31:0]")
    if not isinstance(value,str) or len(value)>64:
        return False
    m=re.fullmatch(r"([1-9][0-9]?)'[bBdDhHoO](0+)",value)
    if m is None:
        return False
    return int(m[1])==width(layout) and len(m[2])<=width(layout)


def prove_zero(node,depth=0):
    layout=zero_shape(node)
    typ=node["type"]
    require(depth<=MAX_CONVERSIONS,"zero_conversion_depth_budget")
    kind=node.get("kind")
    if kind=="IntegerLiteral":
        value=node.get("value")
        require(serialized_zero(value,layout,typ),"not_explicit_binary_defined_zero")
        require("constant" not in node or serialized_zero(node["constant"],layout,typ),
                "zero_constant_disagreement")
    elif kind=="Conversion":
        prove_zero(node.get("operand"),depth+1)
        # Defined zero remains zero through integral resizing, sign and state
        # conversion. Do not infer any general conversion semantics.
        require("constant" not in node or serialized_zero(node["constant"],layout,typ),
                "zero_conversion_constant_disagreement")
    else:
        raise Refusal("not_literal_or_zero_conversion")
    return layout


def expand(node,boundary,owner,resolve,declared,variables,nodes):
    require(isinstance(boundary,dict) and boundary.get("kind")=="ProceduralBlock"
            and boundary.get("procedureKind")=="Initial","not_initial_procedure")
    body=boundary.get("body")
    require(isinstance(body,dict) and body.get("kind")=="ExpressionStatement"
            and body.get("expr") is node,"not_direct_initial_assignment")
    require(isinstance(node,dict) and node.get("kind")=="Assignment"
            and node.get("isNonBlocking") is False and node.get("op") is None
            and node.get("timingControl") is None,"not_plain_blocking_initial_assignment")
    target,dst=named(node.get("left"),resolve,declared,nodes)
    require(target in variables and target.startswith(owner+".") and target.rsplit(".",1)[0]==owner,
            "unproven_direct_variable_target")
    rhs=node.get("right")
    require(zero_shape(node)==dst and zero_shape(rhs)==dst,"initial_assignment_type_disagreement")
    prove_zero(rhs)
    return [{"relation":"initial_zero_assignment_candidate","target":{"signal":target,"bit":i},
             "value":0,"lifetime":"statement_local_startup_only"} for i in range(dst[1],dst[0]+1)]


def audit_initial_zero(ast,index,graph):
    prior=audit_walker(ast,index,graph)
    resolver=SignalResolver(ast,index)
    declared=raw_layouts(index)
    variables={s.get("path") or s["instance_path"]+"."+s["name"] for s in index["signals"] if s.get("kind")=="Variable"}
    nodes=set(graph["nodes"])
    items=[]
    other=[]
    counts=Counter()
    for row in prior["nonvisited"]:
        if row["context"]!="Initial":
            other.append(row)
            continue
        if len(items)>=MAX_ROWS:
            raise ValueError("initial_zero_row_budget")
        chain=ancestors(ast,row["ast_path"])
        node=chain[-1][1]
        owner=row["instance"]
        b=row["boundary"]
        matches=[obj for path,obj in chain[:-1] if b and path==b["ast_path"]]
        if row["reason"]!="excluded_procedure_kind" or len(matches)!=1:
            raise ValueError("initial_boundary_evidence_disagreement")
        item={"instance":owner,"ast_path":row["ast_path"],"source_location":row["source"],
              "context":row["context"],"boundary":b,"historical_flat_assignment_id":None}
        try:
            records=expand(node,matches[0],owner,lambda n:resolver.resolve_exact(owner,n),declared,variables,nodes)
        except Refusal as exc:
            item.update(coverage="partial",reason=str(exc),records=[])
            counts["partial"]+=1
        else:
            counts["records"]+=len(records)
            if counts["records"]>MAX_RECORDS:
                raise ValueError("initial_zero_record_budget")
            counts["supported"]+=1
            item.update(coverage="initial_zero_candidates",records=records)
        items.append(item)
    if len(items)+len(other)!=len(prior["nonvisited"]):
        raise ValueError("initial_partition_disagreement")
    return {"schema_version":1,"scope":"direct_initial_zero_statement_candidates",
            "counts":{"ast_occurrences":prior["counts"]["ast_occurrences"],
                      "historical_nonvisited":len(prior["nonvisited"]),"initial_sites":len(items),
                      "supported":counts["supported"],"partial":counts["partial"],"records":counts["records"],
                      "other_nonvisited":len(other),"historical_unsupported_targets":len(prior["unsupported_targets"])},
            "items":items,"other_nonvisited":other,"historical_replay_exact":True,
            "historical_graph_promoted":False,"new_historical_edges":0,"permanent_constants_inferred":0,
            "design_coverage":"not_measured","functional_influence":"not_proven",
            "caveat":"Direct zero assignment candidate at startup, not a global initial state, synthesis guarantee, permanent constant or proof of scheduling/temporal behavior."}

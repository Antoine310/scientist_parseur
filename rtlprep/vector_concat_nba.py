"""PR109: fixed flat vector concatenation NBA candidates, disjoint from PR106."""
from collections import Counter
from .bit_widths import width
from .generate_nba_targets import shape, literal, named
from .concat_nba_targets import Refusal, require, expand as scalar_expand
from .symbols import SignalResolver
from .typed_layout import raw_layouts
from .walker_exclusion_audit import audit_walker, ancestors

MAX_OPERANDS=32
MAX_WIDTH=64
MAX_ROWS=20000
MAX_RECORDS=32768


def coordinates(node,resolve,declared,variables,nodes,*,target):
    require(isinstance(node,dict),"invalid_operand")
    kind=node.get("kind")
    base=node if kind=="NamedValue" else node.get("value")
    require(kind in ("NamedValue","ElementSelect","RangeSelect"),"unsupported_flat_operand")
    signal,layout=named(base,resolve,declared,nodes)
    require(not target or signal in variables,"target_not_indexed_variable")
    hi,lo=layout[:2]
    if kind!="NamedValue":
        require("[" in base["type"],"selection_on_scalar")
        if kind=="ElementSelect":
            a=b=literal(node.get("selector"))
            expected=(0,0,False,True)
        else:
            require(node.get("selectionKind")=="Simple","not_simple_range")
            a,b=literal(node.get("left")),literal(node.get("right"))
            expected=(a,b,False,True)
        require(lo<=b<=a<=hi,"selection_out_of_bounds_or_reversed")
        require(shape(node)==expected,"selection_type_disagreement")
        hi,lo=a,b
    return [(signal,i) for i in range(lo,hi+1)]


def flatten(node,resolve,declared,variables,nodes,*,target):
    require(isinstance(node,dict) and node.get("kind")=="Concatenation","expected_flat_concat")
    operands=node.get("operands")
    require(isinstance(operands,list) and 2<=len(operands)<=MAX_OPERANDS,"concat_arity_or_budget")
    result=[]
    for operand in reversed(operands):
        result.extend(coordinates(operand,resolve,declared,variables,nodes,target=target))
        require(len(result)<=MAX_WIDTH,"concat_width_budget")
    # integral_shape validates explicit descending types; per-operand shape
    # above is limited to 32 bits. Concat result can be up to 64.
    from .bit_widths import integral_shape
    require(integral_shape(node.get("type"))==(len(result)-1,0,False,True),"concat_type_disagreement")
    return result


def expand(node,context,resolve,declared,variables,nodes):
    require(isinstance(node,dict) and node.get("kind")=="Assignment"
            and context in ("Always","AlwaysFF") and node.get("isNonBlocking") is True
            and node.get("op") is None and node.get("timingControl") is None,"not_plain_nba")
    lhs,rhs=node.get("left"),node.get("right")
    targets=flatten(lhs,resolve,declared,variables,nodes,target=True)
    require(len(set(targets))==len(targets),"overlapping_target_coordinates")
    sources=flatten(rhs,resolve,declared,variables,nodes,target=False)
    from .bit_widths import integral_shape
    require(len(sources)==len(targets) and integral_shape(node.get("type"))==(len(targets)-1,0,False,True),
            "assignment_width_or_type_disagreement")
    return [{"relation":"vector_concat_nba_sampled_position_candidate","concat_lsb_position":i,
             "source":{"signal":src[0],"bit":src[1]},"target":{"signal":dst[0],"bit":dst[1]}}
            for i,(src,dst) in enumerate(zip(sources,targets))]


def audit_vector_concat(ast,index,graph):
    prior=audit_walker(ast,index,graph)
    resolver=SignalResolver(ast,index)
    declared=raw_layouts(index)
    variables={s.get("path") or s["instance_path"]+"."+s["name"] for s in index["signals"] if s.get("kind")=="Variable"}
    nodes=set(graph["nodes"])
    items=[]
    other=[]
    counts=Counter()
    for row in prior["unsupported_targets"]:
        if row["lhs_kind"]!="Concatenation":
            other.append(row)
            continue
        if len(items)>=MAX_ROWS:
            raise ValueError("vector_concat_row_budget")
        owner=row["instance"]
        node=ancestors(ast,row["ast_path"])[-1][1]
        resolve=lambda n:resolver.resolve_exact(owner,n)
        item={"instance":owner,"ast_path":row["ast_path"],"source_location":row["source"],
              "context":row["context"],"historical_flat_assignment_id":None}
        try:
            existing=scalar_expand(node,row["context"],resolve,declared,variables,nodes)
        except Refusal:
            try:
                records=expand(node,row["context"],resolve,declared,variables,nodes)
            except Refusal as exc:
                item.update(coverage="partial",reason=str(exc),records=[])
                counts["partial"]+=1
            else:
                counts["new_records"]+=len(records)
                if counts["new_records"]>MAX_RECORDS:
                    raise ValueError("vector_concat_record_budget")
                item.update(coverage="new_vector_candidates",records=records)
                counts["new_sites"]+=1
        else:
            item.update(coverage="existing_pr106",existing_record_count=len(existing),records=[])
            counts["existing_sites"]+=1
            counts["existing_records"]+=len(existing)
        items.append(item)
    if len(items)+len(other)!=len(prior["unsupported_targets"]):
        raise ValueError("vector_concat_partition_disagreement")
    return {"schema_version":1,"scope":"historically_refused_flat_vector_concat_nba_candidates",
            "counts":{"historical_unsupported_targets":len(items)+len(other),"concat_sites":len(items),
                      "new_sites":counts["new_sites"],"partial":counts["partial"],
                      "existing_pr106_sites":counts["existing_sites"],"existing_pr106_records":counts["existing_records"],
                      "new_records":counts["new_records"],"other_unsupported_targets":len(other)},
            "items":items,"other_targets":other,"historical_replay_exact":True,
            "historical_graph_promoted":False,"new_historical_edges":0,
            "design_coverage":"not_measured","functional_influence":"not_proven",
            "caveat":"Fixed statement-local NBA coordinates; no clock, guard, priority, hold, CDC, global transition or RTL proof."}

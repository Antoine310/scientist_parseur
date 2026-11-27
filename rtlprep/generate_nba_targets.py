"""PR108: exact scoped target, fixed selection, statement-local NBA candidates."""
from collections import Counter
import re
from .bit_widths import integral_shape,width
from .concat_nba_targets import Refusal,require
from .csr_target_audit import audit_targets
from .symbols import SignalResolver
from .typed_layout import raw_layouts
from .walker_exclusion_audit import ancestors

MAX_ROWS=20000
MAX_RECORDS=32768
MAX_WIDTH=32


def shape(node):
    typ=node.get("type") if isinstance(node,dict) else None
    require(isinstance(typ,str) and re.fullmatch(r"(?:logic|reg)(?:\[[0-9]{1,5}:[0-9]{1,5}\])?",typ) is not None,
            "unsupported_unsigned_four_state_layout")
    layout=integral_shape(typ)
    require(layout is not None and width(layout)<=MAX_WIDTH,"layout_width_budget_or_direction")
    return layout


def literal(node):
    require(isinstance(node,dict) and node.get("kind")=="IntegerLiteral" and node.get("type")=="int",
            "selector_not_direct_int_literal")
    raw=node.get("value")
    require(isinstance(raw,str) and re.fullmatch(r"0|[1-9][0-9]{0,4}",raw) is not None
            and node.get("constant",raw)==raw,"selector_literal_unproven")
    return int(raw)


def named(node,resolve,declared,nodes):
    require(isinstance(node,dict) and node.get("kind")=="NamedValue","not_direct_named_value")
    layout=shape(node)
    name=resolve(node)
    require(isinstance(name,str) and name in nodes and declared.get(name)==node["type"],
            "unproven_exact_declaration")
    return name,layout


def expand(node,context,owner,expected_target,resolve,declared,scoped_variables,nodes):
    require(isinstance(node,dict) and node.get("kind")=="Assignment" and context=="AlwaysFF"
            and node.get("isNonBlocking") is True and node.get("op") is None and node.get("timingControl") is None,
            "not_plain_always_ff_nba")
    target,dst=named(node.get("left"),resolve,declared,nodes)
    require(target==expected_target and target in scoped_variables and target.startswith(owner+".")
            and target.rsplit(".",1)[0]!=owner,"unproven_scoped_target")
    require(shape(node)==dst,"assignment_layout_disagreement")
    rhs=node.get("right")
    require(isinstance(rhs,dict) and rhs.get("kind") in ("ElementSelect","RangeSelect"),
            "not_direct_fixed_selection")
    source,src=named(rhs.get("value"),resolve,declared,nodes)
    require(source.startswith(owner+".") and source.rsplit(".",1)[0]==owner and source!=target,
            "source_not_direct_instance_signal")
    require("[" in rhs["value"]["type"],"source_not_explicit_vector")
    if rhs["kind"]=="ElementSelect":
        lo=hi=literal(rhs.get("selector"))
    else:
        require(rhs.get("selectionKind")=="Simple","not_simple_range")
        hi,lo=literal(rhs.get("left")),literal(rhs.get("right"))
    require(src[1]<=lo<=hi<=src[0],"selection_out_of_range_or_reversed")
    n=hi-lo+1
    # slang preserves the declared indices on a Simple RangeSelect, e.g.
    # data[7:4] has logic[7:4], not logic[3:0]. Assignment copies values
    # by ordinal (LSB to LSB), independently of destination indices.
    expected_rhs=(0,0,False,True) if rhs["kind"]=="ElementSelect" else (hi,lo,False,True)
    require(width(dst)==n and shape(rhs)==expected_rhs,"selection_width_or_type_disagreement")
    return [{"relation":"generate_nba_sampled_position_candidate",
             "source":{"signal":source,"bit":lo+i},"target":{"signal":target,"bit":dst[1]+i}}
            for i in range(n)]


def audit_generate_targets(ast,index,graph):
    prior=audit_targets(ast,index,graph)
    resolver=SignalResolver(ast,index)
    declared=raw_layouts(index)
    variables={s.get("path") or s["instance_path"]+"."+s["name"] for s in index["signals"]
               if s.get("scope") and s.get("kind")=="Variable"}
    nodes=set(graph["nodes"])
    items=[]
    counts=Counter()
    other=[]
    for row in prior["items"]:
        if row["reason"]!="generate_scoped_target_outside_legacy_flat_gate":
            other.append(row)
            continue
        if len(items)>=MAX_ROWS:
            raise ValueError("generate_target_row_budget")
        if row["existing_member_record_ids"] or row["existing_typed_positions"]:
            raise ValueError("unexpected_member_overlap")
        owner=row["instance"]
        node=ancestors(ast,row["ast_path"])[-1][1]
        item={k:row[k] for k in ("instance","ast_path","context","source","occurrence_ordinal",
                                   "exact_target","historical_flat_assignment_id")}
        try:
            records=expand(node,row["context"],owner,row["exact_target"],
                           lambda n:resolver.resolve_exact(owner,n),declared,variables,nodes)
        except Refusal as exc:
            item.update(coverage="partial",reason=str(exc),records=[])
            counts["partial"]+=1
        else:
            counts["records"]+=len(records)
            if counts["records"]>MAX_RECORDS:
                raise ValueError("generate_target_record_budget")
            item.update(coverage="scoped_fixed_nba_candidates",records=records)
            counts["supported"]+=1
        items.append(item)
    if len(items)+len(other)!=prior["counts"]["historical_unsupported_targets"]:
        raise ValueError("generate_target_partition_disagreement")
    return {"schema_version":1,"scope":"historically_refused_generate_scoped_fixed_nba_candidates",
            "counts":{"historical_unsupported_targets":len(items)+len(other),"generate_sites":len(items),
                      "supported":counts["supported"],"partial":counts["partial"],"records":counts["records"],
                      "other_unsupported_targets":len(other),
                      "other_existing_member_positions":prior["counts"]["existing_position_records"]},
            "items":items,"other_targets":other,"historical_replay_exact":True,
            "historical_graph_promoted":False,"new_historical_edges":0,
            "design_coverage":"not_measured","functional_influence":"not_proven",
            "caveat":"Local sampled source coordinates only; no proof of guards, timing, priority, reset, hold, CDC or global transition."}

"""PR122: parameter-selected local packed-word mux candidates.

Only direct elaborated instance parameter ports, exact reference identities,
bounded forwarding to the immediate parent, and binary 0/1 terminal values.
Never infer a permanent constant or modify the historical graph.
"""
import json
import re
from collections import Counter
from .array_dependencies import Unsupported, layouts
from .addition_candidates import endpoint
from .bitaccess import build_bit_access_index
from .capture_audit import audit_capture
from .constant_indices import evaluate, integer_value
from .dynamic_conversion_candidates import at_pointer, require
from .residual_audit import exact_links, reconcile_capture
from .state_conversion_candidates import literal_bits, corroborate
from .symbols import SignalResolver
from .typed_layout import raw_layouts, identity
from .enum_member_writes import SYMBOL

PARAM_TYPE="logic signed[31:0]"
WORD="logic[31:0]"
MAX_ROWS=2000
MAX_COORDINATES=32768
MAX_INSTANCES=2048
MAX_MEMBERS=50000
MAX_INSTANCE_DEPTH=32
MAX_CHAIN=8
IDENT=re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*\Z")


def obj(n):
    return n if isinstance(n,dict) else {}


def inventory(ast):
    """Direct Instance bodies only; no generate, interface or package lookup."""
    parents={}; by_addr={}; ambiguous=set(); budget=[MAX_MEMBERS]
    def scan(members,parent,depth):
        if depth>MAX_INSTANCE_DEPTH or not isinstance(members,list):
            raise ValueError("parameter_instance_inventory_budget_or_shape")
        budget[0]-=len(members)
        if budget[0]<0: raise ValueError("parameter_member_budget")
        for n in members:
            if not isinstance(n,dict) or n.get("kind")!="Instance": continue
            name=n.get("name"); body=n.get("body")
            if not isinstance(name,str) or not IDENT.fullmatch(name) or not isinstance(body,dict):
                continue
            path=parent+"."+name if parent else name
            if path in parents: raise ValueError("ambiguous_instance_path")
            if len(parents)>=MAX_INSTANCES: raise ValueError("parameter_instance_budget")
            parents[path]=parent
            direct=body.get("members")
            if not isinstance(direct,list): raise ValueError("malformed_instance_members")
            counts=Counter(p.get("name") for p in direct if isinstance(p,dict)
                           and p.get("kind")=="Parameter" and isinstance(p.get("name"),str))
            for p in direct:
                if not isinstance(p,dict) or p.get("kind")!="Parameter": continue
                addr=identity(p); pname=p.get("name")
                if addr is None: continue
                if addr in by_addr or not isinstance(pname,str) or counts[pname]!=1:
                    ambiguous.add(addr)
                by_addr[addr]=(path,p)
            scan(direct,path,depth+1)
    scan(obj(ast.get("design")).get("members",[]),None,0)
    return parents,{a:v for a,v in by_addr.items() if a not in ambiguous}


def parameter_chain(expr,owner,resolve,inv):
    parents,parameters=inv
    chain=[]; seen=set(); refs=[]; declarations=[]
    current=expr
    for _ in range(MAX_CHAIN):
        require(owner in parents and current.get("kind")=="NamedValue"
                and current.get("type")==PARAM_TYPE and resolve(owner,current) is None,
                "unsupported_parameter_reference")
        token=current.get("symbol")
        m=SYMBOL.fullmatch(token) if isinstance(token,str) else None
        require(m is not None,"malformed_parameter_symbol")
        addr,name=m.groups()
        require(addr not in seen,"cyclic_parameter_chain")
        seen.add(addr)
        actual,p=parameters.get(addr,(None,{}))
        require(actual==owner and p.get("name")==name and p.get("type")==PARAM_TYPE
                and p.get("isPort") is True and p.get("isLocal") is False
                and p.get("isBody") is False,"unproven_parameter_port_identity")
        refs.append((current,addr,name)); declarations.append(p)
        init=obj(p.get("initializer"))
        require(init.get("type")==PARAM_TYPE,"parameter_initializer_type_disagreement")
        if init.get("kind")=="NamedValue":
            chain.append({"instance":owner,"parameter":name,"method":"immediate_parent_reference"})
            owner=parents[owner]
            require(owner is not None,"missing_parameter_parent")
            current=init
            continue
        require(init.get("kind")=="Conversion" and obj(init.get("operand")).get("kind")=="IntegerLiteral"
                and obj(init.get("operand")).get("type")=="int","unsupported_parameter_initializer")
        value=evaluate(init,{})
        require(type(value) is int and value in (0,1),"unsupported_parameter_value")
        chain.append({"instance":owner,"parameter":name,"method":"typed_literal_initializer"})
        for (ref,a,n),decl in zip(refs,declarations):
            require(integer_value(decl.get("value"))==value and evaluate(ref,{a:(n,value)})==value,
                    "parameter_value_or_tag_disagreement")
        return value,chain
    raise ValueError("parameter_chain_budget")


def matches(node):
    lhs,rhs=obj(node.get("left")),obj(node.get("right"))
    cs=rhs.get("conditions")
    return (lhs.get("kind")=="NamedValue" and rhs.get("kind")=="ConditionalOp"
            and isinstance(cs,list) and len(cs)==1
            and obj(obj(cs[0]).get("expr")).get("kind")=="UnaryOp"
            and obj(obj(cs[0]).get("expr")).get("op")=="LogicalNot"
            and obj(rhs.get("left")).get("kind")=="Conversion"
            and obj(rhs.get("right")).get("kind")=="ElementSelect")


def mux_model(value,lane):
    require(type(value) is int and value in (0,1),"unsupported_parameter_value")
    require(type(lane) is int and lane in (0,1),"unsupported_packed_lane")
    return {"parameter_value":value,"lane":lane,"width":32,
            "selected_branch":"zero" if value==0 else "packed_word",
            "domain":"defined_binary_inputs_only"}


def expand(node,context,owner,resolve,raw,declared,inv):
    require(context in ("AlwaysComb","continuous") and node.get("kind")=="Assignment"
            and node.get("isNonBlocking") is False and node.get("op") is None
            and node.get("timingControl") is None,"unsupported_parameter_mux_assignment")
    require(matches(node),"unsupported_parameter_mux_shape")
    lhs,rhs=node["left"],node["right"]
    cond=rhs["conditions"][0]
    require(set(cond)=={"expr"},"unsupported_conditional_pattern")
    test=cond["expr"]; zero,alt=rhs["left"],rhs["right"]
    require(test.get("type")=="logic" and node.get("type")==lhs.get("type")==rhs.get("type")
            ==zero.get("type")==alt.get("type")==WORD,"parameter_mux_type_disagreement")
    value,chain=parameter_chain(obj(test.get("operand")),owner,resolve,inv)
    corroborate(test,1,"logic",[str(1-value)])
    leaf=obj(zero.get("operand"))
    require(leaf.get("kind")=="IntegerLiteral" and leaf.get("type")=="bit[31:0]",
            "unsupported_zero_branch_literal")
    bits=literal_bits(leaf.get("value"),32,"bit")
    require(bits==["0"]*32,"nonzero_literal_branch")
    corroborate(leaf,32,"bit",bits); corroborate(zero,32,"logic",bits)
    require(obj(alt.get("value")).get("kind")=="NamedValue"
            and alt["value"].get("type")=="logic[1:0][31:0]","unsupported_alternative_layout")
    require(all("constant" not in n for n in (lhs,alt,alt["value"])),"unexpected_runtime_constant_tag")
    if value==0: corroborate(rhs,32,"logic",bits)
    else: require("constant" not in rhs,"unexpected_runtime_constant_tag")
    local=lambda e:resolve(owner,e)
    dst=endpoint(lhs,local,raw,declared); src=endpoint(alt,local,raw,declared)
    require(dst["outer_packed_indices"]==[] and dst["bits_lsb_first"]==list(range(32))
            and len(src["outer_packed_indices"])==1 and src["bits_lsb_first"]==list(range(32))
            and src["signal"]!=dst["signal"],"parameter_mux_coordinate_disagreement")
    lane=src["outer_packed_indices"][0]; model=mux_model(value,lane)
    pairs=[{"source":src["signal"],"source_packed_indices":[lane],"source_bit":b,
            "target":dst["signal"],"target_bit":b} for b in range(32)]
    return {"family":"parameter_selected_packed_word_mux","target":dst["signal"],"model":model,
            "parameter_chain":chain,"alternative_source":src["signal"],
            "alternative_positions":pairs if value==0 else [],
            "pairs":pairs if value==1 else [],
            "local_values":[{"target":dst["signal"],"target_bit":b,"value":0} for b in range(32)] if value==0 else [],
            "potential_pairs":32 if value==1 else 0,"permanent_constant":"not_inferred",
            "guard_feasibility":"not_proven","priority":"not_proven","timing":"not_proven",
            "model_domain":"defined_binary_inputs_only"}


def audit_parameter_mux(ast,index,graph):
    census=audit_capture(ast,index,graph)
    _,_,residual,_,_,_=exact_links(graph)
    captured=[]
    replay=build_bit_access_index(ast,expected_top=index["top"],index=index,captured_assignments=captured)
    if json.loads(json.dumps(replay))!=graph["bit_accesses"]:
        raise ValueError("bit_access_replay_disagreement")
    cap=reconcile_capture(replay,captured)
    resolver,raw=SignalResolver(ast,index),raw_layouts(index)
    declared=layouts(index)
    inv=inventory(ast)
    rows=[]; count=values=alternatives=0
    for occ in census["items"]:
        node=at_pointer(ast,occ["ast_path"])
        if not matches(node):
            continue
        if len(rows)>=MAX_ROWS:
            raise ValueError("parameter_mux_row_budget")
        row={k:occ[k] for k in ("ast_path","instance","context","source","historical_status","flat_assignment_id")}
        i=row["flat_assignment_id"]
        row.update(coverage="partial",historical_residual=i in residual)
        try:
            require(i is not None and i in cap,"missing_exact_capture")
            original,owner,partial=cap[i]
            require(original is node and owner==row["instance"],"capture_identity_disagreement")
            require(not partial,"unsupported_procedural_context")
            candidate=expand(node,row["context"],owner,resolver.resolve_exact,raw,declared,inv)
            historical=graph["bit_dependency_graph"]["items"][i]
            access=replay["items"][i]
            require(historical["target"]==candidate["target"] and
                    access["target_selection"]=={"kind":"whole"},
                    "historical_target_selection_disagreement")
        except Unsupported as exc:
            row["reason"]=str(exc)
        else:
            count+=candidate["potential_pairs"]
            values+=len(candidate['local_values']); alternatives+=len(candidate['alternative_positions'])
            if count+values+alternatives>MAX_COORDINATES:
                raise ValueError("parameter_mux_coordinate_budget")
            row.update(coverage="parameter_mux_candidates",candidate=candidate)
        rows.append(row)
    good=[r for r in rows if "candidate" in r]
    return {"schema_version":1,"scope":"active_named_target_parameter_not_zero_packed_word_mux",
            "counts":{"ast_occurrences":census["counts"]["ast_occurrences"],
                      "historical_rows":census["counts"]["historical_rows"],"roots":len(rows),
                      "supported":len(good),"partial":len(rows)-len(good),
                      "supported_residual":sum(r["historical_residual"] for r in good),
                      "potential_pairs":count,"local_value_records":values,"inactive_alternative_positions":alternatives,"stored_coordinates":count+values+alternatives,"truncated":False},
            "items":rows,"partial_reasons":dict(Counter(r["reason"] for r in rows if "reason" in r)),
            "historical_replay_exact":True,"historical_graph_promoted":False,"new_historical_edges":0,
            "design_coverage":"not_measured","functional_influence":"not_proven",
            "caveat":"Configuration-specific statement-local values and selected branch pairs; unselected alternative coordinates are not active pairs. No permanent constants, X/Z, guards, priority, timing, reachability or RTL equivalence."}

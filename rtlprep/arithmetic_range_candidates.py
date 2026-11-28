"""PR125: direct simple packed ranges with bounded localparam arithmetic.

Validate the expression tree and exact declarations before evaluating any
folded tag. Preserve statement-local coordinates and historical evidence.
"""
import json
from collections import Counter, defaultdict
from .array_dependencies import Unsupported, layouts
from .zero_extended_additions import endpoint
from .bitaccess import build_bit_access_index
from .capture_audit import audit_capture
from .constant_indices import evaluate, integer_value
from .dynamic_conversion_candidates import at_pointer, require
from .residual_audit import exact_links, reconcile_capture
from .symbols import SignalResolver
from .typed_layout import raw_layouts, packages, identity, IDENT
from .enum_member_writes import SYMBOL
from .parameter_mux_candidates import inventory, PARAM_TYPE, obj
from .localparam_range_concat_candidates import bound

MAX_ROWS=2000
MAX_COORDINATES=32768
MAX_HISTORICAL_EDGES=100000
MAX_BOUND_DEPTH=6
MAX_BOUND_NODES=32
MAX_REFERENCES=8
MAX_INTERMEDIATE=64
MAX_PACKAGE_MEMBERS=4096
MAX_PACKAGES=128


def matches(node):
    lhs,rhs=obj(node.get("left")),obj(node.get("right"))
    return (lhs.get("kind")=="NamedValue" and rhs.get("kind")=="RangeSelect"
            and any(obj(rhs.get(k)).get("kind")=="BinaryOp" for k in ("left","right")))


def package_bounds(ast):
    """Inventory exact direct package declarations, excluding ambiguous identities.

    Address/name binding comes from the elaborated AST, not name search or
    a guessed import. Package entries are not treated as instance locals.
    """
    pkgs=packages(ast)
    if len(pkgs)>MAX_PACKAGES: raise ValueError("arithmetic_package_inventory_budget")
    names=Counter(p.get("name") for p in pkgs if isinstance(p.get("name"),str))
    candidates=defaultdict(list); count=0
    for p in pkgs:
        name=p.get("name"); members=p.get("members")
        if not isinstance(members,list): raise ValueError("malformed_package_members")
        count+=len(members)
        if count>MAX_PACKAGE_MEMBERS: raise ValueError("arithmetic_package_member_budget")
        member_names=Counter(n.get("name") for n in members if isinstance(n,dict)
                             and isinstance(n.get("name"),str))
        for n in members:
            if not isinstance(n,dict): continue
            addr=identity(n); pname=n.get("name")
            if addr is None: continue
            valid=(isinstance(name,str) and IDENT.fullmatch(name) is not None and names[name]==1
                   and isinstance(pname,str) and IDENT.fullmatch(pname) is not None
                   and member_names[pname]==1 and n.get("kind")=="Parameter")
            candidates[addr].append((name,n) if valid else None)
    return {k:v[0] for k,v in candidates.items() if len(v)==1 and v[0] is not None}


def resolve_bound(expr,owner,resolve,inv):
    parents,local_params,pkg_params=inv
    require(owner in parents and expr.get("kind")=="NamedValue"
            and expr.get("type")==PARAM_TYPE and resolve(owner,expr) is None,
            "unsupported_arithmetic_parameter_reference")
    token=expr.get("symbol")
    m=SYMBOL.fullmatch(token) if isinstance(token,str) else None
    require(m is not None,"malformed_arithmetic_parameter_symbol")
    addr,name=m.groups()
    require(not (addr in local_params and addr in pkg_params),"ambiguous_parameter_scope_identity")
    if addr in local_params:
        return bound(expr,owner,resolve,(parents,local_params))
    pkg,p=pkg_params.get(addr,(None,{}))
    require(isinstance(pkg,str) and IDENT.fullmatch(pkg) is not None
            and p.get("kind")=="Parameter" and identity(p)==addr and p.get("name")==name
            and p.get("type")==PARAM_TYPE and p.get("isLocal") is True
            and p.get("isPort") is False and p.get("isBody") is True,
            "unproven_package_localparam_identity")
    init=obj(p.get("initializer"))
    require(init.get("kind")=="Conversion" and init.get("type")==PARAM_TYPE
            and obj(init.get("operand")).get("kind")=="IntegerLiteral"
            and obj(init.get("operand")).get("type")=="int",
            "unsupported_package_localparam_initializer")
    value=evaluate(init,{})
    require(type(value) is int and 0<=value<32,"unsupported_package_localparam_value")
    require(integer_value(p.get("value"))==value and evaluate(expr,{addr:(name,value)})==value,
            "package_localparam_value_or_tag_disagreement")
    return addr,(name,value),{"package":pkg,"reference_instance":owner,"parameter":name,
                              "value":value,"method":"direct_typed_literal_package_localparam"}


def bound_expression(expr,owner,resolve,inv,constants,proofs,budget,depth=0):
    if depth>MAX_BOUND_DEPTH or budget[0]<=0:
        raise ValueError("arithmetic_bound_expression_budget")
    budget[0]-=1
    require(isinstance(expr,dict),"malformed_arithmetic_bound")
    kind=expr.get("kind"); typ=expr.get("type")
    if kind=="NamedValue":
        addr,entry,proof=resolve_bound(expr,owner,resolve,inv)
        require(addr not in constants or constants[addr]==entry,"localparam_identity_disagreement")
        if addr not in constants and len(constants)>=MAX_REFERENCES:
            raise ValueError("arithmetic_bound_reference_budget")
        constants[addr]=entry
        proofs[addr]=proof
        value=entry[1]
        trace={"kind":"localparam","type":typ,"parameter":entry[0],"value":value}
        if "package" in proof: trace["package"]=proof["package"]
    elif kind=="IntegerLiteral":
        require(typ=="int","unsupported_bound_literal_type")
        value=evaluate(expr,{})
        require(type(value) is int and 0<=value<=MAX_INTERMEDIATE,"unsupported_bound_literal_value")
        trace={"kind":"literal","type":typ,"value":value}
    elif kind=="Conversion":
        operand=obj(expr.get("operand"))
        require(typ==PARAM_TYPE and operand.get("kind")=="IntegerLiteral"
                and operand.get("type")=="int","unsupported_bound_conversion")
        value,child=bound_expression(operand,owner,resolve,inv,constants,proofs,budget,depth+1)
        trace={"kind":"conversion","type":typ,"operand":child,"value":value}
    elif kind=="BinaryOp":
        left,right=obj(expr.get("left")),obj(expr.get("right"))
        op=expr.get("op")
        require(typ==PARAM_TYPE and left.get("type")==right.get("type")==PARAM_TYPE
                and op in ("Add","Subtract"),"unsupported_bound_arithmetic_type_or_operator")
        a,lt=bound_expression(left,owner,resolve,inv,constants,proofs,budget,depth+1)
        b,rt=bound_expression(right,owner,resolve,inv,constants,proofs,budget,depth+1)
        value=a+b if op=="Add" else a-b
        require(0<=value<=MAX_INTERMEDIATE,"arithmetic_bound_intermediate_out_of_scope")
        trace={"kind":op,"type":typ,"left":lt,"right":rt,"value":value}
    else:
        raise Unsupported("unsupported_arithmetic_bound_kind")
    require(evaluate(expr,constants,allow_power=False)==value,"arithmetic_bound_value_or_tag_disagreement")
    return value,trace


def range_model(hi,lo):
    require(type(hi) is int and type(lo) is int and 0<=lo<=hi<32
            and hi-lo+1 in (3,5),"unsupported_arithmetic_range")
    return {"msb":hi,"lsb":lo,"width":hi-lo+1,"source_width":32,
            "domain":"defined_binary_inputs_only"}


def expand(node,context,owner,resolve,raw,declared,inv):
    require(context in ("continuous","AlwaysComb") and node.get("kind")=="Assignment"
            and node.get("isNonBlocking") is False and node.get("op") is None
            and node.get("timingControl") is None,"unsupported_arithmetic_range_assignment")
    require(matches(node),"unsupported_arithmetic_range_shape")
    lhs,rhs=node["left"],node["right"]; base=obj(rhs.get("value"))
    require(base.get("kind")=="NamedValue" and base.get("type")=="logic[31:0]"
            and rhs.get("selectionKind")=="Simple","unsupported_arithmetic_range_source")
    require(all("constant" not in n for n in (lhs,rhs,base)),"unexpected_runtime_constant_tag")
    constants={}; proofs={}; budget=[MAX_BOUND_NODES]
    hi,ht=bound_expression(rhs.get("left"),owner,resolve,inv,constants,proofs,budget)
    lo,lt=bound_expression(rhs.get("right"),owner,resolve,inv,constants,proofs,budget)
    require(bool(constants),"no_exact_localparam_reference")
    model=range_model(hi,lo); n=model["width"]
    require(node.get("type")==lhs.get("type")==f"logic[{n-1}:0]"
            and rhs.get("type")==f"logic[{hi}:{lo}]","arithmetic_range_type_disagreement")
    local=lambda e:resolve(owner,e)
    dst=endpoint(lhs,local,raw,declared,{})
    src=endpoint(rhs,local,raw,declared,constants)
    require(dst["outer_packed_indices"]==src["outer_packed_indices"]==[]
            and dst["bits_lsb_first"]==list(range(n))
            and src["bits_lsb_first"]==list(range(lo,hi+1))
            and dst["signal"]!=src["signal"],"arithmetic_range_coordinate_disagreement")
    pairs=[{"source":src["signal"],"source_bit":b,"target":dst["signal"],"target_bit":j}
           for j,b in enumerate(src["bits_lsb_first"])]
    return {"family":"localparam_arithmetic_range","target":dst["signal"],"source":src["signal"],
            "model":model,"bound_proofs":{"msb":ht,"lsb":lt},
            "parameter_proofs":list(proofs.values()),"pairs":pairs,"potential_pairs":n,
            "guard_feasibility":"not_proven","priority":"not_proven","timing":"not_proven",
            "permanent_constant":"not_inferred","model_domain":"defined_binary_inputs_only"}


def historical_agreement(candidate,historical,edges,i):
    n=candidate["potential_pairs"]
    expected=[{**p,"value_transform":"position_only","assignment_id":i} for p in candidate["pairs"]]
    if historical["coverage"]=="assignment_local_position_candidates":
        require(historical["edge_count"]==n and historical["constant_target_bits"]==[]
                and len(edges)==n and sorted(edges,key=lambda e:e["target_bit"])==expected,
                "historical_position_disagreement")
        return n
    require(historical["coverage"]=="partial" and historical["edge_count"]==0
            and not edges and historical["constant_target_bits"]==[],
            "unexpected_partial_historical_edges")
    return 0


def audit_arithmetic_range(ast,index,graph):
    census=audit_capture(ast,index,graph)
    _,_,residual,_,_,_=exact_links(graph)
    captured=[]
    replay=build_bit_access_index(ast,expected_top=index["top"],index=index,captured_assignments=captured)
    if json.loads(json.dumps(replay))!=graph["bit_accesses"]:
        raise ValueError("bit_access_replay_disagreement")
    cap=reconcile_capture(replay,captured)
    resolver,raw=SignalResolver(ast,index),raw_layouts(index)
    declared=layouts(index); inv=(*inventory(ast),package_bounds(ast))
    flat=graph["bit_dependency_graph"]
    if len(flat["edges"])>MAX_HISTORICAL_EDGES: raise ValueError("historical_edge_budget")
    edges=defaultdict(list)
    for e in flat["edges"]:
        i=e.get("assignment_id")
        if type(i) is not int or not 0<=i<len(flat["items"]):
            raise ValueError("invalid_historical_edge_identity")
        edges[i].append(e)
    rows=[]; count=matched=0
    for occ in census["items"]:
        node=at_pointer(ast,occ["ast_path"])
        if not matches(node): continue
        if len(rows)>=MAX_ROWS: raise ValueError("arithmetic_range_row_budget")
        row={k:occ[k] for k in ("ast_path","instance","context","source","historical_status","flat_assignment_id")}
        i=row["flat_assignment_id"]
        row.update(coverage="partial",historical_residual=i in residual)
        try:
            require(i is not None and i in cap,"missing_exact_capture")
            original,owner,partial=cap[i]
            require(original is node and owner==row["instance"],"capture_identity_disagreement")
            require(not partial,"unsupported_procedural_context")
            candidate=expand(node,row["context"],owner,resolver.resolve_exact,raw,declared,inv)
            historical=flat["items"][i]; access=replay["items"][i]
            require(historical["target"]==candidate["target"] and access["target_selection"]=={"kind":"whole"},
                    "historical_target_selection_disagreement")
            n=historical_agreement(candidate,historical,edges[i],i)
        except Unsupported as exc:
            row["reason"]=str(exc)
        else:
            count+=candidate["potential_pairs"]; matched+=n
            if count>MAX_COORDINATES: raise ValueError("arithmetic_range_coordinate_budget")
            row.update(coverage="arithmetic_range_candidates",candidate=candidate,
                       matched_historical_edges=n)
        rows.append(row)
    good=[r for r in rows if "candidate" in r]
    return {"schema_version":1,"scope":"active_named_target_localparam_arithmetic_range",
            "counts":{"ast_occurrences":census["counts"]["ast_occurrences"],
                      "historical_rows":census["counts"]["historical_rows"],"roots":len(rows),
                      "supported":len(good),"partial":len(rows)-len(good),
                      "supported_residual":sum(r["historical_residual"] for r in good),
                      "potential_pairs":count,"matched_historical_edges":matched,
                      "residual_candidate_pairs":sum(r["candidate"]["potential_pairs"] for r in good if r["historical_residual"]),
                      "stored_coordinates":count,"truncated":False},
            "items":rows,"partial_reasons":dict(Counter(r["reason"] for r in rows if "reason" in r)),
            "historical_replay_exact":True,"historical_graph_promoted":False,"new_historical_edges":0,
            "design_coverage":"not_measured","functional_influence":"not_proven",
            "caveat":"Local binary positions; previously supported edges checked exactly. No X/Z, guard, priority, timing, reachability, permanent constants or RTL equivalence."}

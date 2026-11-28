"""Bounded binary CSR counter decoder composition (PR120).

Exact lexical selector, enum member encoding, unsigned address extension,
constant addition and local scalar logical terms. No graph promotion.
"""
import json
from collections import Counter
from .array_dependencies import Unsupported
from .bitaccess import build_bit_access_index
from .capture_audit import audit_capture
from .constant_indices import evaluate
from .dynamic_conversion_candidates import at_pointer, endpoint, require, position_map
from .bit_widths import integral_shape
from .residual_audit import exact_links, reconcile_capture
from .enum_conversion_candidates import enum_definition, initializer, literal, corroborate
from .enum_member_writes import SYMBOL
from .symbols import SignalResolver
from .typed_layout import Types, raw_layouts, packages, identity
from .decoder_composition_candidates import obj

MAX_ROWS=2000
MAX_PAIRS=32768


def op(n,operator,typ="logic"):
    return isinstance(n,dict) and n.get("kind")=="BinaryOp" and n.get("op")==operator and n.get("type")==typ


def terms(n,depth=0,budget=None):
    if budget is None: budget=[128]
    budget[0]-=1
    if depth>32 or budget[0]<0:
        raise ValueError("csr_composition_tree_budget")
    if op(n,"LogicalAnd"):
        return terms(n.get("left"),depth+1,budget)+terms(n.get("right"),depth+1,budget)
    return [obj(n)]


def matches(node):
    lhs,rhs=obj(node.get("left")),obj(node.get("right"))
    return lhs.get("kind")=="ElementSelect" and op(rhs,"LogicalAnd") and any(
        op(t,"Equality") and op(t.get("right"),"Add","logic[31:0]") for t in terms(rhs))


def table(enum):
    require(enum.get("baseType")=="logic[11:0]","unsupported_csr_enum_base")
    members=enum.get("members")
    require(isinstance(members,list) and 0<len(members)<=256,"unsupported_csr_enum_inventory")
    out={}; names=set(); addresses=set(); values=set()
    for m in members:
        require(isinstance(m,dict) and m.get("kind")=="EnumValue","malformed_csr_enum_member")
        addr,name=identity(m),m.get("name")
        require(addr is not None and isinstance(name,str) and SYMBOL.fullmatch(addr+" "+name),
                "malformed_csr_enum_identity")
        require(addr not in addresses and name not in names,"ambiguous_csr_enum_identity")
        init=obj(m.get("initializer"))
        require(init.get("type")=="logic[11:0]" and init.get("kind")=="Conversion"
                and obj(init.get("operand")).get("type")=="bit[11:0]"
                and obj(init.get("operand")).get("kind")=="IntegerLiteral","unsupported_csr_enum_initializer")
        v=initializer(init)
        require(literal(m.get("value"),12)==v and v not in values,"csr_enum_encoding_disagreement")
        out[addr+" "+name]=(name,v)
        names.add(name); addresses.add(addr); values.add(v)
    return out


def parameter_inventory(ast):
    """Only unique direct package parameter declarations, address keyed."""
    out={}; duplicate=set()
    pkgs=packages(ast)
    names=Counter(p.get("name") for p in pkgs)
    for p in pkgs:
        if names[p.get("name")]!=1: continue
        for n in p.get("members",[]):
            if not isinstance(n,dict) or n.get("kind")!="Parameter": continue
            addr=identity(n)
            if addr is None: continue
            if addr in out: duplicate.add(addr)
            out[addr]=(p["name"],n)
    return {k:v for k,v in out.items() if k not in duplicate}


def width_gate(node,types,params,resolve,pkg):
    require(op(node,"Equality") and "constant" not in node,"unsupported_width_gate")
    a,b=obj(node.get("left")),obj(node.get("right"))
    typ="logic signed[31:0]"
    require(a.get("kind")=="NamedValue" and a.get("type")==b.get("type")==typ
            and resolve(a) is None,"unsupported_width_parameter_reference")
    token=a.get("symbol")
    match=SYMBOL.fullmatch(token) if isinstance(token,str) else None
    require(match is not None,"malformed_width_parameter_identity")
    addr,name=match.groups()
    p,n=params.get(addr,(None,{}))
    require(p==pkg and n.get("name")==name and n.get("type")==typ
            and n.get("isLocal") is True,"unproven_width_parameter_identity")
    require(types.constants.get(addr)==((name,64),typ,pkg),"unproven_width_parameter_value")
    init=obj(n.get("initializer"))
    for x in (init,b):
        require(x.get("kind")=="Conversion" and x.get("type")==typ
                and obj(x.get("operand")).get("kind")=="IntegerLiteral"
                and obj(x.get("operand")).get("type")=="int" and evaluate(x,{})==64,
                "unsupported_width_initializer_or_comparison")
    require(evaluate(a,{addr:(name,64)})==64,"width_parameter_tag_disagreement")
    return {"parameter":pkg+"::"+name,"value":64,"compared_to":64}


def csr_model(base,k,upper):
    require(type(base) is int and type(k) is int and 0<=k<32
            and 0<=base<=4095-k and type(upper) is bool,"csr_model_bounds")
    mode,positions=position_map(integral_shape("logic[11:0]"),integral_shape("logic[31:0]"))
    require(mode=="zero_extend" and positions==list(range(12))+[None]*20,"csr_extension_disagreement")
    return {"address_width":12,"comparison_width":32,"zero_fill_count":20,
            "enum_base":base,"index":k,"comparison_value":base+k,"upper":upper,
            "width_gate":64 if upper else None,"domain":"defined_binary_inputs_only"}


def select(n,resolve,raw,constants):
    require(n.get("kind")=="ElementSelect" and n.get("type")=="logic"
            and "constant" not in n,"unsupported_csr_selection")
    base,idx=obj(n.get("value")),obj(n.get("selector"))
    require(base.get("type")=="logic[31:0]","unsupported_csr_target_layout")
    ep=endpoint(base,resolve,raw)
    require(idx.get("kind")=="NamedValue" and idx.get("type")=="integer"
            and resolve(idx) is None,"unsupported_csr_selector")
    k=evaluate(idx,constants)
    require(type(k) is int and 0<=k<32,"unproven_csr_selector")
    return ep,idx,k


def runtime_tree(n):
    """Check the bounded AND tree itself, not constant subexpressions."""
    if op(n,"LogicalAnd"):
        require("constant" not in n,"unexpected_runtime_constant_tag")
        runtime_tree(n["left"]); runtime_tree(n["right"])


def expand(node,context,resolve,raw,constants,types,params):
    require(context=="continuous" and node.get("kind")=="Assignment"
            and node.get("isNonBlocking") is False and node.get("op") is None
            and node.get("timingControl") is None,"unsupported_csr_assignment")
    require(matches(node) and node.get("type")=="logic","unsupported_csr_composition_shape")
    target,idx,k=select(node["left"],resolve,raw,constants)
    rhs=node["right"]; ts=terms(rhs); runtime_tree(rhs)
    require(len(ts) in (2,4),"unsupported_csr_term_count")
    upper=len(ts)==4
    enable,eq=(ts[1],ts[2]) if upper else ts
    require(enable.get("type")=="logic","unsupported_csr_enable")
    en=endpoint(enable,resolve,raw)
    require(op(eq,"Equality") and "constant" not in eq,"unsupported_csr_equality")
    ac,add=obj(eq.get("left")),obj(eq.get("right"))
    require(ac.get("kind")=="Conversion" and ac.get("type")=="logic[31:0]"
            and "constant" not in ac and op(add,"Add","logic[31:0]"),"unsupported_csr_comparison")
    a=obj(ac.get("operand"))
    require(a.get("kind")=="NamedValue" and "constant" not in a,"unsupported_csr_address")
    address=resolve(a); raw_type=a.get("type")
    require(address is not None and raw.get(address)==raw_type,"unproven_csr_address_identity")
    ed=enum_definition(raw_type,types)
    require(ed is not None and types.types.get(raw_type,{}).get("kind")=="TypeAlias",
            "unproven_csr_enum_alias")
    token,enum=ed
    members=table(enum)
    pkg=token.split(" ",1)[1].split("::",1)[0]
    ec,ic=obj(add.get("left")),obj(add.get("right"))
    require(all(x.get("kind")=="Conversion" and x.get("type")=="logic[31:0]" for x in (ec,ic)),
            "unsupported_csr_sum_operands")
    e,i=obj(ec.get("operand")),obj(ic.get("operand"))
    require(e.get("kind")=="NamedValue" and e.get("type")==token and resolve(e) is None
            and isinstance(e.get("symbol"),str) and e["symbol"] in members,"unproven_csr_enum_member")
    name,base=members[e["symbol"]]
    corroborate(e,base,12); corroborate(ec,base,32)
    require(i.get("kind")=="NamedValue" and i.get("type")=="integer"
            and i.get("symbol")==idx.get("symbol") and resolve(i) is None
            and evaluate(ic,constants)==k,"csr_sum_selector_disagreement")
    model=csr_model(base,k,upper)
    corroborate(add,model["comparison_value"],32)
    inhibit=None; gate=None
    if upper:
        neg=ts[0]
        require(neg.get("kind")=="UnaryOp" and neg.get("op")=="LogicalNot"
                and neg.get("type")=="logic" and "constant" not in neg,"unsupported_csr_inhibition")
        inhibit,other,j=select(obj(neg.get("operand")),resolve,raw,constants)
        require(j==k and other.get("symbol")==idx.get("symbol"),"csr_inhibition_selector_disagreement")
        gate=width_gate(ts[3],types,params,resolve,pkg)
    signals=[target["signal"],address,en["signal"]]+([inhibit["signal"]] if upper else [])
    require(len(set(signals))==len(signals),"overlapping_csr_endpoints")
    pairs=[{"source":address,"source_bit":b,"target":target["signal"],"target_bit":k,
            "role":"comparison_address"} for b in range(12)]
    pairs.append({"source":en["signal"],"source_bit":0,"target":target["signal"],"target_bit":k,"role":"write_enable"})
    if upper:
        pairs.append({"source":inhibit["signal"],"source_bit":k,"target":target["signal"],
                      "target_bit":k,"role":"lower_inhibition"})
    return {"family":"csr_enum_index_logical_decoder","target":target["signal"],"target_bit":k,
            "address":address,"enable":en["signal"],"inhibit":inhibit["signal"] if upper else None,
            "enum_type":token.split(" ",1)[1],"enum_member":name,"width_gate":gate,
            "model":model,"pairs":pairs,"potential_pairs":len(pairs),
            "model_domain":"defined_binary_inputs_only","guard_feasibility":"not_proven",
            "timing":"not_proven","global_influence":"not_proven","permanent_constant":"not_inferred"}


def audit_csr_composition(ast,index,graph):
    census=audit_capture(ast,index,graph)
    _,_,residual,_,_,_=exact_links(graph)
    captured=[]
    replay=build_bit_access_index(ast,expected_top=index["top"],index=index,captured_assignments=captured)
    if json.loads(json.dumps(replay))!=graph["bit_accesses"]:
        raise ValueError("bit_access_replay_disagreement")
    cap=reconcile_capture(replay,captured)
    constants={i:c for i,_,_,_,c,_ in captured}
    resolver,raw=SignalResolver(ast,index),raw_layouts(index)
    types=Types(ast)
    if types.truncated: raise ValueError('package_inventory_budget')
    params=parameter_inventory(ast)
    rows=[]; count=0
    for occ in census["items"]:
        node=at_pointer(ast,occ["ast_path"])
        if not matches(node):
            continue
        if len(rows)>=MAX_ROWS:
            raise ValueError("csr_composition_row_budget")
        row={k:occ[k] for k in ("ast_path","instance","context","source","historical_status","flat_assignment_id")}
        i=row["flat_assignment_id"]
        row.update(coverage="partial",historical_residual=i in residual)
        try:
            require(i is not None and i in cap,"missing_exact_capture")
            original,owner,partial=cap[i]
            require(original is node and owner==row["instance"],"capture_identity_disagreement")
            require(not partial,"unsupported_procedural_context")
            candidate=expand(node,row["context"],lambda e:resolver.resolve_exact(owner,e),raw,constants[i],types,params)
            historical=graph["bit_dependency_graph"]["items"][i]
            access=replay["items"][i]
            require(historical["target"]==candidate["target"] and
                    access["target_selection"]=={"kind":"bit","index":candidate["target_bit"]},
                    "historical_target_coordinate_disagreement")
        except Unsupported as exc:
            row["reason"]=str(exc)
        else:
            count+=candidate["potential_pairs"]
            if count>MAX_PAIRS:
                raise ValueError("csr_composition_pair_budget")
            row.update(coverage="csr_composition_candidates",candidate=candidate)
        rows.append(row)
    good=[r for r in rows if "candidate" in r]
    return {"schema_version":1,"scope":"active_element_target_logical_and_equality_add_roots",
            "counts":{"ast_occurrences":census["counts"]["ast_occurrences"],
                      "historical_rows":census["counts"]["historical_rows"],"roots":len(rows),
                      "supported":len(good),"partial":len(rows)-len(good),
                      "supported_residual":sum(r["historical_residual"] for r in good),
                      "potential_pairs":count,"truncated":False},
            "items":rows,"partial_reasons":dict(Counter(r["reason"] for r in rows if "reason" in r)),
            "historical_replay_exact":True,"historical_graph_promoted":False,"new_historical_edges":0,
            "design_coverage":"not_measured","functional_influence":"not_proven",
            "caveat":"Only this CSR statement-local binary composition; inhibition is an independent local input. No X/Z semantics, guards, timing, reachability, global influence or RTL equivalence."}

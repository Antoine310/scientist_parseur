import copy
import pytest
from rtlprep import typed_layout as tl
from rtlprep.array_dependencies import Unsupported
from rtlprep.dependencies import build_dependency_graph

def n(kind,**kw):
    return {"kind":kind,**kw}
def literal(v):
    return n("IntegerLiteral",type="int",value=str(v))
def ref(name,addr,typ):
    return n("NamedValue",symbol=f"{addr} {name}",type=typ)
STATE="101 pkg::state_t"
ADDR="201 pkg::addr_t"
SIGNALS=[("s",10,STATE),("idx",20,ADDR),("p",30,"logic[3:0][3:0]"),
         ("d",40,"logic[3:0]"),("flag",50,"logic"),("q",60,"logic[3:0]")]
def sym(name):
    a,t=next((a,t) for nm,a,t in SIGNALS if nm==name)
    return ref(name,a,t)
def pkg():
    return n("Package",name="pkg",members=[
        n("EnumType",name="state_t",addr=100,baseType="logic[2:0]"),
        n("TypeAlias",name="state_t",addr=101,target="100 pkg::state_t"),
        n("EnumType",name="addr_t",addr=200,baseType="logic[1:0]"),
        n("TypeAlias",name="addr_t",addr=201,target="200 pkg::addr_t"),
        n("Parameter",name="FLAG",addr=300,type="int",value="1",isLocal=True)])
def ast(a=None,p=None):
    members=[n("CompilationUnit",members=[pkg() if p is None else p])]
    if a is not None:
        signals=[n("Variable",name=nm,addr=ad,type=t) for nm,ad,t in SIGNALS]
        signals.append(n("ContinuousAssign",assignment=a))
        members.append(n("Instance",name="top",body=n("InstanceBody",name="top",members=signals)))
    return {"design":n("Root",members=members)}
def assignment(lhs,rhs):
    return n("Assignment",type=lhs["type"],isNonBlocking=False,left=lhs,right=rhs)
def fixed():
    return assignment(sym("flag"),n("ElementSelect",type="logic",value=sym("s"),
        selector=ref("FLAG",300,"int")))
def dynamic(role="read"):
    idx=n("RangeSelect",type="logic[1:0]",selectionKind="Simple",value=sym("idx"),
          left=literal(1),right=literal(0))
    sel=n("ElementSelect",type="logic[3:0]",value=sym("p"),selector=idx)
    return assignment(sym("q"),sel) if role=="read" else assignment(sel,sym("d"))
def expand(a,p=None,constants=None,raw=None):
    types=tl.Types(ast(p=p))
    symbols={f"{ad} {nm}":f"top.{nm}" for nm,ad,_ in SIGNALS}
    raw={f"top.{nm}":t for nm,_,t in SIGNALS} if raw is None else raw
    return tl.expand(a,types,lambda e:symbols.get(e.get("symbol")),raw,constants or {})
def graph(a,enabled=True,p=None):
    return build_dependency_graph(ast(a,p),expected_top="top",enable_typed_layout=enabled)

def test_exact_tokens_and_alias_chain():
    p=pkg()
    p["members"]+=[n("TypeAlias",name="word_t",addr=400,target="logic[7:4]"),
                  n("TypeAlias",name="word2_t",addr=401,target="400 pkg::word_t")]
    t=tl.Types(ast(p=p))
    assert t.resolve(STATE)=="logic[2:0]"
    assert t.resolve("100 pkg::state_t")=="logic[2:0]"
    assert t.resolve("401 pkg::word2_t")=="logic[7:4]"
    for raw in ("pkg::state_t","101 pkg::addr_t","999 pkg::state_t","101 other::state_t","logic[2:0]"):
        assert t.resolve(raw) is None

@pytest.mark.parametrize("mode",["cycle","wrong_target","signed","struct","union","unpacked_enum","duplicate_address","duplicate_package"])
def test_reject_type_inventory(mode):
    p=pkg()
    if mode=="cycle": p["members"][1]["target"]=STATE
    elif mode=="wrong_target": p["members"][1]["target"]="100 other::state_t"
    elif mode=="signed": p["members"][0]["baseType"]="logic signed[2:0]"
    elif mode=="struct": p["members"][1]["target"]="struct packed{logic x;}pkg::s$1"
    elif mode=="union": p["members"][1]["target"]="union packed{logic x;}pkg::u$1"
    elif mode=="unpacked_enum": p["members"][0]["baseType"]="logic$[0:2]"
    elif mode=="duplicate_address": p["members"].append(n("TypeAlias",name="other",addr=101,target="logic"))
    a=ast(p=p)
    if mode=="duplicate_package": a["design"]["members"].append(copy.deepcopy(p))
    assert tl.Types(a).resolve(STATE) is None

def test_fixed_package_constant_and_private_rewrite():
    a=fixed()
    original=copy.deepcopy(a)
    edges,d,proofs=expand(a)
    assert a==original and d=={"mode":"fixed"}
    assert edges==[{"source":"top.s","source_unpacked_indices":[],"source_packed_indices":[],
        "source_bit":1,"target":"top.flag","target_unpacked_indices":[],"target_packed_indices":[],
        "target_bit":0,"relation":"typed_fixed_position_candidate"}]
    assert {p["kind"] for p in proofs}=={"package_type","package_constant"}
    assert next(p for p in proofs if p["kind"]=="package_constant")["parameter"]=="pkg::FLAG"

@pytest.mark.parametrize("role",["read","write"])
def test_enum_index_exact_alternatives(role):
    edges,d,proofs=expand(dynamic(role))
    assert d["mode"]=="dynamic" and d["selector"]["role"]==role
    assert d["selector"]["indices"]==list(range(4)) and len(edges)==48
    assert proofs[0]["canonical_type"]=="logic[1:0]"
    for i in range(4):
        data=[e for e in edges if e["alternative_id"]==i and e["relation"]=="index_data_candidate"]
        ctrl=[e for e in edges if e["alternative_id"]==i and e["relation"]=="index_control_candidate"]
        assert len(data)==4 and len(ctrl)==8
        assert {(e["source_bit"],e["target_bit"]) for e in data}=={(b,b) for b in range(4)}
        assert all(e[("source" if role=="read" else "target")+"_packed_indices"]==[i] for e in data)
        assert {(e["source"],e["source_bit"],e["target_bit"]) for e in ctrl}=={
            ("top.idx",j,b) for j in range(2) for b in range(4)}

@pytest.mark.parametrize("mode",["wrong_type_token","wrong_signal","declared_mismatch","wrong_constant_name",
    "wrong_constant_address","wrong_constant_type","wrong_constant_tag","nonlocal_parameter","shadowed_constant",
    "out_of_bounds","unsupported_rhs","compound","timed"])
def test_reject_unproven_assignment(mode):
    a=fixed()
    p=pkg()
    c={}
    r={f"top.{nm}":t for nm,_,t in SIGNALS}
    sel=a["right"]["selector"]
    if mode=="wrong_type_token": a["right"]["value"]["type"]="101 other::state_t"
    elif mode=="wrong_signal": a["right"]["value"]["symbol"]="99 s"
    elif mode=="declared_mismatch": r["top.s"]="logic[2:0]"
    elif mode=="wrong_constant_name": sel["symbol"]="300 OTHER"
    elif mode=="wrong_constant_address": sel["symbol"]="301 FLAG"
    elif mode=="wrong_constant_type": sel["type"]="integer"
    elif mode=="wrong_constant_tag": sel["constant"]="0"
    elif mode=="nonlocal_parameter": p["members"][-1]["isLocal"]=False
    elif mode=="shadowed_constant": c={"300":None}
    elif mode=="out_of_bounds": p["members"][-1]["value"]="3"
    elif mode=="unsupported_rhs": a["right"]=n("Call",type="logic",subroutine="f")
    elif mode=="compound": a["op"]="Add"
    elif mode=="timed": a["timingControl"]={}
    with pytest.raises(Unsupported): expand(a,p,c,r)

def test_previous_graph_identity_and_link():
    old,new=graph(dynamic(),False),graph(dynamic())
    excluded={"typed_layout","analysis_limits"}
    assert {k:v for k,v in old.items() if k not in excluded}=={
        k:v for k,v in new.items() if k not in excluded}
    d=new["typed_layout"]
    assert d["counts"]=={"captured":1,"supported":1,"partial":0,"edges":48,"truncated":False}
    assert d["items"][0]["flat_assignment_id"]==0

@pytest.mark.parametrize("limit,value,reason",[("MAX_EDGES",47,"edge_budget_exceeded"),
    ("MAX_PROOFS",0,"type_proof_budget"),("MAX_NODES",1,"type_scan_budget"),
    ("MAX_TYPES",1,"package_inventory_budget"),("MAX_PACKAGE_MEMBERS",1,"package_inventory_budget")])
def test_atomic_budget(monkeypatch,limit,value,reason):
    monkeypatch.setattr(tl,limit,value)
    g=graph(dynamic())
    d=g["typed_layout"]
    assert d["counts"]["truncated"] and not d["edges"]
    assert d["items"][0]["reason"]==reason and "type_proofs" not in d["items"][0]

def test_legacy_graph_inventory():
    from rtlprep.analysis_budgets import analyzer_summary
    g=graph(dynamic())
    g.pop("typed_layout")
    assert len(analyzer_summary(g)["analyzers"])==14

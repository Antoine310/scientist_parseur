import copy
import pytest

from rtlprep import selector_recovery as sr
from rtlprep.constant_indices import evaluate, scope_constants
from rtlprep.array_dependencies import Unsupported,layout
from rtlprep.dependencies import build_dependency_graph

def n(kind,**kw):
    return {"kind":kind,**kw}
def integer(v,typ="integer"):
    return n("IntegerLiteral",type=typ,value=str(v))
def ref(name,addr,typ="logic[3:0]"):
    return n("NamedValue",symbol=f"{addr} {name}",type=typ)
def power(base=2,exp=None,typ="integer"):
    return n("BinaryOp",type=typ,op="Power",left=integer(base,typ),
             right=integer(2) if exp is None else exp)
def level():
    return ref("level",90,"integer")
def idx():
    return n("BinaryOp",type="integer",op="Subtract",
             left=power(exp=level()),right=integer(1))
def select(name,addr,i):
    return n("ElementSelect",type="logic",value=ref(name,addr),selector=i)
def assignment(rhs=None):
    return n("Assignment",type="logic",isNonBlocking=False,left=select("y",30,idx()),
             right=select("a",10,integer(2)) if rhs is None else rhs)
SIGNALS=(("a",10),("b",20),("y",30))
CONST={"90":("level",2)}
def expand(a,constants=CONST):
    declared={f"top.{nm}":layout("logic[3:0]") for nm,_ in SIGNALS}
    symbols={f"{addr} {nm}":f"top.{nm}" for nm,addr in SIGNALS}
    return sr.expand(a,lambda e:symbols.get(e.get("symbol")),declared,constants)
def param(value=2):
    return n("Parameter",name="level",addr=90,type="integer",isLocal=True,value=str(value))
def graph(a,enabled=True):
    members=[n("Variable",name=nm,addr=addr,type="logic[3:0]") for nm,addr in SIGNALS]
    members.extend([param(),n("ContinuousAssign",assignment=a)])
    ast={"design":n("Root",members=[n("Instance",name="top",
        body=n("InstanceBody",name="top",members=members))])}
    return build_dependency_graph(ast,expected_top="top",enable_selector_recovery=enabled)

@pytest.mark.parametrize("base,exp,value",[(2,0,1),(2,5,32),(2,10,1024),(3,3,27),(1,10,1)])
def test_power_opt_in(base,exp,value):
    p=power(base,integer(exp))
    assert evaluate(p,{}) is None
    assert evaluate(p,{},allow_power=True)==value

@pytest.mark.parametrize("mode",["zero_base","negative_base","negative_exp","huge_exp","overflow","type_overflow",
    "type_disagreement","runtime_tag","wrong_name","wrong_address","wrong_tag","unknown_literal","depth","node_budget"])
def test_power_refuses_unproven(mode):
    p=power(exp=level())
    const=CONST
    budget=None
    depth=0
    if mode=="zero_base": p["left"]=integer(0)
    elif mode=="negative_base": p["left"]=integer(-2)
    elif mode=="negative_exp": p["right"]=integer(-1)
    elif mode=="huge_exp": p["right"]=integer(1000000)
    elif mode=="overflow": p=power(3,integer(7))
    elif mode=="type_overflow": p=power(2,integer(3),"logic[2:0]")
    elif mode=="type_disagreement": p["left"]["type"]="int"
    elif mode=="runtime_tag": p["right"]["constant"]="2"; const={}
    elif mode=="wrong_name": p["right"]["symbol"]="90 other"
    elif mode=="wrong_address": p["right"]["symbol"]="91 level"
    elif mode=="wrong_tag": p["constant"]="5"
    elif mode=="unknown_literal": p["right"]=n("IntegerLiteral",type="logic[1:0]",value="2'bxx")
    elif mode=="depth": depth=13
    elif mode=="node_budget": budget=[1]
    assert evaluate(p,const,depth,budget,allow_power=True) is None

def test_lexical_scope_and_no_ast_mutation():
    a=assignment()
    original=copy.deepcopy(a)
    constants=scope_constants([param()])
    rewritten,proofs=sr.normalize(a,constants)
    assert a==original and rewritten["left"]["selector"]==integer(3)
    assert proofs==[{"ast_path":["left","selector"],"type":"integer","index":3,
                     "evidence":"bounded_lexical_power"}]
    with pytest.raises(Unsupported): sr.normalize(a,{})

def test_fixed_copy():
    edges,d,p=expand(assignment())
    assert d=={"mode":"fixed","constant_target_positions":[]} and len(p)==1
    assert edges==[{"source":"top.a","source_packed_indices":[],"source_bit":2,
        "target":"top.y","target_packed_indices":[],"target_bit":3,
        "relation":"fixed_position_candidate"}]

def test_literal_only():
    a=assignment(n("Conversion",type="logic",
        operand=n("IntegerLiteral",type="bit[0:0]",value="1'b0")))
    edges,d,_=expand(a)
    assert not edges and d=={"mode":"fixed","constant_target_positions":[
        {"target":"top.y","target_packed_indices":[],"target_bit":3}]}

def test_bitwise_delegation():
    rhs=n("BinaryOp",type="logic",op="BinaryOr",left=select("a",10,idx()),
          right=select("b",20,integer(0)))
    edges,d,p=expand(assignment(rhs))
    assert d["mode"]=="bitwise" and d["operators"]==["BinaryOr"] and len(p)==2
    assert {(e["source"],e["source_bit"],e["target_bit"]) for e in edges}=={
        ("top.a",3,3),("top.b",0,3)}

def test_mux_delegation():
    rhs=n("ConditionalOp",type="logic",conditions=[{"expr":select("a",10,idx())}],
          left=select("b",20,idx()),right=select("a",10,integer(0)))
    edges,d,p=expand(assignment(rhs))
    assert d["mode"]=="mux" and len(p)==3 and len(edges)==3
    assert {(e["source"],e["source_bit"],e["relation"]) for e in edges}=={
        ("top.a",3,"mux_control_candidate"),("top.b",3,"mux_data_candidate"),
        ("top.a",0,"mux_data_candidate")}

@pytest.mark.parametrize("mode",["out_of_bounds","unsupported_rhs","runtime_leaf","compound","timed"])
def test_atomic_rejection(mode):
    a=assignment()
    if mode=="out_of_bounds": a["left"]["selector"]=power(exp=integer(3))
    elif mode=="unsupported_rhs": a["right"]=n("Call",type="logic",subroutine="f")
    elif mode=="runtime_leaf": a["right"]["selector"]=ref("b",20)
    elif mode=="compound": a["op"]="Add"
    elif mode=="timed": a["timingControl"]={}
    with pytest.raises(Unsupported): expand(a)

def test_channel_identity_and_frozen_previous_graphs():
    a=assignment()
    old,new=graph(a,False),graph(a)
    excluded={"selector_recovery","analysis_limits"}
    assert {k:v for k,v in old.items() if k not in excluded}=={
        k:v for k,v in new.items() if k not in excluded}
    d=new["selector_recovery"]
    assert d["counts"]=={"captured":1,"supported":1,"partial":0,"edges":1,"truncated":False}
    assert d["items"][0]["flat_assignment_id"]==0
    assert new["dynamic_dependencies"]["items"][0]["reason"]=="unproven_selector_type"

@pytest.mark.parametrize("limit,value,reason",[("MAX_EDGES",0,"edge_budget_exceeded"),
    ("MAX_PROOFS",0,"selector_proof_budget"),("MAX_NODES",1,"selector_scan_budget")])
def test_budget_atomic(monkeypatch,limit,value,reason):
    monkeypatch.setattr(sr,limit,value)
    g=graph(assignment())
    d=g["selector_recovery"]
    assert d["counts"]["truncated"] and not d["edges"]
    assert d["items"][0]["reason"]==reason and "selector_proofs" not in d["items"][0]
    assert "selector_recovery" in g["analysis_limits"]["truncated_analyzers"]

def test_legacy_graph_inventory():
    from rtlprep.analysis_budgets import analyzer_summary
    g=graph(assignment())
    g.pop("selector_recovery")
    g.pop("typed_layout")
    assert len(analyzer_summary(g)["analyzers"])==13

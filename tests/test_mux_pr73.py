import pytest
from rtlprep import mux_dependencies as mx
from rtlprep.array_dependencies import layout, Unsupported
from rtlprep.dependencies import build_dependency_graph

def n(kind,**kw):
    return {"kind":kind,**kw}
def ref(name,addr,typ="logic[3:0]"):
    return n("NamedValue",symbol=f"{addr} {name}",type=typ)
def num(v):
    return n("IntegerLiteral",type="int",value=str(v))
def rng(name,addr):
    return n("RangeSelect",type="logic[3:0]",selectionKind="Simple",
             value=ref(name,addr),left=num(3),right=num(0))
def bit(name,addr,index):
    return n("ElementSelect",type="logic",value=ref(name,addr),selector=num(index))
def mux(cond=None,left=None,right=None):
    return n("ConditionalOp",type="logic[3:0]",
             conditions=[{"expr":cond if cond is not None else ref("s",40,"logic")}],
             left=left if left is not None else rng("a",10),
             right=right if right is not None else rng("b",20))
def assignment(rhs=None):
    return n("Assignment",type="logic[3:0]",isNonBlocking=False,left=ref("y",30),
             right=rhs if rhs is not None else mux())
SIGNALS=(("a",10,"logic[3:0]"),("b",20,"logic[3:0]"),("y",30,"logic[3:0]"),
         ("s",40,"logic"),("t",50,"logic"))
def expand(a):
    declared={f"top.{name}":layout(typ) for name,_,typ in SIGNALS}
    symbols={f"{addr} {name}":f"top.{name}" for name,addr,_ in SIGNALS}
    return mx.expand(a,lambda e:symbols.get(e.get("symbol")),declared,{})
def graph(a,enabled=True):
    members=[n("Variable",name=name,addr=addr,type=typ) for name,addr,typ in SIGNALS]
    members.append(n("ContinuousAssign",assignment=a))
    ast={"design":n("Root",members=[n("Instance",name="top",
        body=n("InstanceBody",name="top",members=members))])}
    return build_dependency_graph(ast,expected_top="top",enable_mux=enabled)

def test_mux_data_and_control():
    edges,d,b=expand(assignment())
    assert len(edges)==12 and len(d)==1 and len(b)==2
    assert {(e["source"],e["source_bit"],e["target_bit"],e["branch_id"])
            for e in edges if e["relation"]=="mux_data_candidate"}=={
            ("top."+src,i,i,j) for j,src in enumerate(("a","b")) for i in range(4)}
    assert {(e["source"],e["source_bit"],e["target_bit"],e["decision_id"])
            for e in edges if e["relation"]=="mux_control_candidate"}=={
            ("top.s",0,i,0) for i in range(4)}
    assert [x["path"] for x in b]==[[{"decision_id":0,"arm":"true"}],[{"decision_id":0,"arm":"false"}]]

def test_nested_paths_and_branch_constants():
    c=n("UnbasedUnsizedIntegerLiteral",type="logic[3:0]",value="4'd0")
    edges,d,b=expand(assignment(mux(left=mux(ref("t",50,"logic")),right=c)))
    assert len(edges)==16 and len(d)==2 and len(b)==3
    assert d[1]["path"]==[{"decision_id":0,"arm":"true"}]
    assert b[0]["path"]==[{"decision_id":0,"arm":"true"},{"decision_id":1,"arm":"true"}]
    assert b[1]["path"]==[{"decision_id":0,"arm":"true"},{"decision_id":1,"arm":"false"}]
    assert b[2]["path"]==[{"decision_id":0,"arm":"false"}]
    assert [p["target_bit"] for p in b[2]["constant_target_positions"]]==list(range(4))
    assert all(not x["constant_target_positions"] for x in b[:2])

@pytest.mark.parametrize("op",sorted(mx.COMPARISONS))
def test_comparison_control(op):
    cond=n("BinaryOp",op=op,type="logic",left=bit("a",10,2),right=bit("b",20,1))
    edges,d,_=expand(assignment(mux(cond)))
    assert d[0]["condition_operator"]==op
    assert {(e["source"],e["source_bit"],e["target_bit"]) for e in edges if
            e["relation"]=="mux_control_candidate"}=={(src,b,i) for src,b in (("top.a",2),("top.b",1)) for i in range(4)}

@pytest.mark.parametrize("op",sorted(mx.LOGICAL))
def test_logical_control(op):
    cond=n("BinaryOp",op=op,type="logic",left=ref("s",40,"logic"),right=ref("t",50,"logic"))
    edges,_,_=expand(assignment(mux(cond)))
    assert sum(e["relation"]=="mux_control_candidate" for e in edges)==8

def test_multibit_truth_control():
    edges,_,_=expand(assignment(mux(rng("a",10))))
    assert sum(e["relation"]=="mux_control_candidate" for e in edges)==16

def test_same_data_not_deduplicated_across_paths():
    edges,_,_=expand(assignment(mux(right=rng("a",10))))
    assert len([e for e in edges if e["relation"]=="mux_data_candidate"])==8

def test_constant_condition_does_not_prune_branches():
    edges,d,b=expand(assignment(mux(n("IntegerLiteral",type="logic",value="1'b1"))))
    assert len(edges)==8 and len(b)==2 and d[0]["control_source_count"]==0

def test_bitwise_branch():
    rhs=n("BinaryOp",type="logic[3:0]",op="BinaryXor",left=rng("a",10),right=rng("b",20))
    edges,_,b=expand(assignment(mux(left=rhs)))
    assert len(edges)==16 and b[0]["operators"]==["BinaryXor"]

@pytest.mark.parametrize("mode",["pattern","multiple","missing","dynamic","wrong_identity","width","state","opaque","arithmetic","compound","timed","assignment_type"])
def test_reject_unproven(mode):
    a=assignment()
    rhs=a["right"]
    if mode=="pattern": rhs["conditions"][0]["pattern"]={}
    elif mode=="multiple": rhs["conditions"]*=2
    elif mode=="missing": rhs["conditions"]=[]
    elif mode=="dynamic": rhs["left"]["left"]=ref("b",20)
    elif mode=="wrong_identity": rhs["conditions"][0]["expr"]["symbol"]="999 s"
    elif mode=="width": rhs["right"]["type"]="logic[2:0]"
    elif mode=="state": rhs["right"]["type"]="bit[3:0]"
    elif mode=="opaque": rhs["conditions"][0]["expr"]=n("Call",type="logic",subroutine="f")
    elif mode=="arithmetic": rhs["right"]=n("BinaryOp",type="logic[3:0]",op="Add",left=rng("a",10),right=rng("b",20))
    elif mode=="compound": a["op"]="Add"
    elif mode=="timed": a["timingControl"]={}
    elif mode=="assignment_type": a["type"]="logic[2:0]"
    with pytest.raises(Unsupported): expand(a)

def test_old_graphs_preserved_and_identity():
    old,new=graph(assignment(),False),graph(assignment())
    exclude={"mux_dependencies","analysis_limits"}
    assert {k:v for k,v in old.items() if k not in exclude}=={k:v for k,v in new.items() if k not in exclude}
    d=new["mux_dependencies"]
    assert d["counts"]=={"captured":1,"supported":1,"partial":0,"edges":12,"truncated":False}
    assert d["items"][0]["flat_assignment_id"]==0

@pytest.mark.parametrize("limit,value,reason",[("MAX_EDGES",11,"edge_budget_exceeded"),
    ("MAX_ROW_PAIRS",11,"mux_row_pair_budget"),("MAX_BRANCHES",1,"mux_branch_budget")])
def test_budget_atomic(monkeypatch,limit,value,reason):
    monkeypatch.setattr(mx,limit,value)
    g=graph(assignment())
    d=g["mux_dependencies"]
    assert d["counts"]["truncated"] and not d["edges"]
    assert d["items"][0]["reason"]==reason and "branches" not in d["items"][0]
    assert "mux_dependencies" in g["analysis_limits"]["truncated_analyzers"]

def test_legacy_graph_inventory_readable():
    from rtlprep.analysis_budgets import analyzer_summary
    g=graph(assignment())
    g.pop("mux_dependencies")
    g.pop("dynamic_dependencies")
    g.pop("selector_recovery")
    assert len(analyzer_summary(g)["analyzers"])==11

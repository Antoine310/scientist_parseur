import pytest
from rtlprep import bitwise_dependencies as bw
from rtlprep.array_dependencies import layout, Unsupported
from rtlprep.dependencies import build_dependency_graph

def n(kind,**kw):
    return {"kind":kind,**kw}
def ref(name,addr,typ="logic[3:0]"):
    return n("NamedValue",symbol=f"{addr} {name}",type=typ)
def num(v):
    return n("IntegerLiteral",value=str(v),type="int")
def sel(name,addr):
    return n("RangeSelect",type="logic[3:0]",selectionKind="Simple",
             value=ref(name,addr),left=num(3),right=num(0))
def binary(op,left=None,right=None):
    return n("BinaryOp",type="logic[3:0]",op=op,
             left=left if left is not None else sel("a",10),
             right=right if right is not None else sel("b",20))
def assignment(rhs=None,typ="logic[3:0]"):
    return n("Assignment",type=typ,isNonBlocking=False,left=ref("y",30,typ),
             right=rhs if rhs is not None else binary("BinaryAnd"))
def expand(a):
    declared={"top.a":layout("logic[3:0]"),"top.b":layout("logic[3:0]"),
              "top.y":layout(a["left"]["type"])}
    return bw.expand(a,lambda x:{"10 a":"top.a","20 b":"top.b","30 y":"top.y"}.get(x.get("symbol")),declared,{})
def ast(a):
    return {"design":n("Root",members=[n("Instance",name="top",body=n("InstanceBody",name="top",members=[
        n("Variable",name="a",addr=10,type="logic[3:0]"),
        n("Variable",name="b",addr=20,type="logic[3:0]"),
        n("Variable",name="y",addr=30,type=a["left"]["type"]),
        n("ContinuousAssign",assignment=a)]))])}
@pytest.mark.parametrize("op",sorted(bw.BINARY))
def test_binary_positions(op):
    edges,fixed,ops=expand(assignment(binary(op)))
    assert len(edges)==8 and not fixed and ops==[op]
    assert {(e["source"],e["source_bit"],e["target_bit"]) for e in edges}=={
        (f"top.{s}",b,b) for s in ("a","b") for b in range(4)}
    assert all(e["relation"]=="syntactic_influence_candidate" for e in edges)
@pytest.mark.parametrize("op",sorted(bw.REDUCTION))
def test_reductions(op):
    edges,fixed,ops=expand(assignment(n("UnaryOp",type="logic",op=op,operand=sel("a",10)),"logic"))
    assert len(edges)==4 and not fixed and ops==[op]
    assert {(e["source_bit"],e["target_bit"]) for e in edges}=={(b,0) for b in range(4)}
def test_nested_not_and_xor():
    rhs=n("UnaryOp",type="logic[3:0]",op="BitwiseNot",operand=binary("BinaryXor"))
    edges,_,ops=expand(assignment(rhs))
    assert len(edges)==8 and ops==["BinaryXor","BitwiseNot"]
def test_mask_not_functional_proof():
    rhs=binary("BinaryAnd",right=n("IntegerLiteral",type="logic[3:0]",value="4'b0000"))
    edges,fixed,_=expand(assignment(rhs))
    assert len(edges)==4 and not fixed
    assert all(e["source"]=="top.a" for e in edges)
def test_same_source_deduplicated_not_cancelled():
    edges,_,_=expand(assignment(binary("BinaryXor",right=sel("a",10))))
    assert len(edges)==4
def test_literal_only_positions():
    c=n("IntegerLiteral",type="logic[3:0]",value="4'b0000")
    edges,fixed,_=expand(assignment(binary("BinaryOr",c,c)))
    assert not edges and [r["target_bit"] for r in fixed]==list(range(4))
    assert all("value" not in r for r in fixed)
def test_replication_positions():
    bit=n("ElementSelect",type="logic",value=ref("b",20),selector=num(1))
    rhs=binary("BinaryAnd",right=n("Replication",type="logic[3:0]",count=num(4),
               concat=n("Concatenation",type="logic",operands=[bit])))
    edges,_,_=expand(assignment(rhs))
    assert {(e["source_bit"],e["target_bit"]) for e in edges if e["source"]=="top.b"}=={(1,b) for b in range(4)}
@pytest.mark.parametrize("mode",["add","logical","width","state","dynamic","out_of_bounds","wrong_identity","wrong_type","compound","timed","conversion","opaque"])
def test_refuse_unsupported(mode):
    a=assignment()
    rhs=a["right"]
    if mode=="add": rhs["op"]="Add"
    elif mode=="logical": rhs["op"]="LogicalAnd"
    elif mode=="width": rhs["right"]["type"]="logic[2:0]"
    elif mode=="state": rhs["right"]["type"]="bit[3:0]"
    elif mode=="dynamic": rhs["left"]["left"]=ref("b",20)
    elif mode=="out_of_bounds": rhs["left"]["left"]=num(4)
    elif mode=="wrong_identity": rhs["left"]["value"]["symbol"]="999 a"
    elif mode=="wrong_type": rhs["left"]["value"]["type"]="logic[7:0]"
    elif mode=="compound": a["op"]="Add"
    elif mode=="timed": a["timingControl"]={}
    elif mode=="conversion": rhs["right"]=n("Conversion",type="logic[3:0]",operand=n("IntegerLiteral",type="logic",value="1'b1"))
    elif mode=="opaque": rhs["right"]=n("Call",type="logic[3:0]",subroutine="f")
    with pytest.raises(Unsupported): expand(a)
def test_channel_does_not_change_flat_or_coordinate_graph():
    a=ast(assignment())
    old=build_dependency_graph(a,expected_top="top",enable_bitwise=False)
    new=build_dependency_graph(a,expected_top="top")
    assert {k:v for k,v in old.items() if k not in ("analysis_limits","bitwise_dependencies")}=={
        k:v for k,v in new.items() if k not in ("analysis_limits","bitwise_dependencies")}
    d=new["bitwise_dependencies"]
    assert d["counts"]=={"captured":1,"supported":1,"partial":0,"edges":8,"truncated":False}
    assert d["items"][0]["flat_assignment_id"]==0
def test_budget_atomic_and_visible(monkeypatch):
    monkeypatch.setattr(bw,"MAX_EDGES",7)
    g=build_dependency_graph(ast(assignment()),expected_top="top")
    d=g["bitwise_dependencies"]
    assert d["counts"]["truncated"] and not d["edges"]
    assert d["items"][0]["reason"]=="edge_budget_exceeded"
    assert "bitwise_dependencies" in g["analysis_limits"]["truncated_analyzers"]
def test_row_pair_budget(monkeypatch):
    monkeypatch.setattr(bw,"MAX_ROW_PAIRS",7)
    g=build_dependency_graph(ast(assignment()),expected_top="top")
    assert not g["bitwise_dependencies"]["edges"]
    assert g["bitwise_dependencies"]["items"][0]["reason"]=="row_pair_budget"

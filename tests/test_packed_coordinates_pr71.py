import pytest
from rtlprep import array_dependencies
from rtlprep.dependencies import build_dependency_graph
from rtlprep.packed_coordinates import expand, Unsupported

def n(kind,**kw):
    return {"kind":kind,**kw}
def ref(name,addr,typ):
    return n("NamedValue",symbol=f"{addr} {name}",type=typ)
def num(value):
    return n("IntegerLiteral",type="int",value=str(value))
def word(name,addr,index,typ="logic[2:1][7:4]",selected="logic[7:4]"):
    return n("ElementSelect",type=selected,value=ref(name,addr,typ),selector=num(index))
def assignment(lhs=None,rhs=None):
    return n("Assignment",type="logic[7:4]",isNonBlocking=False,
             left=lhs if lhs is not None else word("q",20,1),
             right=rhs if rhs is not None else word("p",10,2))
def declarations():
    typ=array_dependencies.layout("logic[2:1][7:4]")
    return {"top.p":typ,"top.q":typ}
def resolve(expr):
    return {"10 p":"top.p","20 q":"top.q"}.get(expr.get("symbol"))
def evaluate(node):
    return expand(node,resolve,declarations(),{})
def ast(node,*,procedural=True):
    stmt=n("ProceduralBlock",procedureKind="AlwaysComb",body=n("ExpressionStatement",expr=node)) if procedural else n("ContinuousAssign",assignment=node)
    return {"design":n("Root",members=[n("Instance",name="top",body=n("InstanceBody",name="top",members=[
        n("Variable",name="p",addr=10,type="logic[2:1][7:4]"),
        n("Variable",name="q",addr=20,type="logic[2:1][7:4]"),stmt]))])}
def graph(a,enabled=True):
    return build_dependency_graph(a,expected_top="top",enable_packed_coordinates=enabled)

def test_word_is_four_positions_not_one_bit():
    edges,fixed=evaluate(assignment())
    assert not fixed and len(edges)==4
    assert [(e["source_packed_indices"],e["source_bit"],e["target_packed_indices"],e["target_bit"])
            for e in edges]==[([2],b,[1],b) for b in range(4,8)]
def test_constant_conversion_positions():
    rhs=n("Conversion",type="logic[7:4]",operand=n("IntegerLiteral",type="bit[31:0]",value="32'd1"))
    edges,fixed=evaluate(assignment(rhs=rhs))
    assert not edges
    assert [(r["target_packed_indices"],r["target_bit"]) for r in fixed]==[([1],b) for b in range(4,8)]
    assert all("value" not in r for r in fixed)

@pytest.mark.parametrize("mode",["outside","dynamic","wrong_type","wrong_base","aggregate","indexed","state","assignment_type","compound","timed","operator","untyped_literal"])
def test_reject_unproven_mapping(mode):
    a=assignment()
    if mode=="outside":
        a["left"]["selector"]=num(3)
    elif mode=="dynamic":
        a["left"]["selector"]=ref("i",30,"int")
    elif mode=="wrong_type":
        a["left"]["type"]="logic[3:0]"
    elif mode=="wrong_base":
        a["right"]["value"]["type"]="logic[3:0][7:4]"
    elif mode=="aggregate":
        a["left"]=a["left"]["value"]
    elif mode=="indexed":
        a["left"]=n("RangeSelect",type="logic[7:4]",selectionKind="IndexedUp",value=a["left"],left=num(4),right=num(4))
    elif mode=="state":
        a["right"]=n("Conversion",type="logic[7:4]",operand=a["right"])
    elif mode=="assignment_type":
        a["type"]="logic[3:0]"
    elif mode=="compound":
        a["op"]="Add"
    elif mode=="timed":
        a["timingControl"]={}
    elif mode=="operator":
        a["right"]=n("BinaryOp",type="logic[7:4]",op="Add",left=a["right"],right=num(1))
    elif mode=="untyped_literal":
        a["right"]=n("IntegerLiteral",value="4'd0")
    with pytest.raises(Unsupported):
        evaluate(a)

def test_procedural_link_and_no_flat_change():
    a=ast(assignment())
    old,new=graph(a,False),graph(a)
    assert old["bit_dependency_graph"]==new["bit_dependency_graph"]
    assert old["bit_accesses"]==new["bit_accesses"]
    assert new["bit_dependency_graph"]["counts"]["partial"]==1
    d=new["array_dependencies"]
    assert d["counts"]=={"captured":1,"supported":1,"partial":0,"edges":4,"truncated":False}
    row=d["items"][0]
    assert row["flat_assignment_id"]==0 and row["assignment_kind"]=="procedural"
    assert row["target"]==new["bit_dependency_graph"]["items"][0]["target"]
    assert row["nonblocking"] is False
def test_continuous_old_supported_not_duplicated():
    a=ast(assignment(),procedural=False)
    assert graph(a,False)["array_dependencies"]==graph(a)["array_dependencies"]
def test_continuous_literal_retry():
    a=ast(assignment(rhs=n("Conversion",type="logic[7:4]",operand=n("IntegerLiteral",type="bit[31:0]",value="32'd1"))),procedural=False)
    d=graph(a)["array_dependencies"]
    assert d["counts"]["captured"]==d["counts"]["supported"]==1
    assert len(d["items"][0]["constant_target_positions"])==4
def test_budget_is_atomic(monkeypatch):
    monkeypatch.setattr(array_dependencies,"MAX_EDGES",3)
    g=graph(ast(assignment()))
    d=g["array_dependencies"]
    assert d["counts"]["truncated"] and d["edges"]==[]
    assert d["items"][0]["reason"]=="edge_budget_exceeded"
    assert "array_dependencies" in g["analysis_limits"]["truncated_analyzers"]

def test_generated_selector_identity():
    a=assignment()
    a["left"]["selector"]=n("NamedValue",symbol="30 k",type="integer",constant="1")
    data=ast(a)
    members=data["design"]["members"][0]["body"]["members"]
    proc=members.pop()
    members.append(n("GenerateBlock",name="g",members=[n("Parameter",name="k",addr=30,type="integer",isLocal=True,value="1"),proc]))
    d=graph(data)["array_dependencies"]
    assert d["counts"]["supported"]==1
    assert all(e["target_packed_indices"]==[1] for e in d["edges"])
    members[-1]["members"][0]["addr"]=31
    d=graph(data)["array_dependencies"]
    assert d["counts"]["supported"]==0 and not d["edges"]

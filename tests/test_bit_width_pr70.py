import pytest
from rtlprep.bit_width_literals import literal_width, resize_constant_state
from rtlprep.bit_widths import integral_shape
from rtlprep.dependencies import build_dependency_graph

def n(kind,**kw):
    return {"kind":kind,**kw}

def ref(name,addr,typ):
    return n("NamedValue",symbol=f"{addr} {name}",type=typ)

def lit(value,typ="logic[7:0]",kind="UnbasedUnsizedIntegerLiteral"):
    return n(kind,value=value,type=typ)

def fixture(rhs,target_type="logic[7:0]",*,select=True,extra=None,source_type="logic[7:0]"):
    y=ref("y",20,target_type)
    if select:
        y=n("RangeSelect",type="logic[7:0]",selectionKind="Simple",value=y,
            left=n("IntegerLiteral",value="7"),right=n("IntegerLiteral",value="0"))
    assignment=n("Assignment",left=y,right=rhs,isNonBlocking=False,**(extra or {}))
    members=[n("Variable",name="a",addr=10,type=source_type),
             n("Variable",name="y",addr=20,type=target_type),
             n("ContinuousAssign",assignment=assignment)]
    return {"design":n("Root",members=[n("Instance",name="top",body=n("InstanceBody",name="top",members=members))])}

def graph(ast,enabled=True):
    return build_dependency_graph(ast,expected_top="top",enable_width_literals=enabled)

def recovered(ast,edges,constants):
    old,new=graph(ast,False),graph(ast)
    assert old["bit_dependency_graph"]["counts"]["partial"]==1
    b=new["bit_dependency_graph"]
    assert b["counts"]["supported"]==1
    assert sorted((e["source_bit"],e["target_bit"]) for e in b["edges"])==sorted(edges)
    assert b["items"][0]["constant_target_bits"]==constants
    assert new["bit_accesses"]["items"][0]["width_conversions"]
    assert old["edges"]==new["edges"]

@pytest.mark.parametrize("value",["8'hff","8'b11111111","255","'1","8'hxx","8'hzz",0])
def test_elaborated_fill(value):
    assert literal_width(lit(value))==8

@pytest.mark.parametrize("value,typ",[
    ("4'hf","logic[7:0]"),("8'b2","logic[7:0]"),("8'o9","logic[7:0]"),
    ("256","logic[7:0]"),("unknown","logic[7:0]"),("8'hff","word_t"),
    ("8'hff","logic[0:7]"),(True,"logic[7:0]"),
])
def test_reject_invalid_literal(value,typ):
    assert literal_width(lit(value,typ)) is None

@pytest.mark.parametrize("value",["8'hff","8'h00","8'hxx"])
def test_constant_fill_positions(value):
    recovered(fixture(lit(value)),[],list(range(8)))

def test_typed_integer_decimal():
    recovered(fixture(lit("3","logic[7:0]","IntegerLiteral")),[],list(range(8)))

def test_constant_state_conversion():
    rhs=n("Conversion",type="logic[7:0]",operand=lit("4'd3","bit[3:0]","IntegerLiteral"))
    recovered(fixture(rhs),[],list(range(8)))

def test_dynamic_state_conversion_refused():
    rhs=n("Conversion",type="logic[7:0]",operand=ref("a",10,"bit[3:0]"))
    b=graph(fixture(rhs,source_type="bit[3:0]"))["bit_dependency_graph"]
    assert b["counts"]["partial"]==1 and not b["edges"]

def test_assignment_zero_extension():
    rhs=n("RangeSelect",type="logic[3:0]",selectionKind="Simple",value=ref("a",10,"logic[7:0]"),
          left=n("IntegerLiteral",value="3"),right=n("IntegerLiteral",value="0"))
    recovered(fixture(rhs),[(i,i) for i in range(4)],list(range(4,8)))

def test_assignment_truncation():
    rhs=n("RangeSelect",type="logic[7:0]",selectionKind="Simple",value=ref("a",10,"logic[7:0]"),
          left=n("IntegerLiteral",value="7"),right=n("IntegerLiteral",value="0"))
    recovered(fixture(rhs,target_type="logic[3:0]",select=False),[(i,i) for i in range(4)],[])

@pytest.mark.parametrize("mode",["untyped","wrong_width","compound","unknown_layout","out_of_bounds"])
def test_assignment_resize_rejects_unproved(mode):
    rhs=n("RangeSelect",type="logic[3:0]",selectionKind="Simple",value=ref("a",10,"logic[7:0]"),
          left=n("IntegerLiteral",value="3"),right=n("IntegerLiteral",value="0"))
    typ="logic[7:0]"
    extra=None
    if mode=="untyped":
        rhs.pop("type")
    elif mode=="wrong_width":
        rhs["type"]="logic[2:0]"
    elif mode=="compound":
        extra={"op":"Add"}
    elif mode=="unknown_layout":
        typ="word_t"
    elif mode=="out_of_bounds":
        rhs["left"]["value"]="11"
        rhs["right"]["value"]="8"
    b=graph(fixture(rhs,target_type=typ,extra=extra))["bit_dependency_graph"]
    assert b["counts"]["partial"]==1 and not b["edges"]

def test_old_supported_preserved():
    rhs=n("RangeSelect",type="logic[7:0]",selectionKind="Simple",value=ref("a",10,"logic[7:0]"),
          left=n("IntegerLiteral",value="7"),right=n("IntegerLiteral",value="0"))
    ast=fixture(rhs)
    assert graph(ast)["bit_dependency_graph"]==graph(ast,False)["bit_dependency_graph"]

def test_unknown_state_value_not_interpreted():
    p=[(None,{"kind":"literal","width":4},4)]
    out,mode=resize_constant_state(p,integral_shape("logic[3:0]"),integral_shape("bit[7:0]"))
    assert mode=="constant_state_zero_extend"
    assert all(x[0] is None for x in out) and sum(x[2] for x in out)==8

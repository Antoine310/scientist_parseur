import pytest
from rtlprep.bit_widths import integral_shape, conversion_mode, resize_parts
from rtlprep.bitgraph import expand_assignment, source_positions
from rtlprep.dependencies import build_dependency_graph

@pytest.mark.parametrize("raw,expected",[
    ("logic[7:0]",(7,0,False,True)),
    ("logic signed[11:4]",(11,4,True,True)),
    ("bit",(0,0,False,False)),
    ("int",(31,0,True,False)),
    ("integer unsigned",(31,0,False,True)),
    ("time",(63,0,False,True)),
])
def test_explicit_type(raw,expected):
    assert integral_shape(raw)==expected

@pytest.mark.parametrize("raw",["word_t","logic[0:7]","logic[1:0][7:0]","logic[7:0]$[0:3]","logic[1024:0]",None])
def test_reject_layout(raw):
    assert integral_shape(raw) is None

def fixture(source_type,destination_type,source_width,dest_width):
    a={"kind":"NamedValue","symbol":"10 a","type":source_type}
    y={"kind":"NamedValue","symbol":"20 y","type":f"logic[{dest_width-1}:0]"}
    rhs={"kind":"Concatenation","type":y["type"],"operands":[
         {"kind":"Conversion","type":destination_type,"operand":a}]}
    members=[{"kind":"Variable","name":"a","addr":10,"type":source_type},
             {"kind":"Variable","name":"y","addr":20,"type":y["type"]},
             {"kind":"ContinuousAssign","assignment":{"kind":"Assignment","left":y,
                     "right":rhs,"isNonBlocking":False}}]
    return {"design":{"kind":"Root","members":[{"kind":"Instance","name":"top",
                "body":{"kind":"InstanceBody","name":"top","members":members}}]}}

@pytest.mark.parametrize("src,dst,a,b,expected,constants",[
    ("logic[7:0]","logic[11:0]",8,12,[(i,i) for i in range(8)],list(range(8,12))),
    ("logic signed[7:0]","logic signed[11:0]",8,12,[(i,i) for i in range(8)]+[(7,i) for i in range(8,12)],[]),
    ("logic[11:4]","logic[3:0]",8,4,[(i+4,i) for i in range(4)],[]),
    ("logic signed[7:0]","logic[3:0]",8,4,[(i,i) for i in range(4)],[]),
])
def test_recovered_positions(src,dst,a,b,expected,constants):
    ast=fixture(src,dst,a,b)
    old=build_dependency_graph(ast,expected_top="top",enable_width_conversions=False)
    new=build_dependency_graph(ast,expected_top="top")
    assert old["bit_dependency_graph"]["counts"]["partial"]==1
    graph=new["bit_dependency_graph"]
    assert graph["counts"]["supported"]==1
    assert sorted((e["source_bit"],e["target_bit"]) for e in graph["edges"])==sorted(expected)
    assert graph["items"][0]["constant_target_bits"]==constants
    assert new["edges"]==old["edges"]

@pytest.mark.parametrize("src,dst,reason",[
    ("logic signed[7:0]","logic[11:0]","conversion_extension_signedness_ambiguous"),
    ("logic[7:0]","logic signed[11:0]","conversion_extension_signedness_ambiguous"),
    ("logic[7:0]","bit[11:0]","conversion_state_change_unmodeled"),
    ("word_t","logic[11:0]","conversion_width_unproven_or_changed"),
])
def test_ambiguous_remains_partial(src,dst,reason):
    graph=build_dependency_graph(fixture(src,dst,8,12),expected_top="top")
    assert graph["bit_accesses"]["items"][0]["reason"]==reason
    assert not graph["bit_dependency_graph"]["edges"]

def test_nested_slice_of_concat():
    p=[("top.a",{"kind":"whole"},4),("top.b",{"kind":"whole"},4)]
    parts,mode=resize_parts(p,integral_shape("logic[7:0]"),integral_shape("logic[5:0]"))
    assert mode=="truncate_msb"
    assert parts[0][2]==2
    assert source_positions(parts[0][1],(7,4),2)==[4,5]
    assert parts[1]==p[1]

def test_reject_false_source_span():
    selection={"kind":"conversion_view","base":{"kind":"whole"},"base_width":8,
               "width":4,"offset":0,"repeat":False}
    with pytest.raises(ValueError,match="source_width_mismatch"):
        source_positions(selection,(3,0),4)

def test_reject_outside_view():
    selection={"kind":"conversion_view","base":{"kind":"whole"},"base_width":8,
               "width":4,"offset":6,"repeat":False}
    with pytest.raises(ValueError,match="invalid_conversion_view"):
        source_positions(selection,(7,0),4)

def test_segment_budget():
    parts=[("top.a",{"kind":"bit","index":i},1) for i in range(32)]
    with pytest.raises(ValueError,match="conversion_segment_budget"):
        resize_parts(parts,integral_shape("logic[31:0]"),integral_shape("logic[32:0]"))

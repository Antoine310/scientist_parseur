import pytest
from rtlprep.bitgraph import build_bit_dependency_graph, expand_assignment, packed_bounds
from rtlprep.bitaccess import _bit_graph_positions_valid

def segment(source="u.a",selection=None,start=0,end=3,**extra):
    return {"source":source,"selection":selection or {"kind":"range","msb":7,"lsb":4},
            "rhs_lsb":start,"rhs_msb":end,**extra}

def row(segments=None,**extra):
    return {"target":"u.q","coverage":"rhs_lanes_only","bit_graph_eligible":True,
            "target_selection":{"kind":"whole"},"rhs_width":8,
            "source_segments":segments if segments is not None else [
                segment(),segment(selection={"kind":"range","msb":3,"lsb":0},start=4,end=7)],
            **extra}

BOUNDS={"u.a":(7,0),"u.q":(11,4)}

def test_swap_nonzero_destination_bounds():
    edges,constants=expand_assignment(row(),BOUNDS)
    assert {(e["source_bit"],e["target_bit"]) for e in edges}=={
        *((i+4,i+4) for i in range(4)),*((i,i+8) for i in range(4))}
    assert constants==[]

def test_constants_and_transform():
    r=row([segment(value_transform="bitwise_not"),
           segment(source=None,selection={"kind":"literal","width":4},start=4,end=7)])
    edges,constants=expand_assignment(r,BOUNDS)
    assert len(edges)==4 and all(e["value_transform"]=="bitwise_not" for e in edges)
    assert constants==[8,9,10,11]

@pytest.mark.parametrize("type_string",["logic[7:0]$[0:3]","logic[0:7]","logic[1:0][7:0]","word_t"])
def test_reject_layout(type_string):
    assert packed_bounds(type_string) is None

@pytest.mark.parametrize("mode",["partial","unvalidated","overlap","hole","out_of_bounds","width"])
def test_atomic_rejection(mode):
    r=row()
    if mode=="partial":
        r["coverage"]="partial"
    elif mode=="unvalidated":
        r["bit_graph_eligible"]=False
    elif mode=="overlap":
        r["source_segments"][1]["rhs_lsb"]=3
    elif mode=="hole":
        r["source_segments"].pop()
    elif mode=="out_of_bounds":
        r["source_segments"][0]["selection"]["msb"]=8
    else:
        r["rhs_width"]=7
    with pytest.raises(ValueError):
        expand_assignment(r,BOUNDS)

def test_simple_range_gate():
    node={"kind":"RangeSelect","selectionKind":"Simple","value":{"kind":"NamedValue"},
          "left":{"kind":"IntegerLiteral","value":"7"},
          "right":{"kind":"IntegerLiteral","value":"4"}}
    assert _bit_graph_positions_valid(node)
    node["selectionKind"]="IndexedUp"
    assert not _bit_graph_positions_valid(node)

def test_dynamic_and_nested_gate():
    node={"kind":"ElementSelect","value":{"kind":"NamedValue"},
          "selector":{"kind":"NamedValue","constant":"1"}}
    assert not _bit_graph_positions_valid(node)
    node["selector"]={"kind":"IntegerLiteral","value":"1"}
    assert _bit_graph_positions_valid(node)
    node["value"]={"kind":"ElementSelect"}
    assert not _bit_graph_positions_valid(node)

def test_graph_keeps_assignment_provenance_and_refuses_unknown_layout():
    index={"schema_version":1,"instances":[{"path":"u","ports":[{"name":"a","type":"logic[7:0]"},
                  {"name":"q","type":"logic[11:4]"}]}],"signals":[]}
    access={"schema_version":1,"counts":{"truncated":False},"items":[row(),row()]}
    result=build_bit_dependency_graph(access,index)
    assert result["counts"]["supported"]==2 and result["counts"]["edges"]==16
    assert {e["assignment_id"] for e in result["edges"]}=={0,1}
    index["instances"][0]["ports"][0]["type"]="logic[7:0]$[0:1]"
    result=build_bit_dependency_graph(access,index)
    assert result["counts"]["partial"]==2 and result["edges"]==[]

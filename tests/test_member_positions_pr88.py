import copy
import pytest
from rtlprep.array_dependencies import Unsupported
from rtlprep.member_positions import endpoint,compare_history,field_info

def struct():
    return {"kind":"packed_struct_offset","members":{"a":[2,[[1],[0]]],"b":[0,[[0],[1]]]}}

def test_struct_offset_and_field_index_are_distinct():
    assert endpoint("top.s","10 p::T",struct(),2,"a",[1])=={
        "signal":"top.s","coordinate_kind":"packed_struct_offset","position":2,
        "field":"a","field_coordinates":[1],"declared_type":"p::T"}

def test_vector_declared_index():
    r=endpoint("top.v","logic[7:4]",{"kind":"declared_index","indices":[4,5,6,7]},5)
    assert r["position"]==5 and r["coordinate_kind"]=="declared_index"

def test_multidimensional_coordinate():
    r=endpoint("top.v","logic[0:1][1:0]",{"kind":"packed_vector_coordinates","coordinates":[[1,0],[1,1],[0,0],[0,1]]},2,coords=[0,0])
    assert r["position"]==2 and r["coordinates"]==[0,0]

@pytest.mark.parametrize("bit,field,coord",[(0,"a",None),(4,"a",None),(2,"bad",None),(2,None,None),(2,"a",[0]),(-1,"b",None),(True,"b",None)])
def test_reject_bad_struct_endpoint(bit,field,coord):
    with pytest.raises(Unsupported):
        endpoint("top.s","10 p::T",struct(),bit,field,coord)

@pytest.mark.parametrize("bit,coords",[(0,[0,0]),(2,[1,0]),(0,None)])
def test_reject_bad_packed_coordinate(bit,coords):
    with pytest.raises(Unsupported):
        endpoint("top.v","logic[1:0][0:0]",{"kind":"packed_vector_coordinates","coordinates":[[1,0],[0,0]]},bit,coords=coords)

def test_reject_invalid_declared_index():
    with pytest.raises(Unsupported):
        endpoint("top.v","logic[7:4]",{"kind":"declared_index","indices":[4,5,6,7]},0)

def test_compare_only_compatible_units():
    s={"signal":"top.a","position":0,"coordinate_kind":"declared_index"}
    t={"signal":"top.b","position":0,"coordinate_kind":"declared_index"}
    graph={"edges":[{"source":"top.a","target":"top.b"}],"bit_dependency_graph":{"edges":[
        {"source":"top.a","source_bit":0,"target":"top.b","target_bit":0}]}}
    items=[{"source":s,"target":t},{"source":{**s,"coordinate_kind":"packed_struct_offset"},"target":t}]
    before=copy.deepcopy((items,graph))
    assert compare_history(items,graph)=={"signal_pair_present":2,"signal_pair_absent":0,
        "flat_coordinate_comparable":1,"flat_coordinate_incomparable":1,
        "flat_endpoint_tuple_present":1,"flat_endpoint_tuple_absent":0}
    assert (items,graph)==before

def test_field_metadata_variants():
    assert field_info({"source_field":{"field":"a","field_bit":7}},"source")==("a",[7])
    assert field_info({"field":"b","field_bit":0},"target")==("b",[0])
    assert field_info({"source_field":"a","source_field_coordinates":[1,2]},"source")==("a",[1,2])

import copy
import pytest
from rtlprep.constant_indices import evaluate, integer_value, normalize_positions, scope_constants
from rtlprep.bitaccess import _bit_graph_positions_valid

def param(addr=12,name="k",value="32'sd3",**extra):
    return {"kind":"Parameter","addr":addr,"name":name,"type":"integer",
            "isLocal":True,"value":value,**extra}

def named(symbol="12 k",**extra):
    return {"kind":"NamedValue","symbol":symbol,"type":"integer",**extra}

def lit(value="31",type_string="int"):
    return {"kind":"IntegerLiteral","value":value,"type":type_string}

def sub(left,right,**extra):
    return {"kind":"BinaryOp","op":"Subtract","type":"int","left":left,"right":right,**extra}

def test_generate_reverse():
    constants=scope_constants([param()])
    assert evaluate(named(constant="3"),constants)==3
    assert evaluate(sub(lit(),named(),constant="28"),constants)==28

def test_scope_identity_and_shadowing():
    outer=scope_constants([param()])
    inner=scope_constants([param(addr=13,value="4")],outer)
    assert evaluate(named("12 k"),inner)==3
    assert evaluate(named("13 k"),inner)==4
    assert evaluate(named("12 other"),inner) is None
    assert evaluate(named("99 k",constant="3"),inner) is None
    assert evaluate(named(),scope_constants([])) is None

def test_runtime_tag_is_not_a_parameter():
    constants=scope_constants([{"kind":"Variable","addr":12,"name":"k","type":"integer","value":"3"}])
    assert evaluate(named(constant="3"),constants) is None

def test_conflicting_identity():
    constants=scope_constants([param(),param(value="4")])
    assert evaluate(named(),constants) is None

def test_nonlocal_parameter_not_accepted():
    node=param()
    node["isLocal"]=False
    assert evaluate(named(),scope_constants([node])) is None

@pytest.mark.parametrize("value",["2'd4","4'shF","8'bx001","-1","32'sd1025",True])
def test_bad_literal(value):
    assert integer_value(value) is None

def test_arithmetic_rejects_negative_and_overflow():
    assert evaluate(sub(lit("2"),lit("3")),{}) is None
    node={"kind":"BinaryOp","op":"Add","left":lit("3","logic[1:0]"),
          "right":lit("1","logic[1:0]"),"type":"logic[1:0]"}
    assert evaluate(node,{}) is None

def test_conversion_rejects_truncation():
    node={"kind":"Conversion","type":"logic[1:0]","operand":lit("4")}
    assert evaluate(node,{}) is None

def test_inconsistent_ast_constant_rejected():
    assert evaluate(named(constant="4"),scope_constants([param()])) is None

def test_normalization_does_not_mutate_ast():
    node={"kind":"ElementSelect","value":{"kind":"NamedValue"},
          "selector":sub(lit(),named())}
    original=copy.deepcopy(node)
    result=normalize_positions(node,scope_constants([param()]))
    assert node==original
    assert result["selector"]["value"]=="28"
    assert _bit_graph_positions_valid(result)

def test_unknown_index_stays_ineligible():
    node={"kind":"ElementSelect","value":{"kind":"NamedValue"},
          "selector":named("99 k",constant="3")}
    assert not _bit_graph_positions_valid(normalize_positions(node,scope_constants([param()])))

def test_indexed_range_stays_ineligible():
    node={"kind":"RangeSelect","selectionKind":"IndexedUp","value":{"kind":"NamedValue"},
          "left":named(),"right":lit("2")}
    assert not _bit_graph_positions_valid(normalize_positions(node,scope_constants([param()])))

def test_simple_range_resolves_both_endpoints():
    node={"kind":"RangeSelect","selectionKind":"Simple","value":{"kind":"NamedValue"},
          "left":sub(lit(),named()),"right":named()}
    result=normalize_positions(node,scope_constants([param()]))
    assert result["left"]["value"]=="28" and result["right"]["value"]=="3"
    assert _bit_graph_positions_valid(result)

import pytest
from rtlprep.constant_indices import scope_constants, evaluate
from rtlprep.array_dependencies import constant_unsigned_conversion, constant_assignment, layout, Unsupported

def param(addr=12,value="8",**kw):
    return {"kind":"Parameter","addr":addr,"name":"W","type":"int",
            "value":value,"isLocal":False,"isPort":True,**kw}

def named(symbol="12 W",typ="int"):
    return {"kind":"NamedValue","symbol":symbol,"type":typ}

def cast(value=None,typ="logic[2:0]"):
    return {"kind":"Conversion","type":typ,"operand":{
        "kind":"Call","subroutine":"$unsigned","type":"int unsigned",
        "arguments":[value if value is not None else named()]}}

def constants():
    return scope_constants([param(value="13")],instance_parameters=True)

def test_parameter_port_opt_in():
    assert evaluate(named(),constants())==13
    assert evaluate(named(),scope_constants([param()])) is None

def test_specialization():
    a=scope_constants([param(value="8")],instance_parameters=True)
    b=scope_constants([param(value="5")],instance_parameters=True)
    assert evaluate(named(),a)==8 and evaluate(named(),b)==5

def test_body_parameter_rejected():
    p=param()
    p["isPort"]=False
    assert evaluate(named(),scope_constants([p],instance_parameters=True)) is None

def test_ambiguous_parameter():
    assert evaluate(named(),scope_constants([param(),param(value="5")],instance_parameters=True)) is None

def test_truncation():
    assert constant_unsigned_conversion(cast(),constants())==(3,5)

def test_extension():
    assert constant_unsigned_conversion(cast(typ="logic[63:0]"),constants())==(64,13)

@pytest.mark.parametrize("mode",["runtime","wrong_callee","wrong_type","extra_arg","bad_tag","negative","signed_target","wrong_arg_width"])
def test_reject_conversion(mode):
    expr=cast()
    operand=expr["operand"]
    if mode=="runtime":
        operand["arguments"]=[{**named("99 W"),"constant":"13"}]
    elif mode=="wrong_callee":
        operand["subroutine"]="123 unsigned"
    elif mode=="wrong_type":
        operand["type"]="int"
    elif mode=="extra_arg":
        operand["arguments"].append(named())
    elif mode=="bad_tag":
        expr["constant"]="7"
    elif mode=="negative":
        operand["arguments"]=[{"kind":"IntegerLiteral","type":"int","value":"-1"}]
    elif mode=="signed_target":
        expr["type"]="logic signed[2:0]"
    else:
        operand["arguments"]=[named(typ="logic[3:0]")]
    assert constant_unsigned_conversion(expr,constants()) is None

def test_constant_coordinates():
    lhs={"kind":"ElementSelect","value":named("u.lut","logic[7:0][2:0]"),
         "selector":{"kind":"IntegerLiteral","type":"int","value":"2"}}
    a={"kind":"Assignment","isNonBlocking":False,"left":lhs,"right":cast()}
    result=constant_assignment(a,lambda n:n["symbol"],{"u.lut":layout("logic[7:0][2:0]")},constants())
    assert [(r["target_packed_indices"],r["target_bit"],r["value"]) for r in result]==[
        ([2],0,1),([2],1,0),([2],2,1)]
    a["right"]["type"]="logic[3:0]"
    with pytest.raises(Unsupported,match="width"):
        constant_assignment(a,lambda n:n["symbol"],{"u.lut":layout("logic[7:0][2:0]")},constants())

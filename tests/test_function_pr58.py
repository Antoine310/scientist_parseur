import copy
import pytest
from rtlprep.function_dependencies import summarize_function, resolve_call, Unsupported

def named(symbol):
    return {"kind":"NamedValue","symbol":symbol}

def definition():
    args=[{"kind":"FormalArgument","addr":i,"name":name,"direction":"In"}
          for i,name in [(11,"x"),(12,"y")]]
    return {"kind":"Subroutine","addr":10,"name":"f","subroutineKind":"Function",
            "defaultLifetime":"Automatic","arguments":args,"members":copy.deepcopy(args),
            "body":{"kind":"Return","expr":{"kind":"BinaryOp","op":"BinaryXor",
                "left":named("11 x"),"right":{"kind":"IntegerLiteral","value":"8'h5a"}}}}

def call():
    return {"kind":"Call","subroutine":"10 f","arguments":[named("21 a"),named("22 b")]}

def resolve(node):
    return {"21 a":"u.a","22 b":"u.b"}.get(node.get("symbol"))

def test_single_return():
    assert summarize_function(definition())==(2,[0])

def test_unused_actual_excluded():
    row=resolve_call(call(),{("10","f"):definition()},resolve)
    assert row["used_argument_positions"]==[0]
    assert row["unused_argument_positions"]==[1]
    assert row["return_signal_references"]==["u.a"]
    assert row["argument_signal_references"]==[["u.a"],["u.b"]]

def test_both_actuals():
    d=definition()
    d["body"]["expr"]["right"]=named("12 y")
    assert resolve_call(call(),{("10","f"):d},resolve)["return_signal_references"]==["u.a","u.b"]

def test_cancellation_is_still_reference():
    d=definition()
    d["body"]["expr"]["right"]=named("11 x")
    assert summarize_function(d)==(2,[0])

def test_constant_return():
    d=definition()
    d["body"]["expr"]={"kind":"IntegerLiteral","value":"0"}
    assert resolve_call(call(),{("10","f"):d},resolve)["return_signal_references"]==[]

def test_sequential_wrapper():
    d=definition()
    d["body"]={"kind":"Block","blockKind":"Sequential","body":{"kind":"List","list":[d["body"]]}}
    assert summarize_function(d)==(2,[0])

@pytest.mark.parametrize("mode",["static","task","output","default","global","recursive","multi","local","flags"])
def test_unsupported_function(mode):
    d=definition()
    if mode=="static":
        d["defaultLifetime"]="Static"
    elif mode=="task":
        d["subroutineKind"]="Task"
    elif mode=="output":
        d["arguments"][0]["direction"]="Out"
    elif mode=="default":
        d["arguments"][0]["defaultValue"]={}
    elif mode=="global":
        d["body"]["expr"]=named("99 x")
    elif mode=="recursive":
        d["body"]["expr"]=call()
    elif mode=="multi":
        d["body"]={"kind":"List","list":[d["body"],d["body"]]}
    elif mode=="local":
        d["members"].append({"kind":"Variable","name":"temp"})
    else:
        d["flags"]="DPIImport"
    with pytest.raises(Unsupported):
        summarize_function(d)

@pytest.mark.parametrize("mode",["identity","arity","unused_effect","unknown_actual"])
def test_unsupported_call(mode):
    c=call()
    if mode=="identity":
        c["subroutine"]="99 f"
    elif mode=="arity":
        c["arguments"].pop()
    elif mode=="unused_effect":
        c["arguments"][1]=call()
    else:
        c["arguments"][1]=named("99 b")
    with pytest.raises(Unsupported):
        resolve_call(c,{("10","f"):definition()},resolve)

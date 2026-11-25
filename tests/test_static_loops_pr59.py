import copy
import pytest
from rtlprep.static_loops import for_values, expand_loop, Unsupported, declared_loop

def lit(n):
    return {"kind":"IntegerLiteral","type":"int","value":str(n)}

def named(symbol="12 i",type_string="int"):
    return {"kind":"NamedValue","type":type_string,"symbol":symbol}

def decl():
    return {"kind":"Variable","name":"i","addr":12,"type":"int",
            "lifetime":"Automatic","initializer":lit(0)}

def select(symbol,selector):
    return {"kind":"ElementSelect","value":named(symbol,"logic[7:0]"),"selector":selector}

def body():
    return {"kind":"ExpressionStatement","expr":{"kind":"Assignment","isNonBlocking":False,
        "left":select("21 q",named()),
        "right":select("22 a",{"kind":"BinaryOp","op":"Subtract","type":"int",
                              "left":lit(7),"right":named()})}}

def loop():
    return {"kind":"ForLoop","initializers":[],"stopExpr":{"kind":"BinaryOp","op":"LessThan",
        "left":named(),"right":lit(8)},"steps":[{"kind":"UnaryOp","op":"Postincrement",
        "operand":named()}],"body":body()}

def resolve(n):
    return {"21 q":"u.q","22 a":"u.a"}.get(n.get("symbol"))

BOUNDS={"u.q":(7,0),"u.a":(7,0)}

def test_reverse():
    node=loop()
    original=copy.deepcopy(node)
    r=expand_loop(node,decl(),resolve,BOUNDS)
    assert r["iteration_count"]==8
    assert [(e["source_bit"],e["target_bit"]) for e in r["edges"]]==[(7-i,i) for i in range(8)]
    assert node==original

def test_inclusive():
    n=loop()
    n["stopExpr"].update(op="LessThanEqual",right=lit(7))
    assert for_values(n,decl())[1]==list(range(8))

def test_zero_iterations():
    n=loop()
    n["stopExpr"]["right"]=lit(0)
    assert expand_loop(n,decl(),resolve,BOUNDS)["edges"]==[]

def test_repeat():
    b=body()
    b["expr"]["left"]["selector"]=lit(0)
    b["expr"]["right"]["selector"]=lit(1)
    r=expand_loop({"kind":"RepeatLoop","count":lit(3),"body":b},None,resolve,BOUNDS)
    assert r["iteration_count"]==3
    assert [e["iteration"] for e in r["edges"]]==[0,1,2]
    assert all(e["iterator_value"] is None for e in r["edges"])

def test_declaration_link():
    d=decl()
    n=loop()
    b={"kind":"List","list":[{"kind":"VariableDeclaration","symbol":"12 i"},n]}
    assert declared_loop(b,{"members":[d]})==(n,d)
    assert declared_loop(b,{"members":[]}) is None

@pytest.mark.parametrize("mode",["dynamic","too_many","wrong_step","wrong_identity","static",
                                 "external_init","nonlocal","nba","compound","call","self_read",
                                 "oob","wrong_layout","runtime_selector"])
def test_reject(mode):
    n,d=loop(),decl()
    bounds=dict(BOUNDS)
    if mode=="dynamic":
        n["stopExpr"]["right"]=named("99 count")
    elif mode=="too_many":
        n["stopExpr"]["right"]=lit(65)
    elif mode=="wrong_step":
        n["steps"][0]["op"]="Postdecrement"
    elif mode=="wrong_identity":
        n["steps"][0]["operand"]=named("99 i")
    elif mode=="static":
        d["lifetime"]="Static"
    elif mode=="external_init":
        n["initializers"]=[{}]
    elif mode=="nonlocal":
        d=None
    elif mode=="nba":
        n["body"]["expr"]["isNonBlocking"]=True
    elif mode=="compound":
        n["body"]["expr"]["op"]="Add"
    elif mode=="call":
        n["body"]["expr"]={"kind":"Call"}
    elif mode=="self_read":
        n["body"]["expr"]["right"]["value"]=named("21 q")
    elif mode=="oob":
        n["body"]["expr"]["right"]["selector"]=lit(8)
    elif mode=="wrong_layout":
        bounds.pop("u.a")
    else:
        n["body"]["expr"]["right"]["selector"]=named("99 idx")
    with pytest.raises(Unsupported):
        expand_loop(n,d,resolve,bounds)

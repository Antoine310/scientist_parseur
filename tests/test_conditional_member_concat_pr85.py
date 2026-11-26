import copy
import pytest
from rtlprep.array_dependencies import Unsupported
from rtlprep.conditional_member_concat import PARAM_TYPE, parameter_inventory, parameter_value, guard, conditional_constant
from rtlprep.typed_layout import Types

def literal(v):
    return {"kind":"Conversion","type":PARAM_TYPE,"operand":{"kind":"IntegerLiteral","type":"int","value":str(v)}}
def paramref(a,n):
    return {"kind":"NamedValue","type":PARAM_TYPE,"symbol":f"{a} {n}"}
def param(a,n,v,init):
    return {"kind":"Parameter","addr":a,"name":n,"type":PARAM_TYPE,"value":str(v),"initializer":init,"isPort":True}
def instance(name,members):
    return {"kind":"Instance","name":name,"body":{"kind":"InstanceBody","name":"m","members":members}}
def tree(v=0):
    return {"design":{"members":[instance("top",[param(1,"FPU",v,literal(v)),
        instance("child",[param(2,"FPU",v,paramref(1,"FPU")),param(3,"ZFINX",0,literal(0))])])]}}
def eq(l,r):
    return {"kind":"BinaryOp","type":"logic","op":"Equality","left":l,"right":r}
def condition():
    return {"kind":"BinaryOp","type":"logic","op":"LogicalAnd","left":eq(paramref(2,"FPU"),literal(1)),
            "right":eq(paramref(3,"ZFINX"),literal(0))}
def bit(v):
    return {"kind":"Conversion","type":"logic[0:0]","operand":{"kind":"IntegerLiteral","type":"bit[0:0]","value":f"1'b{v}"}}
def conditional():
    return {"kind":"ConditionalOp","type":"logic[0:0]","conditions":[{"expr":condition()}],
            "left":{"kind":"NamedValue","type":"logic[0:0]","symbol":"9 runtime"},"right":bit(0)}
def resolve(owner,e):
    return None
def run(a,t=None,resolver=resolve):
    return conditional_constant(a,"top.child",parameter_inventory(tree() if t is None else t),resolver,Types({}))

def test_independent_parent_parameter_chain_and_ast_preservation():
    a=conditional()
    t=tree()
    before=copy.deepcopy((a,t))
    vals,p=run(a,t)
    assert vals==[0] and p["guard_value"]==0 and p["selected_branch"]=="right"
    assert {(x["instance"],x["name"],x["value"]) for x in p["parameters"]}=={
        ("top","FPU",0),("top.child","FPU",0),("top.child","ZFINX",0)}
    assert (a,t)==before

def test_enabled_runtime_branch_is_not_folded():
    with pytest.raises(Unsupported,match="selected_branch_not_proven_constant"):
        run(conditional(),tree(1))

def test_enabled_literal_branch():
    a=conditional()
    a["left"]=bit(1)
    vals,p=run(a,tree(1))
    assert vals==[1] and p["selected_branch"]=="left"

@pytest.mark.parametrize("mode",["bad_addr","wrong_name","tag_only","decl_value","wrong_parent",
    "wrong_type","runtime","duplicate","unknown","bad_guard_tag","bad_literal_tag","branch_type",
    "multiple_conditions","unsupported_op","bad_param_tag","cycle","missing_init"])
def test_refuse_unproven(mode):
    a=conditional()
    t=tree()
    members=t["design"]["members"][0]["body"]["members"]
    child=members[1]["body"]["members"]
    g=a["conditions"][0]["expr"]
    resolver=resolve
    if mode=="bad_addr": g["left"]["left"]["symbol"]="22 FPU"
    elif mode=="wrong_name": g["left"]["left"]["symbol"]="2 OTHER"
    elif mode=="tag_only":
        child.pop(0)
        g["left"]["left"]["constant"]="0"
    elif mode=="decl_value": child[0]["value"]="1"
    elif mode=="wrong_parent": child[0]["initializer"]["symbol"]="3 ZFINX"
    elif mode=="wrong_type": child[0]["type"]="int"
    elif mode=="runtime": resolver=lambda owner,e:"top.child.runtime" if e.get("symbol")=="2 FPU" else None
    elif mode=="duplicate": child.append(copy.deepcopy(child[0]))
    elif mode=="unknown": members[0]["initializer"]["operand"]["value"]="x"
    elif mode=="bad_guard_tag": g["constant"]="1'b1"
    elif mode=="bad_literal_tag": a["right"]["constant"]="1'b1"
    elif mode=="branch_type": a["left"]["type"]="logic[1:0]"
    elif mode=="multiple_conditions": a["conditions"].append(copy.deepcopy(a["conditions"][0]))
    elif mode=="unsupported_op": g["op"]="LogicalOr"
    elif mode=="bad_param_tag": g["left"]["left"]["constant"]="1"
    elif mode=="cycle": members[0]["initializer"]=paramref(1,"FPU")
    else: child[0].pop("initializer")
    with pytest.raises(Unsupported):
        run(a,t,resolver)

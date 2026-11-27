import copy
import pytest
from rtlprep.concat_nba_targets import expand, Refusal


def named(name):
    return {"kind":"NamedValue","symbol":name,"type":"logic"}


def concat(*names):
    return {"kind":"Concatenation","type":f"logic[{len(names)-1}:0]","operands":[named(x) for x in names]}


def node(zero=False):
    rhs=concat("qq","q","serial_in")
    if zero:
        rhs={"kind":"Conversion","type":"logic[2:0]","constant":"3'b0",
             "operand":{"kind":"IntegerLiteral","type":"bit[2:0]","value":"3'b0","constant":"3'b0"}}
    return {"kind":"Assignment","type":"logic[2:0]","isNonBlocking":True,
            "left":concat("ck","qq","q"),"right":rhs}


def run(n,context="Always",variables=None,declared=None,nodes=None):
    names={"ck","qq","q","serial_in"}
    return expand(n,context,lambda x:x.get("symbol"),
                  {k:"logic" for k in names} if declared is None else declared,
                  {"ck","qq","q"} if variables is None else variables,
                  names if nodes is None else nodes)


def test_sampled_lsb_order():
    rows=run(node())
    assert [(x["concat_lsb_position"],x["target"]["signal"],x["source"]["signal"]) for x in rows]==[
        (0,"q","serial_in"),(1,"qq","q"),(2,"ck","qq")]
    assert all(x["relation"]=="nba_sampled_position_candidate" and x["constant"] is None for x in rows)


def test_zero_conversion():
    rows=run(node(True),"AlwaysFF")
    assert [x["target"]["signal"] for x in rows]==["q","qq","ck"]
    assert all(x["constant"]==0 and x["source"] is None for x in rows)


def test_direct_zero():
    n=node(True)
    n["right"]={"kind":"IntegerLiteral","type":"logic[2:0]","value":"3'b000"}
    assert len(run(n))==3


@pytest.mark.parametrize("bad",["blocking","timing","op","initial","alias","vector","two_state","unresolved",
    "not_variable","missing_node","type_disagreement","lhs_width","rhs_width","assignment_width",
    "nested","literal_nonzero","literal_x","literal_z","literal_wrong_width","conversion_width",
    "constant_disagreement","signed","arity","rhs_unsupported","source_type"])
def test_refusal(bad):
    n=node(bad in {"literal_nonzero","literal_x","literal_z","literal_wrong_width","conversion_width","constant_disagreement"})
    kw={}
    a=n["left"]["operands"]
    if bad=="blocking": n["isNonBlocking"]=False
    elif bad=="timing": n["timingControl"]={}
    elif bad=="op": n["op"]="Add"
    elif bad=="initial": kw["context"]="Initial"
    elif bad=="alias": a[1]=copy.deepcopy(a[0])
    elif bad=="vector": a[0]["type"]="logic[1:0]"
    elif bad=="two_state": a[0]["type"]="bit"
    elif bad=="unresolved": a[0]["symbol"]="missing"
    elif bad=="not_variable": kw["variables"]={"qq","q"}
    elif bad=="missing_node": kw["nodes"]={"ck","qq","q"}
    elif bad=="type_disagreement": kw["declared"]={"ck":"reg","qq":"logic","q":"logic","serial_in":"logic"}
    elif bad=="lhs_width": n["left"]["type"]="logic[3:0]"
    elif bad=="rhs_width": n["right"]["type"]="logic[3:0]"
    elif bad=="assignment_width": n["type"]="logic[3:0]"
    elif bad=="nested": a[0]=concat("ck","qq")
    elif bad=="literal_nonzero": n["right"]["operand"]["value"]="3'b1"
    elif bad=="literal_x": n["right"]["operand"]["value"]="3'bx"
    elif bad=="literal_z": n["right"]["operand"]["value"]="3'bz"
    elif bad=="literal_wrong_width": n["right"]["operand"]["value"]="4'b0"
    elif bad=="conversion_width": n["right"]["operand"]["type"]="bit[3:0]"
    elif bad=="constant_disagreement": n["right"]["constant"]="3'b1"
    elif bad=="signed": n["left"]["type"]="logic signed[2:0]"
    elif bad=="arity": n["left"]["operands"]=[named("ck")]*33
    elif bad=="rhs_unsupported": n["right"]={"kind":"BinaryOp","type":"logic[2:0]"}
    else: n["right"]["operands"][0]["type"]="bit"
    with pytest.raises(Refusal):
        run(n,**kw)

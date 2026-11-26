import copy
import pytest

from rtlprep.array_dependencies import Unsupported
from rtlprep.member_expressions import expand
from rtlprep.packed_members import observed_members
from rtlprep.typed_layout import Types

RAW="10 p::Triple_t"

def inventory():
    return Types({"design":{"members":[{"kind":"Package","name":"p","members":[
        {"kind":"TypeAlias","addr":10,"name":"Triple_t",
         "target":"struct packed{logic a;logic b;logic c;}p::s$1"}]}]}})

def named(n,a,t):
    return {"kind":"NamedValue","symbol":f"{a} {n}","type":t}

def member(field):
    return {"kind":"MemberAccess","type":"logic","member":f"{21+'abc'.index(field)} {field}",
            "value":named("bundle",1,RAW)}

def neg(e):
    return {"kind":"UnaryOp","type":"logic","op":"LogicalNot","operand":e}

def both(l,r):
    return {"kind":"BinaryOp","type":"logic","op":"LogicalAnd","left":l,"right":r}

def logical():
    return {"kind":"Assignment","isNonBlocking":False,"type":"logic",
            "left":named("flag",2,"logic"),"right":both(member("a"),neg(both(member("b"),neg(member("c")))))}

def concat():
    return {"kind":"Assignment","isNonBlocking":False,"type":"logic[4:0]",
            "left":named("readback",3,"logic[4:0]"),
            "right":{"kind":"Concatenation","type":"logic[4:0]",
                     "operands":[member("a"),named("extra",4,"logic[1:0]"),member("b"),member("c")]}}

def run(a,extra=None):
    t=inventory()
    return expand(a,lambda e:{"1 bundle":"top.bundle","2 flag":"top.flag","3 readback":"top.readback"}.get(e.get("symbol")),
                  {"top.bundle":RAW,"top.flag":"logic","top.readback":"logic[4:0]"},
                  t,observed_members([a,extra],t))

def test_logical_references_not_copy_and_ast_unchanged():
    a=logical()
    before=copy.deepcopy(a)
    e,g=run(a)
    assert not g and {(x["source_bit"],x["target_bit"]) for x in e}=={(0,0),(1,0),(2,0)}
    assert {x["relation"] for x in e}=={"logical_member_reference_candidate"}
    assert a==before

def test_repeated_reference_deduplication():
    a=logical()
    a["right"]=both(member("a"),member("a"))
    e,g=run(a)
    assert not g and len(e)==1 and e[0]["source_bit"]==2

def test_concat_partial_positions():
    e,g=run(concat())
    assert {(x["source_bit"],x["target_bit"]) for x in e}=={(0,0),(1,1),(2,4)}
    assert g==[{"kind":"NamedValue","target_bits":[2,3]}]
    assert {x["relation"] for x in e}=={"concat_member_position_candidate"}

@pytest.mark.parametrize("mode",["nba","compound","timing","target","type","operator","unary",
                                  "field","identity","conflict","concat_width","opaque_type","nested_member"])
def test_fail_closed(mode):
    a=concat() if mode in ("concat_width","opaque_type","nested_member") else logical()
    extra=None
    if mode=="nba": a["isNonBlocking"]=True
    elif mode=="compound": a["op"]="Add"
    elif mode=="timing": a["timingControl"]={}
    elif mode=="target": a["left"]["symbol"]="99 flag"
    elif mode=="type": a["right"]["type"]="logic[0:0]"
    elif mode=="operator": a["right"]["op"]="Add"
    elif mode=="unary": a["right"]["right"]["op"]="BitwiseNot"
    elif mode=="field": a["right"]["left"]["member"]="21 absent"
    elif mode=="identity": a["right"]["left"]["value"]["symbol"]="99 bundle"
    elif mode=="conflict":
        extra=member("a")
        extra["member"]="99 a"
    elif mode=="concat_width": a["right"]["operands"].pop()
    elif mode=="opaque_type": a["right"]["operands"][1]["type"]="logic signed[1:0]"
    else: a["right"]["operands"][0]["value"]=member("b")
    with pytest.raises(Unsupported):
        run(a,extra)

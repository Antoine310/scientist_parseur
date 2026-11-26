import copy
import pytest
from rtlprep.array_dependencies import Unsupported
from rtlprep.member_patterns import binary_literal, expand
from rtlprep.packed_members import observed_members
from rtlprep.typed_layout import Types

RAW="10 p::Pair_t"
def types():
    return Types({"design":{"members":[{"kind":"Package","name":"p","members":[
        {"kind":"TypeAlias","addr":10,"name":"Pair_t","target":"struct packed{logic a;logic b;}p::s$1"}]}]}})
def named(n,a,t):
    return {"kind":"NamedValue","symbol":f"{a} {n}","type":t}
def member(f,base="d",addr=1):
    return {"kind":"MemberAccess","type":"logic","member":f"{21 if f=='a' else 22} {f}",
            "value":named(base,addr,RAW)}
def lit(value="1'b0",typ="bit[0:0]"):
    return {"kind":"IntegerLiteral","type":typ,"value":value}
def pattern():
    return {"kind":"Assignment","type":RAW,"isNonBlocking":True,"left":named("q",2,RAW),
            "right":{"kind":"StructuredAssignmentPattern","type":RAW,"memberSetters":[
                {"member":"22 b","expr":{"kind":"Conversion","type":"logic","operand":lit()}},
                {"member":"21 a","expr":member("a")}]}}
def concat():
    return {"kind":"Assignment","type":"logic[2:0]","isNonBlocking":False,
            "left":named("out",3,"logic[2:0]"),
            "right":{"kind":"Concatenation","type":"logic[2:0]","operands":[member("a"),lit("2'b10","bit[1:0]")]}}
def run(a,context="AlwaysFF"):
    t=types()
    observed=observed_members([a,member("a","q",2),member("b","q",2)],t)
    return expand(a,context,lambda e:{"1 d":"top.d","2 q":"top.q","3 out":"top.out"}.get(e.get("symbol")),
                  {"top.d":RAW,"top.q":RAW,"top.out":"logic[2:0]"},t,observed)

def test_pattern_order_independent_and_no_mutation():
    a=pattern()
    before=copy.deepcopy(a)
    k,e,c,g=run(a)
    assert k=="nba" and not g
    assert [(x["source_bit"],x["target_bit"]) for x in e]==[(1,1)]
    assert [(x["target_bit"],x["value"]) for x in c]==[(0,0)]
    assert a==before
def test_concat_literal_positions():
    k,e,c,g=run(concat(),"continuous")
    assert k=="concat" and not e
    assert [(x["target_bit"],x["value"]) for x in c]==[(0,0),(1,1)]
    assert g==[{"kind":"MemberAccess","target_bits":[2]}]

@pytest.mark.parametrize("value",["4'b101","4'd5","4'h5"])
def test_literal_radices(value):
    assert binary_literal(lit(value,"bit[3:0]"),"bit[3:0]")==[1,0,1,0]

@pytest.mark.parametrize("value",["3'b0","4'bx","4'bz","4'd16","4'h10","4'sd0","4'o0","4'b2"])
def test_bad_literal(value):
    with pytest.raises(Unsupported):
        binary_literal(lit(value,"bit[3:0]"),"bit[3:0]")

@pytest.mark.parametrize("mode",["blocking","context","duplicate","missing","unknown","wrong_type",
                                  "identity","source_type","bad_constant","timing","compound"])
def test_refuse_incomplete_pattern(mode):
    a=pattern()
    s=a["right"]["memberSetters"]
    context="AlwaysFF"
    if mode=="blocking": a["isNonBlocking"]=False
    elif mode=="context": context="AlwaysComb"
    elif mode=="duplicate": s[0]=copy.deepcopy(s[1])
    elif mode=="missing": s.pop()
    elif mode=="unknown": s[0]["member"]="99 b"
    elif mode=="wrong_type": a["right"]["type"]="logic"
    elif mode=="identity": a["left"]["symbol"]="99 q"
    elif mode=="source_type": s[1]["expr"]["type"]="bit"
    elif mode=="bad_constant": s[0]["expr"]["constant"]="1'b1"
    elif mode=="timing": a["timingControl"]={}
    else: a["op"]="Add"
    with pytest.raises(Unsupported):
        run(a,context)

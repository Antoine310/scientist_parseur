import copy
import pytest
from rtlprep import constant_increments as m
from rtlprep.array_dependencies import layout, Unsupported


def fixture(n=4,aligned=False):
    t=f"logic[{n-1}:0]"
    def named(s): return {"kind":"NamedValue","type":t,"symbol":s}
    def lit(v,t="int"): return {"kind":"IntegerLiteral","type":t,"value":str(v)}
    a=named("a")
    if aligned:
        a={"kind":"Concatenation","type":t,"operands":[
            {"kind":"RangeSelect","type":"logic[31:2]","selectionKind":"Simple",
             "value":a,"left":lit(31),"right":lit(2)},
            lit("2'b0","bit[1:0]")]}
    right={"kind":"Conversion","type":t,"operand":lit(4 if aligned else 1)}
    node={"kind":"Assignment","type":t,"isNonBlocking":False,"left":named("s"),
          "right":{"kind":"BinaryOp","op":"Add","type":t,"left":a,"right":right}}
    raw={s:t for s in ("s","a")}
    return node,lambda e:e.get("symbol"),raw,{s:layout(t) for s in raw},{}


def oracle(n):
    result=set()
    for x in range(1<<n):
        y=(x+1)% (1<<n)
        for j in range(n):
            z=((x^(1<<j))+1)%(1<<n)
            for i in range(n):
                if (z^y)&(1<<i):
                    result.add((j,i))
    return result


@pytest.mark.parametrize("n",[1,2,3,4])
def test_exhaustive(n):
    c=m.expand(*fixture(n))
    assert {(j,i) for i,p in enumerate(c["prefix_lengths"]) for j in range(p)}==oracle(n)
    assert c["potential_pairs"]==len(oracle(n))


def test_counter_64():
    c=m.expand(*fixture(64))
    assert c["potential_pairs"]==2080 and c["prefix_lengths"]==list(range(1,65))
    assert c["constant_addend"]==1 and not c["constant_result_positions"]


def test_aligned():
    args=fixture(32,True)
    before=copy.deepcopy(args[0])
    c=m.expand(*args)
    assert c["potential_pairs"]==465 and c["prefix_lengths"]==[0,0]+list(range(1,31))
    assert c["operands"][0]["bits_lsb_first"]==list(range(2,32))
    assert c["constant_result_positions"]==[{"bit":0,"value":0},{"bit":1,"value":0}]
    assert args[0]==before


@pytest.mark.parametrize("bad,reason",[
    ("nba","not_plain_blocking_assignment"),("compound","not_plain_blocking_assignment"),
    ("subtract","not_direct_addition"),("unknown","unproven_increment_constant"),
    ("wrong_value","unproven_increment_constant"),("fake_tag","unproven_increment_constant"),
    ("runtime","increment_constant_not_literal"),("nested_conversion","increment_constant_not_literal"),
    ("state","increment_width_or_state_mismatch"),("identity","unproven_exact_signal_identity_or_type"),
    ("bad_suffix","unproven_alignment_zero_suffix"),("unaligned","not_aligned_address_increment"),
    ("bad_width","alignment_leaf_width_or_state_mismatch")])
def test_refuse(bad,reason):
    node,resolve,raw,d,constants=fixture(32,bad in ("bad_suffix","bad_width"))
    rhs=node["right"]
    if bad=="nba": node["isNonBlocking"]=True
    elif bad=="compound": node["op"]="Add"
    elif bad=="subtract": rhs["op"]="Subtract"
    elif bad=="unknown": rhs["right"]["operand"]["value"]="32'hx"
    elif bad=="wrong_value": rhs["right"]["operand"]["value"]="3"
    elif bad=="fake_tag": rhs["right"]["constant"]="2"
    elif bad=="runtime": rhs["right"]["operand"]={"kind":"NamedValue","type":"int","symbol":"x","constant":"1"}
    elif bad=="nested_conversion": rhs["right"]["operand"]={"kind":"Conversion","type":"int","operand":rhs["right"]["operand"]}
    elif bad=="state": rhs["left"]["type"]="bit[31:0]"
    elif bad=="identity": rhs["left"]["symbol"]="unknown"
    elif bad=="bad_suffix": rhs["left"]["operands"][1]["value"]="2'b01"
    elif bad=="unaligned": rhs["right"]["operand"]["value"]="4"
    else: rhs["left"]["operands"][0]["type"]="logic[30:2]"
    with pytest.raises(Unsupported,match="^"+reason+"$"):
        m.expand(node,resolve,raw,d,constants)


def test_missing_carry_mutant():
    c=m.expand(*fixture(4))
    c["prefix_lengths"]=[1]*4
    assert {(j,i) for i,p in enumerate(c["prefix_lengths"]) for j in range(p)}!=oracle(4)


@pytest.mark.parametrize("n",[4,64])
def test_capture_gate_requires_selection(n):
    # A whole-vector increment is outside the historical flat census.
    # The integration fixture uses a proper subrange of a wider declaration.
    from rtlprep.bitaccess import _contains_selection
    node,_,_,_,_=fixture(n)
    assert not _contains_selection(node["left"],[0])
    assert not _contains_selection(node["right"],[0])
    rhs=node["right"]
    rhs["left"]={"kind":"RangeSelect","type":f"logic[{n-1}:0]",
                 "selectionKind":"Simple",
                 "value":{"kind":"NamedValue","type":f"logic[{n}:0]","symbol":"a"},
                 "left":{"kind":"IntegerLiteral","type":"int","value":str(n-1)},
                 "right":{"kind":"IntegerLiteral","type":"int","value":"0"}}
    assert _contains_selection(rhs,[0])

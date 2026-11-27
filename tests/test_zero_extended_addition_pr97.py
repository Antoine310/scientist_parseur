import copy
import pytest
from rtlprep import zero_extended_additions as m
from rtlprep.array_dependencies import layout, Unsupported

def make(n=3):
    typ=f"logic[{n-1}:0]"
    leaf=f"logic[{n-2}:0]" if n>2 else "logic"
    def named(s,t): return {"kind":"NamedValue","symbol":s,"type":t}
    def lit(v): return {"kind":"IntegerLiteral","type":"int","value":str(v)}
    def select(s,i):
        return {"kind":"ElementSelect","type":leaf,"value":named(s,f"logic[3:0]"+(leaf[5:] if n>2 else "[0:0]")),
                "selector":lit(i)}
    # Slang's scalar selection from a packed array has a one-bit vector type.
    if n==2:
        leaf="logic[0:0]"
    def operand(s,i):
        return {"kind":"Concatenation","type":typ,"operands":[
                {"kind":"IntegerLiteral","type":"bit[0:0]","value":"1'b0"},select(s,i)]}
    node={"kind":"Assignment","type":typ,"isNonBlocking":False,"left":named("s",typ),
          "right":{"kind":"BinaryOp","op":"Add","type":typ,"left":operand("a",0),"right":operand("a",1)}}
    raw={"s":typ,"a":node["right"]["left"]["operands"][1]["value"]["type"]}
    return node,lambda e:e.get("symbol"),raw,{k:layout(v) for k,v in raw.items()},{}

def oracle(m):
    pairs=set()
    for a in range(1<<m):
        for b in range(1<<m):
            y=a+b
            for side in (0,1):
                for j in range(m):
                    x=(a^(1<<j))+b if side==0 else a+(b^(1<<j))
                    for i in range(m+1):
                        if (x^y)&(1<<i):
                            pairs.add((side,j,i))
    return pairs

@pytest.mark.parametrize("width",[2,3,4,5,6])
def test_exhaustive(width):
    c=m.expand(*make(width))
    actual={(s,j,i) for i,p in enumerate(c["prefix_lengths"]) for s in (0,1) for j in range(p)}
    assert actual==oracle(width-1) and len(actual)==c["potential_pairs"]
    assert c["operands"][0]["outer_packed_indices"]==[0]
    assert c["operands"][1]["outer_packed_indices"]==[1]

def test_lexical_selector_not_tag():
    n,resolve,raw,d,constants=make()
    sel=n["right"]["left"]["operands"][1]
    sel["selector"]={"kind":"NamedValue","type":"integer","symbol":"123 i","constant":"2"}
    with pytest.raises(Unsupported,match="unproven_lexical_selector"):
        m.expand(n,resolve,raw,d,constants)
    constants["123"]=("i",2)
    before=copy.deepcopy(n)
    c=m.expand(n,resolve,raw,d,constants)
    assert c["operands"][0]["outer_packed_indices"]==[2]
    assert c["operands"][0]["selector_proofs"][0]["index"]==2 and n==before
    constants["123"]=("other",2)
    with pytest.raises(Unsupported,match="unproven_lexical_selector"):
        m.expand(n,resolve,raw,d,constants)

@pytest.mark.parametrize("bad,reason",[
    ("nonzero","unproven_single_zero_prefix"),("unknown","unproven_single_zero_prefix"),
    ("width","unproven_single_zero_prefix"),("overlap","overlapping_operand_coordinates"),
    ("out_of_range","index_outside_declared_dimension"),
    ("bad_tag","unproven_lexical_selector"),("wrong_type","unproven_exact_signal_identity_or_type"),
    ("conversion","not_single_zero_extended_operand"),("state","zero_extended_leaf_width_or_state_mismatch")])
def test_refuse(bad,reason):
    n,resolve,raw,d,c=make()
    a=n["right"]["left"]
    z,e=a["operands"]
    if bad=="nonzero": z["value"]="1'b1"
    elif bad=="unknown": z["value"]="1'bx"
    elif bad=="width": z.update(type="bit[1:0]",value="2'b00")
    elif bad=="overlap": n["right"]["right"]=copy.deepcopy(a)
    elif bad=="out_of_range": e["selector"]["value"]="4"
    elif bad=="bad_tag": e["selector"]["constant"]="1"
    elif bad=="wrong_type": e["value"]["type"]="logic[4:0][1:0]"
    elif bad=="conversion": n["right"]["left"]={"kind":"Conversion","type":a["type"],"operand":a}
    else: e["type"]="bit[1:0]"
    with pytest.raises(Unsupported,match="^"+reason+"$"):
        m.expand(n,resolve,raw,d,c)

def test_carry_mutant():
    c=m.expand(*make(6))
    assert (0,4,5) in oracle(5)
    c["prefix_lengths"][-1]=0
    assert {(s,j,i) for i,p in enumerate(c["prefix_lengths"]) for s in (0,1) for j in range(p)}!=oracle(5)

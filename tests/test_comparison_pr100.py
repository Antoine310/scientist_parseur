import copy
import pytest
from rtlprep import comparison_candidates as m
from rtlprep.array_dependencies import layout, Unsupported


def fixture(n=2,op="Equality"):
    t=f"logic[{n-1}:0]"
    raw={"a":t,"b":t,"s":"logic"}
    def sig(s): return {"kind":"NamedValue","type":raw[s],"symbol":s}
    node={"kind":"Assignment","type":"logic","isNonBlocking":False,"left":sig("s"),
          "right":{"kind":"BinaryOp","op":op,"type":"logic","left":sig("a"),"right":sig("b")}}
    return node,lambda e:e.get("symbol"),raw,{s:layout(t) for s,t in raw.items()},{}


def literal(n,value):
    return {"kind":"Conversion","type":f"logic[{n-1}:0]","operand":
            {"kind":"IntegerLiteral","type":f"bit[{n-1}:0]","value":f"{n}'d{value}"}}


def parameter_slice():
    return {"kind":"Conversion","type":"logic[1:0]","constant":"2'b10","operand":
            {"kind":"RangeSelect","type":"bit[1:0]","selectionKind":"Simple","constant":"2'b10",
             "value":{"kind":"NamedValue","type":"int unsigned","symbol":"1 DEPTH","constant":"32'd2"},
             "left":{"kind":"NamedValue","type":"int unsigned","symbol":"2 ADDR","constant":"32'd1"},
             "right":{"kind":"IntegerLiteral","type":"int","value":"0"}}}


@pytest.mark.parametrize("n",[1,2,3,4])
@pytest.mark.parametrize("op",["Equality","Inequality"])
def test_independent_exhaustive_direct(n,op):
    args=fixture(n,op)
    before=copy.deepcopy(args[0])
    c=m.expand(*args)
    f=(lambda a,b:a==b) if op=="Equality" else (lambda a,b:a!=b)
    observed={(s,j) for a in range(1<<n) for b in range(1<<n) for s in (0,1) for j in range(n)
              if f(a,b)!= (f(a^(1<<j),b) if s==0 else f(a,b^(1<<j)))}
    actual={(side,j) for side,e in zip(c["operand_sides"],c["operands"]) for j in e["bits_lsb_first"]}
    assert observed==actual and c["potential_pairs"]==len(observed)
    assert args[0]==before
    if n>1:
        assert observed!={(0,0),(1,0)}


@pytest.mark.parametrize("value",range(4))
@pytest.mark.parametrize("op",["Equality","Inequality"])
@pytest.mark.parametrize("side",[0,1])
def test_constant_exhaustive(value,op,side):
    args=fixture(2,op)
    args[0]["right"][("left","right")[side]]=literal(2,value)
    c=m.expand(*args)
    f=(lambda a:a==value) if op=="Equality" else (lambda a:a!=value)
    observed={j for a in range(4) for j in range(2) if f(a)!=f(a^(1<<j))}
    assert c["operand_sides"]==[1-side] and c["constant_operands"][0]["value"]==value
    assert set(c["operands"][0]["bits_lsb_first"])==observed
    assert c["potential_pairs"]==len(observed)


def test_parameter_slice():
    args=fixture()
    args[0]["right"]["right"]=parameter_slice()
    args[4].update({"1":("DEPTH",2),"2":("ADDR",1)})
    c=m.expand(*args)
    assert c["constant_operands"][0]["value"]==2 and c["potential_pairs"]==2


@pytest.mark.parametrize("bad",["alias","order","case","nba","conversion","width","signed",
                                "unknown_literal","tag","runtime_tag","parameter_missing","parameter_bad_tag",
                                "parameter_bad_bound","result_width"])
def test_refusals(bad):
    args=fixture()
    node=args[0]; rhs=node["right"]
    if bad=="alias": rhs["right"]=copy.deepcopy(rhs["left"])
    elif bad=="order": rhs["op"]="GreaterThan"
    elif bad=="case": rhs["op"]="CaseEquality"
    elif bad=="nba": node["isNonBlocking"]=True
    elif bad=="conversion": node["right"]={"kind":"Conversion","type":"logic","operand":rhs}
    elif bad=="width": rhs["right"]["type"]="logic[2:0]"
    elif bad=="signed": rhs["right"]["type"]="logic signed[1:0]"
    elif bad=="result_width": rhs["type"]="logic[1:0]"
    elif bad=="unknown_literal":
        rhs["right"]=literal(2,0);rhs["right"]["operand"]["value"]="2'bx0"
    elif bad=="tag":
        rhs["right"]=literal(2,1);rhs["right"]["constant"]="2'd2"
    elif bad=="runtime_tag":
        rhs["right"]={"kind":"NamedValue","type":"logic[1:0]","symbol":"unbound","constant":"2'd1"}
    else:
        rhs["right"]=parameter_slice()
        if bad!="parameter_missing": args[4].update({"1":("DEPTH",2),"2":("ADDR",1)})
        if bad=="parameter_bad_tag": rhs["right"]["operand"]["constant"]="2'b11"
        if bad=="parameter_bad_bound": rhs["right"]["operand"]["left"]={"kind":"IntegerLiteral","type":"int","value":"0"}
    with pytest.raises(Unsupported):
        m.expand(*args)

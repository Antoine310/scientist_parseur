import copy
import pytest
from rtlprep import signed_order_candidates as m
from rtlprep.array_dependencies import layout, Unsupported


def fixture(n=8):
    t=f"logic[{n-1}:0]"
    raw={"a":t,"b":t,"c":"logic","d":"logic","y":"logic"}
    def sig(s): return {"kind":"NamedValue","type":raw[s],"symbol":s}
    def side(s):
        msb={"kind":"ElementSelect","type":"logic","value":sig(s),
             "selector":{"kind":"IntegerLiteral","type":"int","value":str(n-1)}}
        sign={"kind":"BinaryOp","type":"logic","op":"BinaryAnd","left":msb,"right":sig("c")}
        return {"kind":"Call","type":f"logic signed[{n}:0]","subroutine":"$signed",
                "arguments":[{"kind":"Concatenation","type":f"logic[{n}:0]","operands":[sign,sig(s)]}]}
    node={"kind":"Assignment","type":"logic","isNonBlocking":False,"left":sig("y"),
          "right":{"kind":"BinaryOp","type":"logic","op":"GreaterThan","left":side("a"),"right":side("b")}}
    return node,lambda e:e.get("symbol"),raw,{s:layout(t) for s,t in raw.items()},{}


def signed_value(x,n,mode):
    return x-(1<<n) if mode and x&(1<<(n-1)) else x


@pytest.mark.parametrize("n",[2,3,4])
def test_exhaustive_support(n):
    args=fixture(n); before=copy.deepcopy(args[0]); c=m.expand(*args)
    def cmp(a,b,mode): return signed_value(a,n,mode)>signed_value(b,n,mode)
    observed=set()
    for a in range(1<<n):
        for b in range(1<<n):
            for mode in range(2):
                y=cmp(a,b,mode)
                for j in range(n):
                    if y!=cmp(a^(1<<j),b,mode): observed.add(("a",j))
                    if y!=cmp(a,b^(1<<j),mode): observed.add(("b",j))
                if y!=cmp(a,b,mode^1): observed.add(("c",0))
    actual={(e["signal"],j) for e in c["operands"] for j in e["bits_lsb_first"]}
    assert observed==actual and len(actual)==c["potential_pairs"]==2*n+1
    assert args[0]==before
    assert cmp(1<<(n-1),0,0)!=cmp(1<<(n-1),0,1)


def test_eight_bit_unique_coordinates():
    c=m.expand(*fixture())
    assert c["potential_pairs"]==17 and c["shared_control_occurrences"]==2
    assert [len(e["bits_lsb_first"]) for e in c["operands"]]==[8,8,1]
    assert [e["bits_lsb_first"] for e in c["sign_msb_evidence"]]==[[7],[7]]


@pytest.mark.parametrize("bad",["unsigned_call","call_arity","call_width","concat_width","concat_arity","sign_or",
                                "wrong_msb","other_control","same_data","control_alias","target_alias","nba",
                                "operator","result_type","signed_data","runtime_index","wrapped_rhs","different_width"])
def test_refusals(bad):
    args=fixture(); node=args[0]; rhs=node["right"]
    a,b=rhs["left"],rhs["right"]
    ca,cb=a["arguments"][0],b["arguments"][0]
    sa,sb=ca["operands"][0],cb["operands"][0]
    if bad=="unsigned_call": a["subroutine"]="$unsigned"
    elif bad=="call_arity": a["arguments"].append(copy.deepcopy(ca))
    elif bad=="call_width": a["type"]="logic signed[9:0]"
    elif bad=="concat_width": ca["type"]="logic[7:0]"
    elif bad=="concat_arity": ca["operands"].append(copy.deepcopy(sa))
    elif bad=="sign_or": sa["op"]="BinaryOr"
    elif bad=="wrong_msb": sa["left"]["selector"]["value"]="6"
    elif bad=="other_control": sb["right"]["symbol"]="d"
    elif bad=="same_data": rhs["right"]=copy.deepcopy(a)
    elif bad=="control_alias":
        sa["right"]=copy.deepcopy(sa["left"]); sb["right"]=copy.deepcopy(sa["left"])
    elif bad=="target_alias": node["left"]["symbol"]="c"
    elif bad=="nba": node["isNonBlocking"]=True
    elif bad=="operator": rhs["op"]="LessThan"
    elif bad=="result_type": rhs["type"]="bit"
    elif bad=="signed_data": ca["operands"][1]["type"]="logic signed[7:0]"
    elif bad=="runtime_index": sa["left"]["selector"]={"kind":"NamedValue","type":"int","symbol":"unbound","constant":"7"}
    elif bad=="wrapped_rhs": node["right"]={"kind":"Conversion","type":"logic","operand":rhs}
    else:
        other=fixture(4)
        rhs["right"]=other[0]["right"]["right"];args[2]["b"]="logic[3:0]";args[3]["b"]=layout("logic[3:0]")
    with pytest.raises(Unsupported):
        m.expand(*args)

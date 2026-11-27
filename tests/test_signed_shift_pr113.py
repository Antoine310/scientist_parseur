import copy
import pytest
from rtlprep.signed_shift_candidates import expand,Unsupported
from rtlprep.array_dependencies import layout


def site(n=8):
    m={4:2,8:3,16:4}[n]
    t=f"logic[{n-1}:0]"
    raw={"d":t,"k":f"logic[{m-1}:0]","mode":"logic","y":t}
    def sig(s): return {"kind":"NamedValue","type":raw[s],"symbol":s}
    msb={"kind":"ElementSelect","type":"logic","value":sig("d"),
         "selector":{"kind":"IntegerLiteral","type":"int","value":str(n-1),"constant":str(n-1)}}
    sign={"kind":"BinaryOp","type":"logic","op":"BinaryAnd","left":sig("mode"),"right":msb}
    cat={"kind":"Concatenation","type":f"logic[{n}:0]","operands":[sign,sig("d")]}
    call={"kind":"Call","type":f"logic signed[{n}:0]","subroutine":"$signed","arguments":[cat]}
    op={"kind":"BinaryOp","type":call["type"],"op":"ArithmeticShiftRight","left":call,"right":sig("k")}
    node={"kind":"Assignment","type":t,"isNonBlocking":False,"left":sig("y"),
          "right":{"kind":"Conversion","type":t,"operand":op}}
    return node,lambda e:e.get("symbol"),raw,{s:layout(t) for s,t in raw.items()},{}


@pytest.mark.parametrize("n",[4,8])
def test_exhaustive_binary_sensitivity(n):
    args=site(n);before=copy.deepcopy(args[0]);c=expand(*args)
    m=c["amount_width"]
    def oracle(d,k,mode):
        value=d-(1<<n) if mode and d&(1<<(n-1)) else d
        return (value//(2**k))%2**n
    observed=[set() for _ in range(n)]
    for d in range(2**n):
        for k in range(2**m):
            for mode in range(2):
                base=oracle(d,k,mode)
                for b in range(n+m+1):
                    other=(oracle(d^(1<<b),k,mode) if b<n else
                           oracle(d,k^(1<<(b-n)),mode) if b<n+m else oracle(d,k,mode^1))
                    diff=base^other
                    for i in range(n):
                        if diff&(1<<i): observed[i].add(b)
    assert observed==[set(l["data_ordinals"])|{n+j for j in l["amount_ordinals"]}|
                      {n+m+j for j in l["mode_ordinals"]} for l in c["lane_support"]]
    assert c["potential_pairs"]==sum(map(len,observed))
    assert args[0]==before


def test_sixteen_and_commuted_sign():
    args=site(16);n=args[0]
    sign=n["right"]["operand"]["left"]["arguments"][0]["operands"][0]
    sign["left"],sign["right"]=sign["right"],sign["left"]
    c=expand(*args)
    assert c["potential_pairs"]==215
    assert c["lane_support"][0]=={"data_ordinals":list(range(16)),"amount_ordinals":list(range(4)),"mode_ordinals":[]}
    assert c["lane_support"][-1]=={"data_ordinals":[15],"amount_ordinals":list(range(4)),"mode_ordinals":[0]}


@pytest.mark.parametrize("bad",["nba","timing","compound","wrong_target_type","missing_conversion","wrong_conversion",
    "logical_shift","wrong_signed_width","unsigned_call","wrong_call_type","call_arity","cat_arity","cat_type",
    "sign_or","wrong_msb","wrong_msb_identity","mode_alias","target_alias","amount_alias","amount_width",
    "signed_amount","two_state_data","unresolved","wrong_range_type","dynamic_selector","ascending"])
def test_refusals(bad):
    args=site();n=args[0];rhs=n["right"];op=rhs["operand"];call=op["left"];cat=call["arguments"][0]
    sign,data=cat["operands"]
    if bad=="nba": n["isNonBlocking"]=True
    elif bad=="timing": n["timingControl"]={}
    elif bad=="compound": n["op"]="Add"
    elif bad=="wrong_target_type": n["type"]="logic[6:0]"
    elif bad=="missing_conversion": n["right"]=op
    elif bad=="wrong_conversion": rhs["type"]="logic[6:0]"
    elif bad=="logical_shift": op["op"]="LogicalShiftRight"
    elif bad=="wrong_signed_width": op["type"]="logic signed[7:0]"
    elif bad=="unsigned_call": call["subroutine"]="$unsigned"
    elif bad=="wrong_call_type": call["type"]="logic[8:0]"
    elif bad=="call_arity": call["arguments"].append(copy.deepcopy(cat))
    elif bad=="cat_arity": cat["operands"].append(copy.deepcopy(data))
    elif bad=="cat_type": cat["type"]="logic[7:0]"
    elif bad=="sign_or": sign["op"]="BinaryOr"
    elif bad=="wrong_msb": sign["right"]["selector"].update(value="6",constant="6")
    elif bad=="wrong_msb_identity": sign["right"]["value"]["symbol"]="y"
    elif bad=="mode_alias": sign["left"]=copy.deepcopy(sign["right"])
    elif bad=="target_alias": n["left"]=copy.deepcopy(data)
    elif bad=="amount_alias":
        op["right"]={"kind":"RangeSelect","type":"logic[2:0]","selectionKind":"Simple","value":copy.deepcopy(data),
                     "left":{"kind":"IntegerLiteral","type":"int","value":"2"},"right":{"kind":"IntegerLiteral","type":"int","value":"0"}}
    elif bad=="amount_width": op["right"]={"kind":"NamedValue","type":"logic","symbol":"mode"}
    elif bad=="signed_amount": op["right"]["type"]="logic signed[2:0]"
    elif bad=="two_state_data": data["type"]="bit[7:0]"
    elif bad=="unresolved": data["symbol"]="missing"
    elif bad=="wrong_range_type":
        cat["operands"][1]={"kind":"RangeSelect","type":"logic[8:1]","selectionKind":"Simple","value":copy.deepcopy(data),
                            "left":{"kind":"IntegerLiteral","type":"int","value":"7"},"right":{"kind":"IntegerLiteral","type":"int","value":"0"}}
    elif bad=="dynamic_selector": sign["right"]["selector"]=copy.deepcopy(sign["left"])
    else:
        data["type"]="logic[0:7]";args[2]["d"]=data["type"];args[3]["d"]=layout(data["type"])
    with pytest.raises(Unsupported):
        expand(*args)


def test_runner_top(monkeypatch,tmp_path):
    from scripts import run_signed_shift_pr113 as runner
    import re
    names=re.findall(r"(?m)^module\s+(\w+)\s*\(",runner.FIXTURE.read_text())
    calls=[]
    monkeypatch.setattr(runner,"extract",lambda directory,top,sources:calls.append((directory,top,sources)))
    runner.extract_fixture(tmp_path)
    assert names==["signed_shift_pr113"] and calls==[(tmp_path,names[0],[runner.FIXTURE])]

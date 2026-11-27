import pytest
from rtlprep.shift_candidates import expand,lane_support,Unsupported
from rtlprep.array_dependencies import layout


def sig(s,t):
    return {"kind":"NamedValue","type":t,"symbol":s}


def lit(v):
    return {"kind":"IntegerLiteral","type":"int","value":str(v),"constant":str(v)}


def site():
    raw={"d":"logic[7:0]","k":"logic[2:0]","y":"logic[7:0]"}
    rhs={"kind":"BinaryOp","op":"LogicalShiftLeft","type":raw["d"],"left":sig("d",raw["d"]),"right":sig("k",raw["k"])}
    return ({"kind":"Assignment","type":raw["y"],"isNonBlocking":False,"left":sig("y",raw["y"]),"right":rhs},
            lambda e:e.get("symbol"),raw,{s:layout(t) for s,t in raw.items()},{})


def test_dynamic_left():
    c=expand(*site())
    assert c["potential_pairs"]==60
    assert c["lane_support"][0]=={"data_ordinals":[0],"amount_ordinals":[0,1,2],"constant_value":None}


def test_fixed_shift_and_overshift():
    args=site();args[0]["right"]["right"]=lit(2)
    c=expand(*args)
    assert c["potential_pairs"]==6 and c["lane_support"][0]["constant_value"]==0
    args[0]["right"]["right"]=lit(8)
    assert all(l["constant_value"]==0 for l in expand(*args)["lane_support"])


@pytest.mark.parametrize("op",["LogicalShiftLeft","LogicalShiftRight"])
@pytest.mark.parametrize("n",[2,4,8])
def test_independent_exhaustive_binary_support(op,n):
    lanes=lane_support(n,n,op,3,None,None)
    observed=[set() for _ in range(n)]
    def oracle(x,k):
        return ((x*(2**k)) if op=="LogicalShiftLeft" else (x//(2**k)))%(2**n)
    for x in range(2**n):
        for k in range(8):
            base=oracle(x,k)
            for b in range(n+3):
                y=oracle(x^(1<<b),k) if b<n else oracle(x,k^(1<<(b-n)))
                diff=base^y
                for i in range(n):
                    if diff&(1<<i): observed[i].add(b)
    assert observed==[set(l["data_ordinals"])|{n+j for j in l["amount_ordinals"]} for l in lanes]


def test_mask_independent_threshold():
    lanes=lane_support(32,32,"LogicalShiftLeft",5,None,0xfffffffe)
    assert sum(len(l["amount_ordinals"]) for l in lanes)==129
    for i,l in enumerate(lanes):
        expected=[b for b in range(5) if any((k<i)!=((k^(1<<b))<i) for k in range(32))]
        assert l["amount_ordinals"]==expected and not l["data_ordinals"]
        assert l["constant_value"]==(0 if i==0 else None)


@pytest.mark.parametrize("bad",["nba","timing","compound","signed","arithmetic","unknown","bad_width","wide_amount",
    "signed_amount","two_state","alias","literal_negative","literal_mismatch","nested","conversion_same_width",
    "conversion_state","target_type","unresolved","wrong_declaration","malformed"])
def test_refusals(bad):
    args=site();n=args[0];rhs=n["right"]
    if bad=="nba": n["isNonBlocking"]=True
    elif bad=="timing": n["timingControl"]={}
    elif bad=="compound": n["op"]="Add"
    elif bad=="signed": rhs["left"]["type"]="logic signed[7:0]"
    elif bad=="arithmetic": rhs["op"]="ArithmeticShiftRight"
    elif bad=="unknown": rhs["op"]="Multiply"
    elif bad=="bad_width": rhs["type"]="logic[3:0]"
    elif bad=="wide_amount": rhs["right"]["type"]="logic[5:0]"
    elif bad=="signed_amount": rhs["right"]["type"]="logic signed[2:0]"
    elif bad=="two_state": rhs["left"]["type"]="bit[7:0]"
    elif bad=="alias": rhs["left"]=sig("y","logic[7:0]")
    elif bad=="literal_negative": rhs["right"]=lit(-1)
    elif bad=="literal_mismatch": rhs["right"]=lit(2);rhs["right"]["constant"]="3"
    elif bad=="nested": rhs["left"]={"kind":"BinaryOp","type":"logic[7:0]","op":"Add"}
    elif bad=="conversion_same_width": n["right"]={"kind":"Conversion","type":n["type"],"operand":rhs}
    elif bad=="conversion_state": n["right"]={"kind":"Conversion","type":"bit[7:0]","operand":rhs}
    elif bad=="target_type": n["type"]="logic[6:0]"
    elif bad=="unresolved": rhs["left"]["symbol"]="missing"
    elif bad=="wrong_declaration": rhs["left"]["type"]="logic[8:1]"
    else: rhs["right"]=None
    with pytest.raises(Unsupported):
        expand(*args)


def test_runner_top(monkeypatch,tmp_path):
    from scripts import run_shift_candidates_pr112 as runner
    import re
    declared=re.findall(r"(?m)^module\s+(\w+)\s*\(",runner.FIXTURE.read_text())
    calls=[]
    monkeypatch.setattr(runner,"extract",lambda directory,top,sources:calls.append((directory,top,sources)))
    runner.extract_fixture(tmp_path)
    assert declared==["shift_candidates_pr112"] and calls==[(tmp_path,declared[0],[runner.FIXTURE])]

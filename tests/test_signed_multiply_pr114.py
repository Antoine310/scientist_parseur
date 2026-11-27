import copy
import pytest
from rtlprep.multiply_candidates import expand,Unsupported
from rtlprep.array_dependencies import layout


def site(n=9,packed=True):
    def typ(w):
        return f"logic[{w-1}:0]"
    def sign(w):
        return f"logic signed[{w-1}:0]"
    raw={k:("logic[3:0]" if packed else "")+typ(w)[5:] if packed else typ(w)
         for k,w in (("a",n),("b",n),("p",2*n))}
    def ep(k,w):
        base={"kind":"NamedValue","symbol":k,"type":raw[k]}
        if not packed:
            return base
        return {"kind":"ElementSelect","type":typ(w),"value":base,
                "selector":{"kind":"IntegerLiteral","type":"int","value":"1","constant":"1"}}
    def operand(k):
        return {"kind":"Conversion","type":sign(2*n),"operand":
                {"kind":"Call","subroutine":"$signed","type":sign(n),"arguments":[ep(k,n)]}}
    node={"kind":"Assignment","type":typ(2*n),"isNonBlocking":False,"left":ep("p",2*n),
          "right":{"kind":"Conversion","type":typ(2*n),"operand":{"kind":"BinaryOp",
                  "op":"Multiply","type":sign(2*n),"left":operand("a"),"right":operand("b")}}}
    return node,lambda e:e.get("symbol"),raw,{k:layout(v) for k,v in raw.items()},{}


@pytest.mark.parametrize("n,pairs",[(4,52),(9,252),(17,884)])
def test_exact_width_and_outer_coordinates(n,pairs):
    args=site(n);before=copy.deepcopy(args[0]);x=expand(*args)
    assert x["potential_pairs"]==pairs and x["prefix_lengths"]==[min(i+1,n) for i in range(2*n)]
    assert all(e["outer_packed_indices"]==[1] for e in [x["target"],*x["operands"]])
    assert args[0]==before


def test_direct_word_and_same_signal_disjoint_lanes():
    assert expand(*site(4,False))["potential_pairs"]==52
    args=site(4);op=args[0]["right"]["operand"]
    a=op["left"]["operand"]["arguments"][0]
    b=op["right"]["operand"]["arguments"][0]
    b["value"]=copy.deepcopy(a["value"])
    b["selector"].update(value="2",constant="2")
    assert [e["outer_packed_indices"] for e in expand(*args)["operands"]]==[[1],[2]]


def test_exhaustive_small_signed_sensitivity():
    n=4;mask=(1<<(2*n))-1
    def oracle(a,b):
        return ((a-16 if a>=8 else a)*(b-16 if b>=8 else b))&mask
    observed=[set() for _ in range(2*n)]
    for a in range(16):
        for b in range(16):
            for j in range(2*n):
                diff=oracle(a,b)^(oracle(a^(1<<j),b) if j<n else oracle(a,b^(1<<(j-n))))
                for i in range(2*n):
                    if diff&(1<<i):
                        observed[i].add(j)
    assert observed==[set(range(k))|set(range(n,n+k)) for k in expand(*site(n))["prefix_lengths"]]


@pytest.mark.parametrize("bad",["nba","timing","compound","bad_target","no_conversion","result_state",
    "wrong_op","wrong_product_width","missing_extension","wrong_extension","unsigned_call","call_width",
    "call_arity","unresolved","decl_type","dynamic","selector_disagreement","out_of_range",
    "ascending","wrong_selected_type","operand_overlap","target_overlap","range","malformed"])
def test_refusals(bad):
    args=site();n=args[0];rhs=n["right"];op=rhs["operand"];ext=op["left"];call=ext["operand"];a=call["arguments"][0]
    if bad=="nba": n["isNonBlocking"]=True
    elif bad=="timing": n["timingControl"]={}
    elif bad=="compound": n["op"]="Add"
    elif bad=="bad_target": n["type"]="logic[16:0]"
    elif bad=="no_conversion": n["right"]=op
    elif bad=="result_state": rhs["type"]="bit[17:0]"
    elif bad=="wrong_op": op["op"]="Add"
    elif bad=="wrong_product_width": op["type"]="logic signed[16:0]"
    elif bad=="missing_extension": op["left"]=call
    elif bad=="wrong_extension": ext["type"]="logic[17:0]"
    elif bad=="unsigned_call": call["subroutine"]="$unsigned"
    elif bad=="call_width": call["type"]="logic signed[9:0]"
    elif bad=="call_arity": call["arguments"].append(copy.deepcopy(a))
    elif bad=="unresolved": a["value"]["symbol"]="missing"
    elif bad=="decl_type": a["value"]["type"]="logic[4:0][8:0]"
    elif bad=="dynamic": a["selector"]={"kind":"NamedValue","type":"int","symbol":"i"}
    elif bad=="selector_disagreement": a["selector"]["constant"]="2"
    elif bad=="out_of_range": a["selector"].update(value="4",constant="4")
    elif bad=="ascending":
        a["value"]["type"]="logic[0:3][8:0]";args[2]["a"]=a["value"]["type"];args[3]["a"]=layout(args[2]["a"])
    elif bad=="wrong_selected_type": a["type"]="logic[9:1]"
    elif bad=="operand_overlap": op["right"]=copy.deepcopy(ext)
    elif bad=="target_overlap":
        # Same declaration with incompatible width cannot masquerade as product target.
        n["left"]["value"]["symbol"]="a"
    elif bad=="range": a["kind"]="RangeSelect"
    else: call["arguments"]=[None]
    with pytest.raises(Unsupported):
        expand(*args)


def test_runner_top(monkeypatch,tmp_path):
    from scripts import run_signed_multiply_pr114 as runner
    import re
    names=re.findall(r"(?m)^module\s+(\w+)\s*\(",runner.FIXTURE.read_text())
    calls=[]
    monkeypatch.setattr(runner,"extract",lambda directory,top,sources:calls.append((directory,top,sources)))
    runner.extract_fixture(tmp_path)
    assert names==["signed_multiply_pr114"] and calls==[(tmp_path,names[0],[runner.FIXTURE])]

import copy
import pytest
from rtlprep import addition_candidates as m
from rtlprep.array_dependencies import layout, Unsupported


def fixture(n=4):
    raw=f"logic[{n-1}:0]"
    def sig(s): return {"kind":"NamedValue","type":raw,"symbol":s}
    node={"kind":"Assignment","type":raw,"isNonBlocking":False,"left":sig("s"),
          "right":{"kind":"BinaryOp","op":"Add","type":raw,"left":sig("a"),"right":sig("b")}}
    decl={s:raw for s in ("a","b","s")}
    return node,lambda e:e.get("symbol"),decl,{s:layout(t) for s,t in decl.items()}


def oracle(n):
    # Exhaustively toggle each operand bit on independent binary inputs.
    result=set()
    mask=(1<<n)-1
    for a in range(1<<n):
        for b in range(1<<n):
            y=(a+b)&mask
            for side in (0,1):
                for j in range(n):
                    x=((a^(1<<j))+b if side==0 else a+(b^(1<<j)))&mask
                    for i in range(n):
                        if (x^y)&(1<<i):
                            result.add((side,j,i))
    return result


def pairs(c):
    return {(side,j,i) for i,prefix in enumerate(c["prefix_lengths"])
            for side in (0,1) for j in range(prefix)}


@pytest.mark.parametrize("n",[1,2,3,4])
def test_exhaustive_independent_oracle(n):
    c=m.expand(*fixture(n))
    assert pairs(c)==oracle(n)
    assert len(pairs(c))==c["potential_pairs"]
    assert c["target"]["bits_lsb_first"]==list(range(n))


def test_compact_32_and_mutant():
    c=m.expand(*fixture(32))
    assert c["potential_pairs"]==1056 and c["prefix_lengths"]==list(range(1,33))
    assert c["operands"][0]["bits_lsb_first"]==list(range(32))
    # Missing-carry mutant differs from independent exhaustive oracle.
    c=m.expand(*fixture(4))
    c["prefix_lengths"]=[1]*4
    assert pairs(c)!=oracle(4)


@pytest.mark.parametrize("mode,reason",[
    ("nba","not_plain_blocking_assignment"),("compound","not_plain_blocking_assignment"),
    ("timing","not_plain_blocking_assignment"),("subtract","not_direct_addition"),
    ("conversion","not_direct_addition"),("signed","unproven_unsigned_result_layout"),
    ("state","addition_width_or_state_mismatch"),("width","addition_width_or_state_mismatch"),
    ("identity","unproven_exact_signal_identity_or_type"),("alias","overlapping_operand_coordinates"),
    ("nested","unsupported_selection_chain"),("assignment_type","assignment_type_mismatch")])
def test_refusals(mode,reason):
    n,resolve,raw,d=fixture()
    rhs=n["right"]
    if mode=="nba": n["isNonBlocking"]=True
    elif mode=="compound": n["op"]="Add"
    elif mode=="timing": n["timingControl"]={}
    elif mode=="subtract": rhs["op"]="Subtract"
    elif mode=="conversion": n["right"]={"kind":"Conversion","type":rhs["type"],"operand":rhs}
    elif mode=="signed": rhs["left"]["type"]="logic signed[3:0]"
    elif mode=="state": rhs["left"]["type"]="bit[3:0]"
    elif mode=="width": rhs["left"]["type"]="logic[2:0]"
    elif mode=="identity": rhs["left"]["symbol"]="unbound"
    elif mode=="alias": rhs["right"]["symbol"]="a"
    elif mode=="nested": rhs["left"]=copy.deepcopy(rhs)
    else: n["type"]="logic"
    with pytest.raises(Unsupported,match="^"+reason+"$"):
        m.expand(n,resolve,raw,d)


def test_width_cap():
    with pytest.raises(Unsupported,match="addition_width_outside_scope"):
        m.expand(*fixture(65))


def test_no_mutation():
    n,resolve,raw,d=fixture()
    before=copy.deepcopy(n)
    m.expand(n,resolve,raw,d)
    assert n==before

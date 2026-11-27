import copy
import pytest
from rtlprep import subtraction_candidates as m
from rtlprep.array_dependencies import layout, Unsupported


def fixture(n=2,mask=False):
    t=f"logic[{n-1}:0]"
    def sig(s,t=t): return {"kind":"NamedValue","type":t,"symbol":s}
    one={"kind":"Conversion","type":t,"operand":{"kind":"IntegerLiteral","type":f"bit[{n-1}:0]","value":f"{n}'d1"}}
    left,right=sig("a"),sig("b")
    raw={s:t for s in ("a","b","s")}
    if mask:
        raw["k"]="logic[4:0]"
        left={"kind":"BinaryOp","op":"LogicalShiftLeft","type":t,"left":copy.deepcopy(one),
              "right":sig("k",raw["k"])}
        right=one
    node={"kind":"Assignment","type":t,"isNonBlocking":False,"left":sig("s"),
          "right":{"kind":"BinaryOp","op":"Subtract","type":t,"left":left,"right":right}}
    return node,lambda e:e.get("symbol"),raw,{s:layout(t) for s,t in raw.items()},{}


def test_direct_subtraction_32():
    c=m.expand(*fixture(32))
    assert c["potential_pairs"]==1056 and c["prefix_lengths"]==list(range(1,33))


@pytest.mark.parametrize("n",[1,2,3,4])
def test_exhaustive_modular_subtraction(n):
    c=m.expand(*fixture(n))
    expected=set()
    for a in range(1<<n):
        for b in range(1<<n):
            y=(a-b)%(1<<n)
            for side in (0,1):
                for j in range(n):
                    z=((a^(1<<j))-b if side==0 else a-(b^(1<<j)))%(1<<n)
                    for i in range(n):
                        if (y^z)&(1<<i): expected.add((side,j,i))
    actual={(side,j,i) for i,p in enumerate(c["prefix_lengths"]) for j in range(p) for side in (0,1)}
    assert actual==expected and len(actual)==c["potential_pairs"]
    if n>1:
        assert {(side,i,i) for side in (0,1) for i in range(n)}!=expected


def test_mask_exhaustive():
    args=fixture(32,True)
    before=copy.deepcopy(args[0])
    c=m.expand(*args)
    expected={(j,i) for k in range(32) for j in range(5) for i in range(32)
              if (((1<<k)-1)^((1<<(k^(1<<j)))-1))&(1<<i)}
    actual={(j,i) for i,row in enumerate(c["source_offsets_by_result"]) for j in row}
    assert actual==expected and len(actual)==129==c["potential_pairs"]
    assert c["constant_result_positions"]==[{"bit":31,"value":0}]
    assert c["source_offsets_by_result"][3]==[2,3,4]
    assert c["source_offsets_by_result"][15]==[4]
    assert c["source_offsets_by_result"][31]==[]
    assert args[0]==before
    # Mutant: naive every bit to every output, including absent low bits.
    assert {(j,i) for i in range(31) for j in range(5)}!=expected


@pytest.mark.parametrize("bad,reason",[
    ("nba","not_plain_blocking_assignment"),("compound","not_plain_blocking_assignment"),
    ("timing","not_plain_blocking_assignment"),("add","not_direct_subtraction"),
    ("conversion","not_direct_subtraction"),("state","subtraction_width_or_state_mismatch"),
    ("width","subtraction_width_or_state_mismatch"),("signed","unproven_unsigned_result_layout"),
    ("alias","overlapping_operand_coordinates"),("unbound","unproven_exact_signal_identity_or_type"),
    ("mask_width","unproven_shift_mask_width_or_state"),("base4","not_one_shift_minus_one"),
    ("minus4","not_one_shift_minus_one"),("fake_tag","unproven_increment_constant"),
    ("runtime_base","increment_constant_not_literal"),("shift_right","unsupported_selection_chain")])
def test_refuse(bad,reason):
    n,resolve,raw,d,constants=fixture(32,bad in ("mask_width","base4","minus4","fake_tag","runtime_base","shift_right"))
    rhs=n["right"]
    if bad=="nba": n["isNonBlocking"]=True
    elif bad=="compound": n["op"]="Subtract"
    elif bad=="timing": n["timingControl"]={}
    elif bad=="add": rhs["op"]="Add"
    elif bad=="conversion": n["right"]={"kind":"Conversion","type":rhs["type"],"operand":rhs}
    elif bad=="state": rhs["left"]["type"]="bit[31:0]"
    elif bad=="width": rhs["left"]["type"]="logic[30:0]"
    elif bad=="signed": rhs["left"]["type"]="logic signed[31:0]"
    elif bad=="alias": rhs["right"]["symbol"]="a"
    elif bad=="unbound": rhs["right"]["symbol"]="nope"
    elif bad=="mask_width": rhs["left"]["right"]["type"]="logic[5:0]"
    elif bad=="base4": rhs["left"]["left"]["operand"]["value"]="32'd4"
    elif bad=="minus4": rhs["right"]["operand"]["value"]="32'd4"
    elif bad=="fake_tag": rhs["right"]["constant"]="2"
    elif bad=="runtime_base": rhs["left"]["left"]["operand"]={"kind":"NamedValue","type":"bit[31:0]","symbol":"x","constant":"1"}
    else: rhs["left"]["op"]="LogicalShiftRight"
    with pytest.raises(Unsupported,match="^"+reason+"$"):
        m.expand(n,resolve,raw,d,constants)

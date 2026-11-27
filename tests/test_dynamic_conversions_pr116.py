import copy
import pytest
from rtlprep.dynamic_conversion_candidates import expand, position_map, shape, Unsupported, at_pointer


def site(src="logic[3:0]", dst="logic[7:0]"):
    a = {"kind":"NamedValue","type":src,"symbol":"1 a"}
    b = {"kind":"NamedValue","type":dst,"symbol":"2 b"}
    n = {"kind":"Assignment","isNonBlocking":False,"type":dst,"left":b,
         "right":{"kind":"Conversion","type":dst,"operand":a}}
    return n, "continuous", lambda e: {"1 a":"top.a","2 b":"top.b"}.get(e.get("symbol")), {"top.a":src,"top.b":dst}


@pytest.mark.parametrize("src,dst,mode,pairs,zeros", [
    ("logic[3:0]","logic[7:0]","zero_extend",[0,1,2,3],[4,5,6,7]),
    ("logic signed[3:0]","logic signed[7:0]","sign_extend",[0,1,2,3,3,3,3,3],[]),
    ("logic[7:0]","logic[3:0]","truncate_msb",[0,1,2,3],[]),
    ("logic[11:8]","logic[7:4]","same_width",[8,9,10,11],[]),
    ("bit[5:2]","bit[12:5]","zero_extend",[2,3,4,5],[9,10,11,12]),
    ("logic signed[7:0]","logic[3:0]","truncate_msb",[0,1,2,3],[]),
])
def test_map(src,dst,mode,pairs,zeros):
    args=site(src,dst)
    before=copy.deepcopy(args[0])
    r=expand(*args)
    assert r["mode"]==mode
    assert [x["source_bit"] for x in r["pairs"]]==pairs
    assert r["zero_fill_bits"]==zeros
    assert [x["target_bit"] for x in r["pairs"]]+zeros==r["target"]["bits_lsb_first"]
    assert r["potential_pairs"]==len(pairs) and r["permanent_constant"]=="not_inferred"
    assert args[0]==before


@pytest.mark.parametrize("src,dst,reason", [
    ("logic signed[3:0]","logic[7:0]","conversion_extension_signedness_ambiguous"),
    ("logic[3:0]","logic signed[7:0]","conversion_extension_signedness_ambiguous"),
    ("bit[3:0]","logic[7:0]","conversion_state_change_unmodeled"),
    ("logic[3:0]","bit[7:0]","conversion_state_change_unmodeled"),
    ("logic[0:3]","logic[7:0]","conversion_layout_or_budget"),
    ("logic[64:0]","logic[7:0]","conversion_layout_or_budget"),
    ("logic[1:0][3:0]","logic[7:0]","unsupported_integral_type"),
    ("logic[3:0]","enum_t","unsupported_integral_type"),
])
def test_type_refusals(src,dst,reason):
    with pytest.raises(Unsupported,match=reason):
        expand(*site(src,dst))


@pytest.mark.parametrize("bad",["nba","timing","compound","context","type","nested","tag","rhs_tag","identity","selection","dst_identity"])
def test_structural_refusals(bad):
    args=list(site())
    n=args[0]; r=n["right"]; a=r["operand"]
    if bad=="nba": n["isNonBlocking"]=True
    elif bad=="timing": n["timingControl"]={}
    elif bad=="compound": n["op"]="Add"
    elif bad=="context": args[1]="AlwaysFF"
    elif bad=="type": r["type"]="logic[8:0]"
    elif bad=="nested": r["operand"]={"kind":"Conversion","type":a["type"],"operand":a}
    elif bad=="tag": a["constant"]="4'd0"
    elif bad=="rhs_tag": r["constant"]="8'd0"
    elif bad=="identity": a["symbol"]="9 a"
    elif bad=="selection": a["kind"]="RangeSelect"
    else: n["left"]["symbol"]="9 b"
    with pytest.raises(Unsupported):
        expand(*args)


def test_always_comb_is_local():
    args=list(site()); args[1]="AlwaysComb"
    r=expand(*args)
    assert r["guard_feasibility"]==r["timing"]=="not_proven"


def test_pointer():
    assert at_pointer({"a/b":[{"~key":3}]},"/a~1b/0/~0key")==3


@pytest.mark.parametrize("signed",[False,True])
def test_exhaustive_small_binary_map(signed):
    for a in range(1,5):
        for b in range(1,7):
            _,p=position_map((a-1,0,signed,True),(b-1,0,signed,True))
            for x in range(1<<a):
                actual=sum(((x>>j)&1)<<i for i,j in enumerate(p) if j is not None)
                expected=(x-(1<<a) if signed and x&(1<<(a-1)) else x)&((1<<b)-1)
                assert actual==expected


def test_runner_top():
    from scripts.run_dynamic_conversions_pr116 import TOP,FIXTURE
    assert ("module "+TOP+"(") in FIXTURE.read_text()

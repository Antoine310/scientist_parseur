import pytest
from rtlprep.generate_nba_targets import expand,Refusal


def named(name,typ="logic"):
    return {"kind":"NamedValue","symbol":name,"type":typ}


def lit(value):
    return {"kind":"IntegerLiteral","type":"int","value":str(value),"constant":str(value)}


def node(vector=False):
    typ="logic[3:0]" if vector else "logic"
    rhs={"kind":"RangeSelect","type":typ,"value":named("top.data","logic[7:0]"),
         "selectionKind":"Simple","left":lit(7),"right":lit(4)} if vector else {
         "kind":"ElementSelect","type":typ,"value":named("top.data","logic[7:0]"),"selector":lit(2)}
    return {"kind":"Assignment","type":typ,"isNonBlocking":True,
            "left":named("top.gen_a.word_q" if vector else "top.gen_a.flag_q",typ),"right":rhs}


def run(n,context="AlwaysFF",expected=None,variables=None,declared=None,nodes=None):
    types={"top.data":"logic[7:0]","top.gen_a.flag_q":"logic","top.gen_a.word_q":"logic[3:0]",
           "top.gen_b.flag_q":"logic","top.flag_q":"logic"}
    return expand(n,context,"top",n["left"]["symbol"] if expected is None else expected,lambda x:x.get("symbol"),
                  types if declared is None else declared,
                  set(types)-{"top.data","top.flag_q"} if variables is None else variables,
                  set(types) if nodes is None else nodes)


def test_scalar():
    assert run(node())==[{"relation":"generate_nba_sampled_position_candidate",
                          "source":{"signal":"top.data","bit":2},"target":{"signal":"top.gen_a.flag_q","bit":0}}]


def test_vector():
    rows=run(node(True))
    assert [(r["source"]["bit"],r["target"]["bit"]) for r in rows]==[(4,0),(5,1),(6,2),(7,3)]


def test_homonyms_not_flattened():
    n=node()
    n["left"]["symbol"]="top.gen_b.flag_q"
    assert run(n)[0]["target"]["signal"]=="top.gen_b.flag_q"
    with pytest.raises(Refusal):
        run(n,expected="top.gen_a.flag_q")


@pytest.mark.parametrize("bad",["blocking","timing","op","context","wrong_target","unresolved","unindexed",
    "not_variable","direct_target","wrong_type","signed","two_state","ascending","dynamic","selector_mismatch",
    "negative","out_of_range","range_reversed","indexed_range","range_width","result_width","nested_source",
    "source_type","scoped_source","conversion","assignment_width"])
def test_refusals(bad):
    n=node(bad in ("range_reversed","indexed_range","range_width"))
    kw={}
    lhs,rhs=n["left"],n["right"]
    if bad=="blocking": n["isNonBlocking"]=False
    elif bad=="timing": n["timingControl"]={}
    elif bad=="op": n["op"]="Add"
    elif bad=="context": kw["context"]="Always"
    elif bad=="wrong_target": kw["expected"]="top.gen_b.flag_q"
    elif bad=="unresolved": lhs["symbol"]=None
    elif bad=="unindexed": kw["nodes"]={"top.data"}
    elif bad=="not_variable": kw["variables"]=set()
    elif bad=="direct_target": lhs["symbol"]="top.flag_q"
    elif bad=="wrong_type": lhs["type"]="reg"
    elif bad=="signed": lhs["type"]="logic signed"
    elif bad=="two_state": lhs["type"]="bit"
    elif bad=="ascending": rhs["value"]["type"]="logic[0:7]"
    elif bad=="dynamic": rhs["selector"]=named("top.flag_q")
    elif bad=="selector_mismatch": rhs["selector"]["constant"]="1"
    elif bad=="negative": rhs["selector"]=lit(-1)
    elif bad=="out_of_range": rhs["selector"]=lit(8)
    elif bad=="range_reversed": rhs["left"],rhs["right"]=rhs["right"],rhs["left"]
    elif bad=="indexed_range": rhs["selectionKind"]="IndexedUp"
    elif bad=="range_width": rhs["right"]=lit(5)
    elif bad=="result_width": rhs["type"]="logic[1:0]"
    elif bad=="nested_source": rhs["value"]={"kind":"ElementSelect","type":"logic[7:0]"}
    elif bad=="source_type": rhs["value"]["type"]="reg[7:0]"
    elif bad=="scoped_source": rhs["value"]=named("top.gen_a.word_q","logic[3:0]")
    elif bad=="conversion": n["right"]={"kind":"Conversion","type":"logic","operand":rhs}
    else: n["type"]="logic[1:0]"
    with pytest.raises(Refusal):
        run(n,**kw)


def test_fixture_runner_top(monkeypatch,tmp_path):
    from scripts import run_generate_nba_pr108 as runner
    import re
    declared=re.findall(r"(?m)^module\s+(\w+)\s*\(",runner.FIXTURE.read_text())
    calls=[]
    monkeypatch.setattr(runner,"extract",lambda directory,top,sources:calls.append((directory,top,sources)))
    runner.extract_fixture(tmp_path)
    assert declared==["generate_nba_pr108"] and calls==[(tmp_path,declared[0],[runner.FIXTURE])]

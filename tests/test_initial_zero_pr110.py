import pytest
from rtlprep.initial_zero_candidates import expand,prove_zero,Refusal


def lit(typ,value):
    return {"kind":"IntegerLiteral","type":typ,"value":value,"constant":value}


def conv(typ,operand,constant):
    return {"kind":"Conversion","type":typ,"operand":operand,"constant":constant}


def site(typ="reg",rhs=None):
    n={"kind":"Assignment","type":typ,"isNonBlocking":False,
       "left":{"kind":"NamedValue","symbol":"top.q","type":typ},
       "right":conv("reg",lit("bit[0:0]","1'b0"),"1'b0") if rhs is None else rhs}
    return n,{"kind":"ProceduralBlock","procedureKind":"Initial","body":{"kind":"ExpressionStatement","expr":n}}


def run(n,b,variables=None,declared=None,nodes=None):
    return expand(n,b,"top",lambda x:x.get("symbol"),
                  {"top.q":n["left"]["type"]} if declared is None else declared,
                  {"top.q"} if variables is None else variables,{"top.q"} if nodes is None else nodes)


def test_scalar_initial_zero():
    n,b=site()
    assert run(n,b)==[{"relation":"initial_zero_assignment_candidate","target":{"signal":"top.q","bit":0},
                       "value":0,"lifetime":"statement_local_startup_only"}]


def test_unsized_zero_conversion_archived_shape():
    n,b=site("reg[27:0]",conv("reg[27:0]",conv("logic signed[31:0]",lit("int","0"),"0"),"28'd0"))
    assert [r["target"]["bit"] for r in run(n,b)]==list(range(28))


def test_nonzero_declared_indices():
    n,b=site("logic[5:2]",conv("logic[5:2]",conv("logic signed[31:0]",lit("int","0"),"0"),"4'd0"))
    assert [r["target"]["bit"] for r in run(n,b)]==[2,3,4,5]


@pytest.mark.parametrize("bad",["nonzero","x","z","bad_width","bad_constant","parameter","range",
    "blocking_unknown","nba","timing","compound","wrong_procedure","nested","wrong_identity",
    "unresolved","nonvariable","missing_node","wrong_declared_type","rhs_layout","assignment_layout",
    "signed_target","two_state_target","ascending","deep_conversion","wide","malformed"])
def test_refusals(bad):
    n,b=site()
    kw={}
    rhs=n["right"]
    if bad=="nonzero": rhs["operand"]["value"]="1'b1"
    elif bad=="x": rhs["operand"]["value"]="1'bx"
    elif bad=="z": rhs["operand"]["value"]="1'bz"
    elif bad=="bad_width": rhs["operand"]["value"]="2'b0"
    elif bad=="bad_constant": rhs["constant"]="1'b1"
    elif bad=="parameter": n["right"]={"kind":"NamedValue","type":"reg","symbol":"top.P"}
    elif bad=="range": n["right"]={"kind":"RangeSelect","type":"reg"}
    elif bad=="blocking_unknown": del n["isNonBlocking"]
    elif bad=="nba": n["isNonBlocking"]=True
    elif bad=="timing": n["timingControl"]={}
    elif bad=="compound": n["op"]="Add"
    elif bad=="wrong_procedure": b["procedureKind"]="Always"
    elif bad=="nested": b["body"]={"kind":"Block","body":b["body"]}
    elif bad=="wrong_identity": b["body"]["expr"]=dict(n)
    elif bad=="unresolved": n["left"]["symbol"]=None
    elif bad=="nonvariable": kw["variables"]=set()
    elif bad=="missing_node": kw["nodes"]=set()
    elif bad=="wrong_declared_type": kw["declared"]={"top.q":"logic"}
    elif bad=="rhs_layout": rhs["type"]="reg[1:0]"
    elif bad=="assignment_layout": n["type"]="reg[1:0]"
    elif bad=="signed_target": n["left"]["type"]="reg signed"
    elif bad=="two_state_target": n["left"]["type"]="bit"
    elif bad=="ascending": n["left"]["type"]="reg[0:7]"
    elif bad=="deep_conversion":
        for _ in range(5): n["right"]=conv("reg",n["right"],"1'b0")
    elif bad=="wide": n["left"]["type"]="reg[32:0]"
    else: n["right"]=None
    with pytest.raises(Refusal):
        run(n,b,**kw)


def test_runner_top(monkeypatch,tmp_path):
    from scripts import run_initial_zero_pr110 as runner
    import re
    declared=re.findall(r"(?m)^module\s+(\w+)\s*\(",runner.FIXTURE.read_text())
    calls=[]
    monkeypatch.setattr(runner,"extract",lambda directory,top,sources:calls.append((directory,top,sources)))
    runner.extract_fixture(tmp_path)
    assert declared==["initial_zero_pr110"] and calls==[(tmp_path,declared[0],[runner.FIXTURE])]

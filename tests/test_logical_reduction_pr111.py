import pytest
from rtlprep.logical_candidates import expand,Unsupported
from rtlprep.array_dependencies import layout


def sig(s,t="logic"):
    return {"kind":"NamedValue","type":t,"symbol":s}


def unary(op,x):
    return {"kind":"UnaryOp","op":op,"type":"logic","operand":x}


def binary(op,x,y):
    return {"kind":"BinaryOp","op":op,"type":"logic","left":x,"right":y}


def site(rhs=None):
    raw={"a":"logic","b":"logic","c":"logic","d":"logic","v":"logic[3:0]","y":"logic"}
    rhs=rhs if rhs is not None else binary("LogicalAnd",sig("a"),unary("LogicalNot",sig("b")))
    return ({"kind":"Assignment","type":"logic","isNonBlocking":False,"left":sig("y"),"right":rhs},
            lambda e:e.get("symbol"),raw,{s:layout(t) for s,t in raw.items()},{})


def test_and_not():
    c=expand(*site())
    assert c["potential_pairs"]==2
    assert c["tree"]=={"op":"LogicalAnd","args":[{"leaf":0,"truth_conversion":"scalar"},
        {"op":"LogicalNot","args":[{"leaf":1,"truth_conversion":"scalar"}]}]}


def test_multibit_truth():
    c=expand(*site(binary("LogicalOr",sig("v","logic[3:0]"),sig("b"))))
    assert c["potential_pairs"]==5 and c["tree"]["args"][0]["truth_conversion"]=="nonzero"


@pytest.mark.parametrize("op",["BitwiseAnd","BitwiseOr","BitwiseXor","BitwiseNand","BitwiseNor","BitwiseXnor"])
def test_reductions(op):
    c=expand(*site(unary(op,sig("v","logic[3:0]"))))
    assert c["potential_pairs"]==4 and c["tree"]["args"]==[{"leaf":0,"truth_conversion":"reduction_bits"}]


def test_nested_scalar_reduction():
    c=expand(*site(binary("LogicalAnd",unary("BitwiseOr",sig("v","logic[3:0]")),sig("d"))))
    assert c["potential_pairs"]==5


@pytest.mark.parametrize("bad",["repeat","target_alias","unresolved","wrong_type","signed","two_state","nba",
    "timing","op","conversion","compare","literal","call","bitwise","composed_reduction","bad_result",
    "bad_target","deep","dynamic","bad_rhs"])
def test_refusals(bad):
    args=site()
    n=args[0]
    rhs=n["right"]
    if bad=="repeat": rhs["right"]=unary("LogicalNot",sig("a"))
    elif bad=="target_alias": rhs["right"]=sig("y")
    elif bad=="unresolved": rhs["left"]=sig("missing")
    elif bad=="wrong_type": rhs["left"]=sig("v","logic")
    elif bad=="signed": rhs["left"]=sig("v","logic signed[3:0]")
    elif bad=="two_state": rhs["left"]=sig("a","bit")
    elif bad=="nba": n["isNonBlocking"]=True
    elif bad=="timing": n["timingControl"]={}
    elif bad=="op": n["op"]="Add"
    elif bad=="conversion": n["right"]={"kind":"Conversion","type":"logic","operand":rhs}
    elif bad=="compare": rhs["right"]=binary("Equality",sig("b"),sig("c"))
    elif bad=="literal": rhs["right"]={"kind":"IntegerLiteral","type":"logic","value":"1'b0"}
    elif bad=="call": rhs["right"]={"kind":"Call","type":"logic"}
    elif bad=="bitwise": rhs["right"]=binary("BinaryAnd",sig("b"),sig("c"))
    elif bad=="composed_reduction": rhs["right"]=unary("BitwiseOr",binary("BinaryAnd",sig("b"),sig("c")))
    elif bad=="bad_result": rhs["type"]="logic[1:0]"
    elif bad=="bad_target": n["type"]="bit"
    elif bad=="deep":
        for _ in range(10): n["right"]=unary("LogicalNot",n["right"])
    elif bad=="dynamic":
        rhs["left"]={"kind":"ElementSelect","type":"logic","value":sig("v","logic[3:0]"),"selector":sig("c")}
    else: rhs["right"]=None
    with pytest.raises(Unsupported):
        expand(*args)


def test_runner_top(monkeypatch,tmp_path):
    from scripts import run_logical_reduction_pr111 as runner
    import re
    declared=re.findall(r"(?m)^module\s+(\w+)\s*\(",runner.FIXTURE.read_text())
    calls=[]
    monkeypatch.setattr(runner,"extract",lambda directory,top,sources:calls.append((directory,top,sources)))
    runner.extract_fixture(tmp_path)
    assert declared==["logical_reduction_pr111"] and calls==[(tmp_path,declared[0],[runner.FIXTURE])]

import pytest
from rtlprep.vector_concat_nba import expand,Refusal


def named(name,typ):
    return {"kind":"NamedValue","symbol":name,"type":typ}


def lit(n):
    return {"kind":"IntegerLiteral","type":"int","value":str(n),"constant":str(n)}


def sel(name,typ,hi,lo=None):
    if lo is None:
        return {"kind":"ElementSelect","type":"logic","value":named(name,typ),"selector":lit(hi)}
    return {"kind":"RangeSelect","type":f"logic[{hi}:{lo}]","value":named(name,typ),
            "selectionKind":"Simple","left":lit(hi),"right":lit(lo)}


def concat(n,*ops):
    return {"kind":"Concatenation","type":f"logic[{n-1}:0]","operands":list(ops)}


def node(split=False):
    if split:
        lhs=concat(4,sel("split","logic[3:0]",3,2),sel("split","logic[3:0]",1,0))
        rhs=concat(4,sel("data","logic[7:0]",4),sel("data","logic[7:0]",7,5))
    else:
        lhs=concat(5,named("word","logic[5:2]"),named("flag","logic"))
        rhs=concat(5,sel("data","logic[7:0]",7,5),sel("data","logic[7:0]",1,0))
    return {"kind":"Assignment","type":lhs["type"],"isNonBlocking":True,"left":lhs,"right":rhs}


def run(n,context="AlwaysFF",variables=None,types=None,nodes=None):
    d={"data":"logic[7:0]","word":"logic[5:2]","flag":"logic","split":"logic[3:0]"}
    return expand(n,context,lambda x:x.get("symbol"),d if types is None else types,
                  {"word","flag","split"} if variables is None else variables,set(d) if nodes is None else nodes)


def compact(rows):
    return [(r["source"]["signal"],r["source"]["bit"],r["target"]["signal"],r["target"]["bit"]) for r in rows]


def test_mixed_width_and_nonzero_destination():
    assert compact(run(node()))==[("data",0,"flag",0),("data",1,"word",2),
                                 ("data",5,"word",3),("data",6,"word",4),("data",7,"word",5)]


def test_disjoint_slices_same_target_allowed():
    assert compact(run(node(True)))==[("data",5,"split",0),("data",6,"split",1),
                                     ("data",7,"split",2),("data",4,"split",3)]


def test_source_repetition_allowed():
    n=node(True)
    n["right"]["operands"][0]=sel("data","logic[7:0]",5)
    assert [r["source"]["bit"] for r in run(n)]==[5,6,7,5]


@pytest.mark.parametrize("bad",["blocking","timing","op","context","overlap","full_overlap","dynamic",
    "reversed","indexed","out_of_bounds","type_bounds","nested","conversion","constant","ascending",
    "signed","two_state","unresolved","wrong_declaration","nonvariable","missing_node","width",
    "concat_type","assignment_type","arity","scalar_select"])
def test_refusals(bad):
    n=node(bad in ("overlap","full_overlap"))
    a,b=n["left"]["operands"],n["right"]["operands"]
    kw={}
    if bad=="blocking": n["isNonBlocking"]=False
    elif bad=="timing": n["timingControl"]={}
    elif bad=="op": n["op"]="Add"
    elif bad=="context": kw["context"]="AlwaysComb"
    elif bad=="overlap": a[1]=sel("split","logic[3:0]",2,1)
    elif bad=="full_overlap": a[1]=a[0]
    elif bad=="dynamic": b[0]["left"]=named("flag","logic")
    elif bad=="reversed": b[0]["left"],b[0]["right"]=b[0]["right"],b[0]["left"]
    elif bad=="indexed": b[0]["selectionKind"]="IndexedUp"
    elif bad=="out_of_bounds": b[0]["left"]=lit(8)
    elif bad=="type_bounds": b[0]["type"]="logic[2:0]"
    elif bad=="nested": b[0]=concat(3,b[0],b[1])
    elif bad=="conversion": b[0]={"kind":"Conversion","type":"logic[7:5]","operand":b[0]}
    elif bad=="constant": b[0]={"kind":"IntegerLiteral","type":"logic[2:0]","value":"3'b0"}
    elif bad=="ascending": a[0]["type"]="logic[2:5]"
    elif bad=="signed": a[0]["type"]="logic signed[5:2]"
    elif bad=="two_state": a[0]["type"]="bit[5:2]"
    elif bad=="unresolved": a[0]["symbol"]=None
    elif bad=="wrong_declaration": a[0]["type"]="reg[5:2]"
    elif bad=="nonvariable": kw["variables"]={"flag"}
    elif bad=="missing_node": kw["nodes"]={"flag","word"}
    elif bad=="width": b[1]=sel("data","logic[7:0]",0)
    elif bad=="concat_type": n["left"]["type"]="logic[5:0]"
    elif bad=="assignment_type": n["type"]="logic[3:0]"
    elif bad=="arity": n["left"]["operands"]=[a[0]]*33
    else: a[1]=sel("flag","logic",0)
    with pytest.raises(Refusal):
        run(n,**kw)


def test_runner_top(monkeypatch,tmp_path):
    from scripts import run_vector_concat_pr109 as runner
    import re
    declared=re.findall(r"(?m)^module\s+(\w+)\s*\(",runner.FIXTURE.read_text())
    calls=[]
    monkeypatch.setattr(runner,"extract",lambda directory,top,sources:calls.append((directory,top,sources)))
    runner.extract_fixture(tmp_path)
    assert declared==["vector_concat_nba_pr109"] and calls==[(tmp_path,declared[0],[runner.FIXTURE])]

import copy
import pytest
from rtlprep.constant_conversion_candidates import expand,Unsupported
from rtlprep.array_dependencies import layout


def literal(v,t="int"):
    return {"kind":"IntegerLiteral","type":t,"value":v,"constant":v}


def site(family="wide"):
    j={"kind":"NamedValue","type":"integer","symbol":"1 j","constant":"3"}
    typ="logic[3:0][63:0]" if family=="wide" else "logic[3:0][4:0]" if family=="index" else "logic[3:0][31:0]"
    word="logic"+typ[10:]
    lhs={"kind":"ElementSelect","type":word,"value":{"kind":"NamedValue","type":typ,"symbol":"q"},
         "selector":copy.deepcopy(j)}
    zero=literal("32'd0","bit[31:0]")
    if family=="index":
        leaf={"kind":"Call","type":"logic[31:0]","subroutine":"$unsigned","arguments":[copy.deepcopy(j)],"constant":"32'd3"}
        rhs={"kind":"Conversion","type":word,"operand":leaf,"constant":"5'b11"}
    else:
        rhs={"kind":"Conversion","type":word,"operand":zero,"constant": "64'h0" if family=="wide" else "32'd0"}
    if family=="slice":
        lhs={"kind":"RangeSelect","type":"logic[31:16]","selectionKind":"Simple","value":lhs,
             "left":literal("31"),"right":{"kind":"NamedValue","type":"integer","symbol":"2 HI","constant":"16"}}
        rhs={"kind":"Conversion","type":lhs["type"],"operand":rhs,"constant":"16'd0"}
    node={"kind":"Assignment","isNonBlocking":False,"type":lhs["type"],"left":lhs,"right":rhs}
    raw={"q":typ}
    return node,lambda e:e.get("symbol"),raw,{"q":layout(typ)},{"1":("j",3),"2":("HI",16)}


@pytest.mark.parametrize("family,n,value", [("wide",64,0),("equal",32,0),("slice",16,0),("index",5,3)])
def test_value_coordinates(family,n,value):
    args=site(family);before=copy.deepcopy(args[0])
    r=expand(*args)
    assert r["value"]==value and r["values_lsb_first"]==[(value>>i)&1 for i in range(n)]
    assert r["target"]["outer_packed_indices"]==[3]
    assert r["target"]["bits_lsb_first"]==list(range(16,32) if family=="slice" else range(n))
    assert r["potential_pairs"]==0 and r["permanent_constant"]=="not_inferred" and args[0]==before


def test_all_unsigned_indices():
    for j in range(32):
        args=site("index")
        node,_,raw,declared,constants=args
        raw["q"]="logic[31:0][4:0]";declared["q"]=layout(raw["q"])
        node["left"]["value"]["type"]=raw["q"]
        node["left"]["selector"]["constant"]=str(j)
        arg=node["right"]["operand"]["arguments"][0]
        arg["constant"]=str(j);constants["1"]=("j",j)
        node["right"]["operand"]["constant"]=f"32'd{j}"
        node["right"]["constant"]=f"5'b{j:b}"
        assert expand(*args)["value"]==j


@pytest.mark.parametrize("bad",["nba","timing","compound","assignment_type","no_conversion","bad_result_type",
    "unknown_literal","nonzero_literal","literal_width","literal_tag","folded_width","folded_value",
    "missing_leaf","too_deep","dynamic_selector","selector_tag","unknown_decl","ascending",
    "wrong_unsigned","wrong_arg","wrong_arg_type","wrong_arg_symbol","unbound_index","unsigned_tag"])
def test_refusals(bad):
    args=site("index" if bad in ("wrong_unsigned","wrong_arg","wrong_arg_type","wrong_arg_symbol","unbound_index","unsigned_tag") else "wide")
    node=args[0];lhs=node["left"];rhs=node["right"];leaf=rhs["operand"]
    if bad=="nba": node["isNonBlocking"]=True
    elif bad=="timing": node["timingControl"]={}
    elif bad=="compound": node["op"]="Add"
    elif bad=="assignment_type": node["type"]="logic[31:0]"
    elif bad=="no_conversion": node["right"]=leaf
    elif bad=="bad_result_type": rhs["type"]="logic signed[63:0]"
    elif bad=="unknown_literal": leaf["value"]="32'bx"
    elif bad=="nonzero_literal": leaf["value"]="32'd1"
    elif bad=="literal_width": leaf["type"]="bit[15:0]"
    elif bad=="literal_tag": leaf["constant"]="32'd1"
    elif bad=="folded_width": rhs["constant"]="32'd0"
    elif bad=="folded_value": rhs["constant"]="64'h1"
    elif bad=="missing_leaf": rhs["operand"]=None
    elif bad=="too_deep":
        for _ in range(5): node["right"]={"kind":"Conversion","type":lhs["type"],"operand":node["right"]}
    elif bad=="dynamic_selector": lhs["selector"]["symbol"]="99 runtime"
    elif bad=="selector_tag": lhs["selector"]["constant"]="2"
    elif bad=="unknown_decl": lhs["value"]["symbol"]="missing"
    elif bad=="ascending":
        lhs["value"]["type"]="logic[0:3][63:0]";args[2]["q"]=lhs["value"]["type"];args[3]["q"]=layout(args[2]["q"])
    elif bad=="wrong_unsigned": leaf["subroutine"]="$signed"
    elif bad=="wrong_arg": leaf["arguments"]=[]
    elif bad=="wrong_arg_type": leaf["arguments"][0]["type"]="int"
    elif bad=="wrong_arg_symbol": leaf["arguments"][0]["symbol"]="2 HI"
    elif bad=="unbound_index": args[4].clear()
    else: leaf["constant"]="32'd2"
    with pytest.raises(Unsupported):
        expand(*args)


def test_runner_top(monkeypatch,tmp_path):
    from scripts import run_constant_conversions_pr115 as runner
    import re
    names=re.findall(r"(?m)^module\s+(\w+)\s*\(",runner.FIXTURE.read_text())
    calls=[]
    monkeypatch.setattr(runner,"extract",lambda directory,top,sources:calls.append((directory,top,sources)))
    runner.extract_fixture(tmp_path)
    assert names==["constant_conversions_pr115"] and calls==[(tmp_path,names[0],[runner.FIXTURE])]

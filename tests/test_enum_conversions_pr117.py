import copy
from types import SimpleNamespace
import pytest
from rtlprep.enum_conversion_candidates import enum_table, expand, initializer, Unsupported
from rtlprep.array_dependencies import layout


def enum(n=2, explicit=False):
    t=f"logic[{n-1}:0]"
    members=[]
    for i in range(4):
        v=f"{n}'b{i:b}"
        e={"kind":"EnumValue","name":f"E{i}","addr":100+i,"value":v}
        if explicit:
            lit={"kind":"IntegerLiteral","type":"bit[31:0]","value":f"32'd{i}"}
            e["initializer"]={"kind":"Conversion","type":t,"operand":{"kind":"Conversion","type":"logic[31:0]","operand":lit},"constant":v}
        members.append(e)
    return {"kind":"EnumType","baseType":t,"members":members}


@pytest.mark.parametrize("explicit",[False,True])
def test_table(explicit):
    e=enum(explicit=explicit); old=copy.deepcopy(e)
    t,n,table=enum_table(e)
    assert (t,n)==("logic[1:0]",2)
    assert [v[1] for v in table.values()]==list(range(4))
    assert e==old


@pytest.mark.parametrize("bad",["wrong_value","dup_name","dup_address","overflow","unknown","bad_literal_width","bad_tag","bad_type","bad_init_kind","depth","empty"])
def test_table_refusals(bad):
    e=enum(explicit=True); m=e["members"]; i=m[1]["initializer"]
    if bad=="wrong_value": m[1]["value"]="2'b0"
    elif bad=="dup_name": m[1]["name"]=m[0]["name"]
    elif bad=="dup_address": m[1]["addr"]=m[0]["addr"]
    elif bad=="overflow": i["operand"]["operand"]["value"]="32'd4"
    elif bad=="unknown": i["operand"]["operand"]["value"]="32'bx"
    elif bad=="bad_literal_width": i["operand"]["operand"]["value"]="31'd1"
    elif bad=="bad_tag": i["constant"]="2'b0"
    elif bad=="bad_type": i["type"]="logic signed[1:0]"
    elif bad=="bad_init_kind": i["operand"]["kind"]="Call"
    elif bad=="depth":
        for _ in range(5): i["operand"]={"kind":"Conversion","type":"logic[31:0]","operand":i["operand"]}
    else: e["members"]=[]
    with pytest.raises(Unsupported): enum_table(e)


def setup(dynamic=False):
    token="10 p::e"; alias="11 p::e"; t="logic[1:0]"
    types=SimpleNamespace(types={token:enum(),alias:{"kind":"TypeAlias","target":token}})
    if dynamic:
        lhs={"kind":"NamedValue","type":alias,"symbol":"1 q"}
        leaf={"kind":"RangeSelect","type":"logic[4:3]","selectionKind":"Simple",
              "value":{"kind":"NamedValue","type":"logic[7:0]","symbol":"2 w"},
              "left":{"kind":"IntegerLiteral","type":"int","value":"4"},
              "right":{"kind":"IntegerLiteral","type":"int","value":"3"}}
    else:
        lhs={"kind":"NamedValue","type":t,"symbol":"1 q"}
        leaf={"kind":"NamedValue","type":token,"symbol":"102 E2"}
    node={"kind":"Assignment","type":lhs["type"],"isNonBlocking":False,"left":lhs,
          "right":{"kind":"Conversion","type":lhs["type"],"operand":leaf}}
    raw={"q":lhs["type"],"w":"logic[7:0]"}
    return [node,"AlwaysComb",types,lambda e:{"1 q":"q","2 w":"w"}.get(e.get("symbol")),
            raw,{"w":layout(raw["w"])},{}]


def test_constant():
    args=setup(); r=expand(*args)
    assert r["value"]==2 and r["values_lsb_first"]==[0,1]
    assert r["potential_pairs"]==0 and r["permanent_constant"]=="not_inferred"


def test_dynamic():
    args=setup(True); r=expand(*args,linked=True)
    assert r["pairs"]==[{"source_bit":3,"target_bit":0},{"source_bit":4,"target_bit":1}]
    assert r["enum_domain_size"]==4 and r["potential_pairs"]==2


@pytest.mark.parametrize("bad",["unknown_enum","wrong_symbol","runtime_symbol","target_identity","nba","context","tag","result_type","nested","dynamic_no_link","dynamic_incomplete","dynamic_index","dynamic_width"])
def test_refusals(bad):
    args=setup(bad.startswith("dynamic")); n=args[0]; leaf=n["right"]["operand"]
    if bad=="unknown_enum": leaf["type"]="99 p::e"
    elif bad=="wrong_symbol": leaf["symbol"]="102 E1"
    elif bad=="runtime_symbol": leaf["symbol"]="2 w"
    elif bad=="target_identity": n["left"]["symbol"]="9 q"
    elif bad=="nba": n["isNonBlocking"]=True
    elif bad=="context": args[1]="AlwaysFF"
    elif bad=="tag": n["right"]["constant"]="2'b0"
    elif bad=="result_type": n["right"]["type"]="logic[2:0]"
    elif bad=="nested": leaf["kind"]="Conversion"
    elif bad=="dynamic_incomplete": args[2].types["10 p::e"]["members"].pop()
    elif bad=="dynamic_index": leaf["left"]={"kind":"NamedValue","type":"int","symbol":"9 x","constant":"4"}
    elif bad=="dynamic_width": leaf["type"]="logic[5:3]"
    with pytest.raises(Unsupported): expand(*args,linked=bad!="dynamic_no_link")


def test_runner_top():
    from scripts.run_enum_conversions_pr117 import TOP,FIXTURE
    assert ("module "+TOP+"(") in FIXTURE.read_text()


@pytest.mark.parametrize("tagged",["leaf","rhs","both"])
def test_enum_tags_corroborate_only(tagged):
    args=setup(); rhs=args[0]["right"]; leaf=rhs["operand"]
    if tagged in ("leaf","both"): leaf["constant"]="2'b10"
    if tagged in ("rhs","both"): rhs["constant"]="2'b10"
    assert expand(*args)["value"]==2
    if tagged in ("leaf","both"): leaf["constant"]="2'b11"
    else: rhs["constant"]="2'b11"
    with pytest.raises(Unsupported,match="enum_folded_disagreement"): expand(*args)


def test_tag_does_not_resolve_enum_symbol():
    args=setup(); leaf=args[0]["right"]["operand"]
    leaf.update(symbol="999 E2",constant="2'b10")
    with pytest.raises(Unsupported,match="unproven_enum_value_identity"): expand(*args)


def test_dynamic_cast_rejects_folded_leaf():
    args=setup(True); args[0]["right"]["operand"]["constant"]="2'b10"
    with pytest.raises(Unsupported,match="unsupported_dynamic_enum_target"): expand(*args,linked=True)

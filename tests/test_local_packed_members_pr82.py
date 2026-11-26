import copy
import pytest
from rtlprep.array_dependencies import Unsupported
from rtlprep.local_packed_members import coordinates, local_types, field_layout, observations, expand

RAW="10 m.Pair_t"
HI="logic[1:0][3:0]"
LO="logic[0:1][1:0]"
OWNER="top"

def ast():
    return {"design":{"members":[{"kind":"Instance","name":OWNER,"body":{
        "kind":"InstanceBody","name":"m","members":[{"kind":"TypeAlias","addr":10,
        "name":"Pair_t","target":f"struct packed{{{HI} upper;{LO} lower;}}m.s$1"}]}}]}}

def named(n, a, t):
    return {"kind":"NamedValue","symbol":f"{a} {n}","type":t}

def member():
    return {"kind":"MemberAccess","type":HI,"member":"21 upper","value":named("bundle",1,RAW)}

def assignment(zero=False):
    return {"kind":"Assignment","type":HI,"isNonBlocking":False,
            "left":member() if zero else named("hi",2,HI),
            "right":{"kind":"UnbasedUnsizedIntegerLiteral","type":HI,"value":"8'h0"} if zero else member()}

def run(a, tree=None, extra=None):
    types=local_types(ast() if tree is None else tree)
    sites=[(OWNER,"continuous",a)]
    if extra is not None:
        sites.append((OWNER,"continuous",extra))
    return expand(a,OWNER,lambda e:{"1 bundle":"top.bundle","2 hi":"top.hi"}.get(e.get("symbol")),
                  {"top.bundle":RAW,"top.hi":HI},types,observations(sites,types))

def test_coordinates_ascending_and_descending():
    assert coordinates(LO)==[(1,0),(1,1),(0,0),(0,1)]
    assert coordinates(HI)==[(0,i) for i in range(4)]+[(1,i) for i in range(4)]

def test_layout_offsets():
    f=field_layout(RAW,OWNER,local_types(ast()))
    assert f["lower"][2]==0 and f["upper"][2]==4

def test_read_positions_and_ast_unchanged():
    a=assignment()
    before=copy.deepcopy(a)
    e,c=run(a)
    assert not c and [(x["source_bit"],x["target_packed_offset"]) for x in e]==[(4+i,i) for i in range(8)]
    assert [x["target_coordinates"] for x in e]==[list(x) for x in coordinates(HI)]
    assert a==before

@pytest.mark.parametrize("field,typ,width,value,offset", [
    ("upper", HI, 8, "8'h0", 4),
    ("upper", HI, 8, "8'd0", 4),
    ("upper", HI, 8, "8'b0", 4),
    ("lower", LO, 4, "4'b0", 0),
])
def test_zero_positions_no_edges(field,typ,width,value,offset):
    a=assignment(True)
    a["type"]=typ
    a["left"].update(type=typ,member=f"21 {field}")
    a["right"].update(type=typ,value=value,constant=value)
    e,c=run(a)
    assert not e and [(x["target_bit"],x["value"]) for x in c]==[(offset+i,0) for i in range(width)]
    assert [x["field_coordinates"] for x in c]==[list(x) for x in coordinates(typ)]


@pytest.mark.parametrize("value", [
    "4'b0", "8'd1", "8'bx", "8'bz", "8'sd0", "8'o0", "8'd00", "8'd0 ", 0,
])
def test_zero_spelling_fail_closed(value):
    a=assignment(True)
    a["right"]["value"]=value
    with pytest.raises(Unsupported,match="unproven_exact_zero"):
        run(a)

@pytest.mark.parametrize("mode",["wrong_owner","wrong_addr","duplicate_alias","duplicate_instance","inactive",
    "signed","union","unpacked","field","conflict","nba","compound","timing","source","target",
    "width","nonzero","unknown","constant_disagreement"])
def test_refusals(mode):
    a=assignment(mode in ("nonzero","unknown","constant_disagreement"))
    t=ast()
    inst=t["design"]["members"][0]
    alias=inst["body"]["members"][0]
    extra=None
    if mode=="wrong_owner": inst["name"]="other"
    elif mode=="wrong_addr": alias["addr"]=11
    elif mode=="duplicate_alias": inst["body"]["members"].append(copy.deepcopy(alias))
    elif mode=="duplicate_instance": t["design"]["members"].append(copy.deepcopy(inst))
    elif mode=="inactive": inst["isUninstantiated"]=True
    elif mode=="signed": alias["target"]=alias["target"].replace("logic[1:0]","logic signed[1:0]")
    elif mode=="union": alias["target"]=alias["target"].replace("struct","union")
    elif mode=="unpacked": alias["target"]=alias["target"].replace(HI,"logic[3:0]$[1:0]")
    elif mode=="field": a["right"]["member"]="21 absent"
    elif mode=="conflict":
        extra=assignment()
        extra["right"]["member"]="22 upper"
    elif mode=="nba": a["isNonBlocking"]=True
    elif mode=="compound": a["op"]="Add"
    elif mode=="timing": a["timingControl"]={}
    elif mode=="source": a["right"]["value"]["symbol"]="9 bundle"
    elif mode=="target": a["left"]["symbol"]="9 hi"
    elif mode=="width": a["type"]=LO
    elif mode=="nonzero": a["right"]["value"]="8'hff"
    elif mode=="unknown": a["right"]["value"]="8'hx"
    else: a["right"]["constant"]="8'hff"
    with pytest.raises(Unsupported):
        run(a,t,extra)

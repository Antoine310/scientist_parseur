import copy
import pytest
from rtlprep.array_dependencies import layout, coordinates, expand_assignment, Unsupported

def named(name,typ):
    return {"kind":"NamedValue","symbol":name,"type":typ}

def lit(value):
    return {"kind":"IntegerLiteral","type":"int","value":str(value)}

def element(value,selector):
    return {"kind":"ElementSelect","value":value,"selector":selector}

def span(value,left,right,kind="Simple"):
    return {"kind":"RangeSelect","value":value,"left":lit(left),"right":lit(right),
            "selectionKind":kind}

def resolve(n):
    return n.get("symbol")

TYPES={"u.a":"logic[7:0]","u.arr":"logic[7:0]$[1:2]",
       "u.grid":"logic[7:0]$[2:1][0:1]","u.p":"logic[1:0][7:0]",
       "u.asc":"logic[0:7]$[0:1]","u.out":"logic[3:0]","u.scalar":"logic"}
DECLARED={k:layout(v) for k,v in TYPES.items()}

def base(name):
    return named("u."+name,TYPES["u."+name])

def coords(expr,constants=None):
    return coordinates(expr,resolve,DECLARED,constants or {})

def test_layout():
    assert layout("logic[7:0]$[1:2]")==("logic",((7,0),),((1,2),))
    assert layout("logic[1:0][7:0]")==("logic",((1,0),(7,0)),())
    assert layout("logic")==("logic",(),())

@pytest.mark.parametrize("raw",["logic[7:0]$[]","logic$[$]","logic$[*]","alias",
                                "logic[-1:0]","logic[65536:0]","logic[7:0]$[0:99999]",
                                "logic[0:1][0:1][0:1][0:1][0:1]","logic[1024:0]"])
def test_unsupported_layout(raw):
    assert layout(raw) is None

def test_unpacked_element():
    assert coords(element(base("arr"),lit(2)))==("u.arr",[2],[],list(range(8)))

def test_nested_slice():
    assert coords(span(element(base("arr"),lit(1)),5,2))==("u.arr",[1],[],[2,3,4,5])

def test_two_unpacked_dimensions():
    assert coords(element(element(base("grid"),lit(2)),lit(0)))==("u.grid",[2,0],[],list(range(8)))

def test_packed_dimensions():
    assert coords(element(element(base("p"),lit(0)),lit(6)))==("u.p",[],[0],[6])

def test_ascending_packed_order():
    assert coords(span(element(base("asc"),lit(1)),2,5))==("u.asc",[1],[],[5,4,3,2])

def test_lexical_constant_index():
    selector=named("12 k","int")
    assert coords(element(base("arr"),selector),{"12":("k",2)})[1]==[2]

def test_exact_copy():
    a={"kind":"Assignment","isNonBlocking":False,"left":base("out"),
       "right":span(element(base("arr"),lit(2)),5,2)}
    original=copy.deepcopy(a)
    edges=expand_assignment(a,resolve,DECLARED,{})
    assert [(e["source_unpacked_indices"],e["source_bit"],e["target_bit"]) for e in edges]==[
        ([2],2,0),([2],3,1),([2],4,2),([2],5,3)]
    assert a==original

@pytest.mark.parametrize("mode",["dynamic","out_of_bounds","aggregate","outer_slice",
                                 "extra_select","indexed_part","wrong_direction","wrong_type"])
def test_reject(mode):
    arr=base("arr")
    expr=element(arr,lit(1))
    if mode=="dynamic":
        expr=element(arr,{**named("99 idx","int"),"constant":"1"})
    elif mode=="out_of_bounds":
        expr=element(arr,lit(0))
    elif mode=="aggregate":
        expr=arr
    elif mode=="outer_slice":
        expr=span(arr,2,1)
    elif mode=="extra_select":
        expr=element(element(expr,lit(0)),lit(0))
    elif mode=="indexed_part":
        expr=span(expr,0,2,"IndexedUp")
    elif mode=="wrong_direction":
        expr=span(expr,2,5)
    else:
        arr["type"]="logic[7:0]$[0:1]"
    with pytest.raises(Unsupported):
        coords(expr)

def test_width_mismatch():
    a={"kind":"Assignment","isNonBlocking":False,"left":base("out"),
       "right":element(base("arr"),lit(1))}
    with pytest.raises(Unsupported,match="width"):
        expand_assignment(a,resolve,DECLARED,{})

def test_width_preserving_conversion():
    inner=span(element(base("arr"),lit(2)),5,2)
    inner["type"]="logic[5:2]"
    expr={"kind":"Conversion","type":"logic[3:0]","operand":inner}
    assert coordinates(expr,resolve,DECLARED,{},allow_conversion=True)[3]==[2,3,4,5]
    expr["type"]="logic[7:0]"
    with pytest.raises(Unsupported,match="width"):
        coordinates(expr,resolve,DECLARED,{},allow_conversion=True)

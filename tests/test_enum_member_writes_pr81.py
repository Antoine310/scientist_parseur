import copy
import pytest

from rtlprep.array_dependencies import Unsupported
from rtlprep.enum_member_writes import expand
from rtlprep.packed_members import observed_members
from rtlprep.typed_layout import Types

ALIAS = "11 p::Mode_t"
ENUM = "12 p::Mode_t"
STRUCT = "13 p::Word_t"


def inventory():
    e = {"kind":"EnumValue","name":"HI","addr":21,"value":"2'b10",
         "initializer":{"kind":"Conversion","type":"logic[1:0]","constant":"2'b10",
                        "operand":{"kind":"IntegerLiteral","type":"bit[1:0]",
                                   "value":"2'b10","constant":"2'b10"}}}
    t = Types({"design":{"members":[{"kind":"Package","name":"p","members":[
        {"kind":"TypeAlias","name":"Mode_t","addr":11,"target":ENUM},
        {"kind":"EnumType","name":"Mode_t","addr":12,"baseType":"logic[1:0]","members":[e]},
        {"kind":"TypeAlias","name":"Word_t","addr":13,
         "target":f"struct packed{{logic marker;{ALIAS} mode;logic tail;}}p::s$1"}]}]}})
    return t, e


def assignment():
    return {"kind":"Assignment","type":ALIAS,"isNonBlocking":False,
            "left":{"kind":"MemberAccess","type":ALIAS,"member":"31 mode",
                    "value":{"kind":"NamedValue","type":STRUCT,"symbol":"1 bundle"}},
            "right":{"kind":"NamedValue","type":ENUM,"symbol":"21 HI"}}


def run(a, t, runtime=False):
    def resolve(e):
        return {"1 bundle":"top.bundle", **({"21 HI":"top.runtime"} if runtime else {})}.get(e.get("symbol"))
    return expand(a, resolve, {"top.bundle":STRUCT}, t, observed_members(a,t))


def test_enum_positions_and_preservation():
    t,_ = inventory()
    a = assignment()
    before = copy.deepcopy(a)
    constants = run(a,t)
    assert [(c["target_bit"],c["field_bit"],c["value"]) for c in constants] == [(1,0,0),(2,1,1)]
    assert all(c["target"]=="top.bundle" and c["enum_value"]=="HI" for c in constants)
    assert a == before


def test_slang_compact_binary_value_zero_extension():
    t,e = inventory()
    e["value"] = e["initializer"]["constant"] = "2'b1"
    e["initializer"]["operand"].update(value="2'b1",constant="2'b1")
    assert [c["value"] for c in run(assignment(),t)] == [1,0]


@pytest.mark.parametrize("mode", ["address","name","type","alias","runtime","duplicate",
                                  "value","initializer","unknown","overflow","signed",
                                  "field","base","nba","compound","timing","tag"])
def test_reject_unproven_enum(mode):
    t,e = inventory()
    a = assignment()
    if mode=="address": a["right"]["symbol"]="22 HI"
    elif mode=="name": a["right"]["symbol"]="21 OTHER"
    elif mode=="type": a["right"]["type"]=ALIAS
    elif mode=="alias": t.types[ALIAS]["target"]="99 p::Mode_t"
    elif mode=="duplicate": t.types[ENUM]["members"].append(copy.deepcopy(e))
    elif mode=="value": e["value"]="2'b11"
    elif mode=="initializer": e["initializer"]["operand"]["kind"]="NamedValue"
    elif mode=="unknown": e["initializer"]["operand"]["value"]="2'bx"
    elif mode=="overflow": e["initializer"]["operand"]["value"]="2'b100"
    elif mode=="signed": t.types[ENUM]["baseType"]="logic signed[1:0]"
    elif mode=="field": a["left"]["member"]="31 absent"
    elif mode=="base": a["left"]["value"]["symbol"]="99 bundle"
    elif mode=="nba": a["isNonBlocking"]=True
    elif mode=="compound": a["op"]="Add"
    elif mode=="timing": a["timingControl"]={}
    elif mode=="tag": a["right"]["constant"]="2'b00"
    with pytest.raises(Unsupported):
        run(a,t,runtime=mode=="runtime")

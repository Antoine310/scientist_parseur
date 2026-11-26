import copy
import pytest

from rtlprep.packed_members import fields, expand, observed_members
from rtlprep.typed_layout import Types
from rtlprep.array_dependencies import Unsupported

TYPE = "10 p::Pair_t"
TARGET = "struct packed{logic[7:5] high;logic[4:0] low;}p::s$1"


def inventory(target=TARGET):
    return Types({"design": {"members": [{"kind": "Package", "name": "p",
        "members": [{"kind": "TypeAlias", "addr": 10, "name": "Pair_t",
                     "target": target}]}]}})


def ref(name, addr, typ):
    return {"kind": "NamedValue", "symbol": f"{addr} {name}", "type": typ}


def assignment():
    return {"kind": "Assignment", "isNonBlocking": False, "type": "logic[7:5]",
            "left": {"kind": "MemberAccess", "type": "logic[7:5]", "member": "21 high",
                     "value": ref("bundle", 1, TYPE)},
            "right": ref("d", 2, "logic[2:0]")}


def expand_case(node, types=None, extra=None):
    types = inventory() if types is None else types
    obs = observed_members([node, extra], types)
    return expand(node, lambda e: {"1 bundle": "top.bundle", "2 d": "top.d"}.get(e["symbol"]),
                  {"top.bundle": TYPE, "top.d": "logic[2:0]"}, types, obs)


def test_field_layout_order_and_nonzero_indices():
    state, f = fields(TYPE, inventory())
    assert state == "logic"
    assert f == {"low": ("logic[4:0]", [0,1,2,3,4], 0),
                 "high": ("logic[7:5]", [5,6,7], 5)}


def test_direct_field_write_exact_positions_and_unchanged_ast():
    a = assignment()
    before = copy.deepcopy(a)
    e = expand_case(a)
    assert [(x["source_bit"], x["target_bit"], x["target_field"]["field_bit"]) for x in e] == [
        (0,5,5), (1,6,6), (2,7,7)]
    assert a == before


@pytest.mark.parametrize("target", [
    "union packed{logic[7:5] high;logic[4:0] low;}p::u$1",
    "struct packed signed{logic[7:5] high;logic[4:0] low;}p::s$1",
    "struct packed{logic high;logic high;}p::s$1",
    "struct packed{logic[7:5] high;bit[4:0] low;}p::s$1",
    "struct packed{logic[7:5] high;logic[4:0] low;}q::s$1",
    "struct packed{logic[7:5] high;logic[4:0] low}p::s$1",
])
def test_reject_unsupported_layouts(target):
    with pytest.raises(Unsupported):
        fields(TYPE, inventory(target))


@pytest.mark.parametrize("mode", ["identity", "field", "type", "nba", "compound", "width", "conflicting_token"])
def test_fail_closed(mode):
    a = assignment()
    extra = None
    if mode == "identity": a["left"]["value"]["symbol"] = "3 bundle"
    elif mode == "field": a["left"]["member"] = "21 bogus"
    elif mode == "type": a["left"]["type"] = "logic[2:0]"
    elif mode == "nba": a["isNonBlocking"] = True
    elif mode == "compound": a["op"] = "Add"
    elif mode == "width": a["type"] = "logic[1:0]"
    else:
        extra = copy.deepcopy(a["left"])
        extra["member"] = "22 high"
    with pytest.raises(Unsupported):
        expand_case(a, extra=extra)

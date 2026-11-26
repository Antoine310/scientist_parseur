import copy
import pytest
from rtlprep.array_dependencies import Unsupported
from rtlprep.member_writes import expand
from rtlprep.packed_members import observed_members
from rtlprep.typed_layout import Types

RAW = "10 p::Four_t"

def inventory():
    return Types({"design": {"members": [{"kind": "Package", "name": "p",
        "members": [{"kind": "TypeAlias", "addr": 10, "name": "Four_t",
                     "target": "struct packed{logic a;logic b;logic c;logic d;}p::s$1"}]}]}})

def assignment(literal=False):
    rhs = {"kind": "ElementSelect", "type": "logic",
           "value": {"kind": "NamedValue", "type": "logic[3:0]", "symbol": "2 data"},
           "selector": {"kind": "IntegerLiteral", "type": "int", "value": "3"}}
    if literal:
        rhs = {"kind": "Conversion", "type": "logic", "operand":
               {"kind": "IntegerLiteral", "type": "bit[0:0]", "value": "1'b1"}}
    return {"kind": "Assignment", "type": "logic", "isNonBlocking": False,
            "left": {"kind": "MemberAccess", "type": "logic", "member": "21 a",
                     "value": {"kind": "NamedValue", "type": RAW, "symbol": "1 bundle"}},
            "right": rhs}

def run(a, extra=None):
    t = inventory()
    return expand(a, lambda e: {"1 bundle": "top.bundle", "2 data": "top.data"}.get(e.get("symbol")),
                  {"top.bundle": RAW, "top.data": "logic[3:0]"}, t, observed_members([a, extra], t))

def test_fixed_select_and_unchanged_ast():
    a = assignment()
    before = copy.deepcopy(a)
    edge, constant = run(a)
    assert constant is None
    assert (edge["source"], edge["source_bit"], edge["target"], edge["target_bit"]) == (
        "top.data", 3, "top.bundle", 3)
    assert a == before

@pytest.mark.parametrize("value", ["1'b0", "1'b1"])
def test_constant_has_no_edge(value):
    a = assignment(True)
    a["right"]["operand"]["value"] = value
    edge, constant = run(a)
    assert edge is None
    assert constant["target_bit"] == 3 and constant["value"] == int(value[-1])

@pytest.mark.parametrize("mode", ["nba", "compound", "timed", "bad_field", "bad_base",
    "bad_source", "out_of_range", "dynamic", "signed_index", "wrong_tag",
    "literal_x", "literal_tag", "fake_constant"])
def test_reject_unproven(mode):
    a = assignment(mode.startswith("literal") or mode == "fake_constant")
    if mode == "nba": a["isNonBlocking"] = True
    elif mode == "compound": a["op"] = "Add"
    elif mode == "timed": a["timingControl"] = {}
    elif mode == "bad_field": a["left"]["member"] = "21 missing"
    elif mode == "bad_base": a["left"]["value"]["symbol"] = "9 bundle"
    elif mode == "bad_source": a["right"]["value"]["symbol"] = "9 data"
    elif mode == "out_of_range": a["right"]["selector"]["value"] = "4"
    elif mode == "dynamic": a["right"]["selector"]["kind"] = "NamedValue"
    elif mode == "signed_index": a["right"]["selector"]["value"] = "-1"
    elif mode == "wrong_tag": a["right"]["selector"]["constant"] = "2"
    elif mode == "literal_x": a["right"]["operand"]["value"] = "1'bx"
    elif mode == "literal_tag": a["right"]["constant"] = "1'b0"
    else: a["right"]["operand"]["kind"] = "NamedValue"
    with pytest.raises(Unsupported):
        run(a)

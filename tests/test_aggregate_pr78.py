import copy
import pytest
from rtlprep.aggregate_layout import audit, expand_concat
from rtlprep.array_dependencies import Unsupported
from rtlprep.symbols import SignalResolver


def ref(n, t, a):
    return {"kind": "NamedValue", "symbol": f"{a} {n}", "type": t}


def cat(*parts, t="logic[7:0]"):
    return {"kind": "Concatenation", "operands": list(parts), "type": t}


def assignment():
    return {"kind": "Assignment", "isNonBlocking": False, "type": "logic[7:0]",
            "left": cat(ref("hi", "logic[2:0]", 1), ref("lo", "logic[4:0]", 2)),
            "right": ref("d", "logic[7:0]", 3)}


DECLARED = {"top.hi": "logic[2:0]", "top.lo": "logic[4:0]", "top.d": "logic[7:0]"}
SYMBOLS = {"1 hi": "top.hi", "2 lo": "top.lo", "3 d": "top.d"}


def expand(a, declared=None):
    return expand_concat(a, lambda e: SYMBOLS.get(e.get("symbol")),
                         DECLARED if declared is None else declared)


def pairs(edges):
    return {(e["source"], e["source_bit"], e["target"], e["target_bit"]) for e in edges}


def test_exact_mixed_width_concat_and_ast_unchanged():
    a = assignment()
    old = copy.deepcopy(a)
    assert pairs(expand(a)) == (
        {("top.d", i, "top.lo", i) for i in range(5)} |
        {("top.d", i+5, "top.hi", i) for i in range(3)})
    assert a == old


def test_ascending_declaration_positions():
    a = assignment()
    a["right"]["type"] = "logic[0:7]"
    e = expand(a, {**DECLARED, "top.d": "logic[0:7]"})
    assert pairs(e) == ({("top.d", 7-i, "top.lo", i) for i in range(5)} |
                        {("top.d", 2-i, "top.hi", i) for i in range(3)})


def test_rhs_concat_with_repeated_source_is_not_target_overlap():
    a = assignment()
    a["right"] = cat(ref("lo", "logic[4:0]", 2), ref("hi", "logic[2:0]", 1))
    assert pairs(expand(a)) == {
        ("top.hi", 0, "top.lo", 0), ("top.hi", 1, "top.lo", 1),
        ("top.hi", 2, "top.lo", 2), ("top.lo", 0, "top.lo", 3),
        ("top.lo", 1, "top.lo", 4), ("top.lo", 2, "top.hi", 0),
        ("top.lo", 3, "top.hi", 1), ("top.lo", 4, "top.hi", 2)}


@pytest.mark.parametrize("mode", ["missing_identity", "wrong_type", "signed", "conversion",
                                  "width", "nested", "overlap", "nba", "compound", "timed"])
def test_unsupported_is_atomic(mode):
    a = assignment()
    if mode == "missing_identity": a["right"]["symbol"] = "4 d"
    elif mode == "wrong_type": a["right"]["type"] = "logic[0:7]"
    elif mode == "signed": a["right"]["type"] = "logic signed[7:0]"
    elif mode == "conversion": a["right"] = {"kind": "Conversion", "type": "logic[7:0]", "operand": a["right"]}
    elif mode == "width": a["left"]["type"] = "logic[6:0]"
    elif mode == "nested": a["left"]["operands"][0] = cat(a["left"]["operands"][0], t="logic[2:0]")
    elif mode == "overlap":
        a["left"] = cat(ref("d", "logic[7:0]", 3), ref("d", "logic[7:0]", 3), t="logic[15:0]")
        a["right"] = cat(ref("d", "logic[7:0]", 3), ref("d", "logic[7:0]", 3), t="logic[15:0]")
        a["type"] = "logic[15:0]"
    elif mode == "nba": a["isNonBlocking"] = True
    elif mode == "compound": a["op"] = "Add"
    elif mode == "timed": a["timingControl"] = {}
    with pytest.raises(Unsupported):
        expand(a)


def synthetic():
    members = [{"kind": "Variable", "name": n, "addr": i, "type": DECLARED["top."+n]}
               for i,n in enumerate(("hi", "lo", "d"), 1)]
    members.append({"kind": "ContinuousAssign", "assignment": assignment()})
    index = {"instances": [{"path": "top", "ports": []}],
             "signals": [{"instance_path": "top", "name": n, "type": t}
                         for p,t in DECLARED.items() for n in [p.split(".")[1]]]}
    ast = {"design": {"members": [{"kind": "Instance", "name": "top", "body": {"members": members}}]}}
    return ast, index, members


def test_audit_exact_identity_inactive_scope_and_member_abstention():
    ast, idx, members = synthetic()
    a = assignment()
    a["left"] = ref("hi", "logic[2:0]", 1)
    a["right"] = {"kind": "MemberAccess", "value": ref("d", "logic[7:0]", 3),
                  "member": "991 high", "type": "logic[2:0]"}
    members.append({"kind": "ContinuousAssign", "assignment": a})
    members.append({"kind": "GenerateBlock", "isUninstantiated": True,
                    "members": [{"kind": "ContinuousAssign", "assignment": assignment()}]})
    result = audit(ast, idx)
    assert result["counts"] == {"sites": 2, "supported": 1, "partial": 1, "edges": 8,
                                "lhs_concat": 1, "lhs_member": 0, "rhs_member": 1}
    assert result["partial_reasons"] == {"member_layout_not_proven": 1}
    assert result["items"][1]["rhs_members"][0]["member"] == "high"


def test_no_legacy_name_fallback_in_new_resolver():
    ast, idx, members = synthetic()
    del members[0]["addr"]
    resolver = SignalResolver(ast, idx)
    assert resolver.resolve("top", ref("hi", "logic[2:0]", 1)) == "top.hi"
    assert resolver.resolve_exact("top", ref("hi", "logic[2:0]", 1)) is None
    assert resolver.resolve_exact("top", ref("lo", "logic[4:0]", 2)) == "top.lo"
    assert resolver.resolve_exact("top", ref("hi", "logic[2:0]", 2)) is None


def test_budget_is_failure_not_complete_report(monkeypatch):
    from rtlprep import aggregate_layout
    ast, idx, _ = synthetic()
    monkeypatch.setattr(aggregate_layout, "MAX_EDGES", 7)
    with pytest.raises(Unsupported, match="aggregate_edge_budget"):
        audit(ast, idx)

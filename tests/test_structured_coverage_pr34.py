"""PR #34 — structural expression trees and conservative nested bit accesses."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from rtlprep.dependencies import build_dependency_graph
from rtlprep.field_validation import git_blob_sha1
from rtlprep.manifest import load_design
from rtlprep.runner import dependency_design


ROOT = Path(__file__).resolve().parents[1]
PINNED = (
    ("axis_register", ROOT / "upstream_unknown/verilog-axis/rtl/axis_register.v",
     "93fe0bee6ff1f50d1e2236f5babc283bada2f1a2"),
    ("priority_encoder", ROOT / "upstream_unknown/verilog-axis/rtl/priority_encoder.v",
     "cf82512ba84c43cfddc7728782493241b563b8f3"),
    ("rxuart", ROOT / "upstream_unknown/wbuart32/rtl/rxuart.v",
     "1506e563944a2da1c1b01be6c1a953ad92fdff7d"),
)


def n(kind, **fields):
    return {"kind": kind, **fields}


def ref(name, *, constant=None):
    result = n("NamedValue", symbol="123 " + name)
    if constant is not None:
        result["constant"] = constant
    return result


def lit(value):
    return n("IntegerLiteral", value=value)


def bit(name, index):
    return n("ElementSelect", value=ref(name), selector=index)


def lane(name, upper, lower):
    return n("RangeSelect", value=ref(name), left=upper, right=lower)


def assign(lhs, rhs):
    return n("ContinuousAssign", assignment=n(
        "Assignment", left=lhs, right=rhs, isNonBlocking=False,
    ))


def graph(*nodes):
    variables = [
        n("Variable", name=name, type="logic[7:0]")
        for name in ("a", "b", "out", "arr", "idx", "cond")
    ]
    ast = {"design": n("Root", members=[n(
        "Instance", name="top",
        body=n("InstanceBody", name="top", members=variables + list(nodes)),
    )])}
    return build_dependency_graph(ast, expected_top="top")


def row(result, target="top.out"):
    return next(item for item in result["expressions"]["items"]
                if item["target"] == target)


def test_expression_preserves_nested_ternary_and_slices_not_just_wires():
    nested = n("ConditionalOp", conditions=[{"expr": ref("cond")}],
               left=n("Concatenation", operands=[
                   bit("a", lit("2")),
                   lane("b", lit("3"), lit("0")),
               ]),
               right=n("Replication", count=lit("5"),
                       concat=n("Concatenation", operands=[bit("b", lit("0"))])))
    result = graph(assign(ref("out"), nested))
    record = row(result)
    assert record["coverage"] == "syntax_supported", record
    expr = record["expression"]
    assert expr["kind"] == "conditional"
    assert expr["conditions"][0]["path"] == "top.cond"
    assert expr["left"]["kind"] == "concatenation"
    assert expr["left"]["operands"][0]["kind"] == "element_select"
    assert expr["left"]["operands"][0]["selector"]["value"] == "2"
    assert expr["left"]["operands"][1]["kind"] == "range_select"
    assert expr["right"]["kind"] == "replication"
    assert expr["right"]["count"]["value"] == "5"
    assert expr["right"]["concat"]["operands"][0]["value"]["path"] == "top.b"


def test_expression_nested_array_selection_is_structural_not_flattened():
    source = n("ElementSelect",
               value=n("ElementSelect", value=ref("arr"), selector=lit("1")),
               selector=lit("3"))
    result = graph(assign(ref("out"), source))
    expr = row(result)["expression"]
    assert row(result)["coverage"] == "syntax_supported"
    assert expr["kind"] == "element_select"
    assert expr["value"]["kind"] == "element_select"
    assert expr["value"]["value"]["path"] == "top.arr"


def test_expression_malformed_or_pattern_conditional_stays_partial():
    for conditions in ([], [{"expr": ref("cond"), "pattern": {"kind": "Pattern"}}],
                       [{"not_expr": ref("cond")}]):
        result = graph(assign(ref("out"), n(
            "ConditionalOp", conditions=conditions,
            left=ref("a"), right=ref("b"),
        )))
        item = row(result)
        assert item["coverage"] == "partial"
        assert item["expression"]["kind"] == "unsupported"


def test_expression_unsupported_call_and_malformed_repetition_stay_partial():
    for rhs in (
        n("Call", args=[lit("1")]),
        n("Replication", count=lit("2")),
        n("Concatenation", operands=[]),
    ):
        result = graph(assign(ref("out"), rhs))
        assert row(result)["coverage"] == "partial"
        assert row(result)["expression"]["kind"] == "unsupported"


def test_expression_depth_budget_still_reports_partial_for_deeper_ast():
    deep = lit("1")
    for _ in range(24):
        deep = n("UnaryOp", op="LogicalNot", operand=deep)
    result = graph(assign(ref("out"), deep))
    item = row(result)
    assert item["coverage"] == "partial"
    current = item["expression"]
    while current.get("kind") == "unary":
        current = current["operand"]
    assert current == {"kind": "unsupported", "ast_kind": "limit_exceeded"}


def test_expression_node_budget_reports_partial_for_wide_ast():
    # Fewer than 16 levels but exponentially many AST nodes.
    wide = lit("1")
    for _ in range(8):
        wide = n("BinaryOp", op="BitwiseXor", left=wide, right=wide)
    result = graph(assign(ref("out"), wide))
    item = row(result)
    assert item["coverage"] == "partial"
    kinds = []
    def walk(part):
        if isinstance(part, dict):
            if part.get("kind") == "unsupported":
                kinds.append(part.get("ast_kind"))
            for child in part.values():
                walk(child)
        elif isinstance(part, list):
            for child in part:
                walk(child)
    walk(item["expression"])
    assert "limit_exceeded" in kinds


def test_bit_access_nested_target_is_not_given_invented_flat_target_lanes():
    target = n("ElementSelect",
               value=n("ElementSelect", value=ref("arr"), selector=lit("1")),
               selector=lit("2"))
    result = graph(assign(target, bit("a", lit("5"))))
    item = next(x for x in result["bit_accesses"]["items"] if x["target"] == "top.arr")
    assert item["coverage"] == "rhs_lanes_only"
    assert item["target_selection"] == {
        "kind": "nested", "selectors": [
            {"kind": "bit", "index": 1},
            {"kind": "bit", "index": 2},
        ],
    }
    assert item["rhs_width"] == 1
    assert item["source_segments"][0]["selection"] == {"kind": "bit", "index": 5}
    assert "target_lsb" not in item["source_segments"][0]
    # The independent expressions index also retains the selected LHS
    # without claiming that arr[1][2] is a flat bit of arr.
    ex = row(result, "top.arr")
    assert ex["coverage"] == "syntax_supported"
    assert ex["target_access"]["kind"] == "element_select"
    assert ex["target_access"]["value"]["kind"] == "element_select"
    assert ex["target_access"]["value"]["value"]["path"] == "top.arr"


def test_bit_access_generate_arithmetic_index_is_bounded():
    index = n("BinaryOp", op="Add", left=n(
        "BinaryOp", op="Multiply", left=ref("gen_n", constant="2"),
        right=lit("2"),
    ), right=lit("1"))
    result = graph(assign(bit("out", lit("3")), bit("a", index)))
    item = result["bit_accesses"]["items"][0]
    assert item["coverage"] == "explicit_target_lanes"
    assert item["rhs_width"] == 1
    assert item["source_segments"][0]["selection"] == {"kind": "bit", "index": 5}
    assert item["source_segments"][0]["target_lsb"] == 3


def test_runtime_signal_constant_tag_cannot_prove_static_position():
    selector = ref("idx", constant="3")
    result = graph(assign(bit("out", lit("0")), bit("a", selector)))
    item = result["bit_accesses"]["items"][0]
    assert item["coverage"] == "partial"
    assert item["reason"] == "dynamic_or_unknown_index"
    assert item["source_segments"] == []


def test_bit_access_never_resolves_shadowed_symbol_by_name_only():
    def named(addr, name):
        return n("NamedValue", symbol=f"{addr} {name}")

    def ast_with_assign(lhs, rhs):
        return {"design": n("Root", members=[n(
            "Instance", name="top", body=n("InstanceBody", name="top",
                members=[
                    n("Variable", name="out", type="logic[7:0]", addr="222"),
                    n("Variable", name="a", type="logic[7:0]", addr="111"),
                    assign(lhs, rhs),
                ]),
        )])}

    bad_lhs = n("ElementSelect",
                value=named("wrong", "out"), selector=lit("0"))
    good_rhs = n("ElementSelect",
                 value=named("111", "a"), selector=lit("1"))
    invalid_target = build_dependency_graph(
        ast_with_assign(bad_lhs, good_rhs), expected_top="top"
    )
    assert invalid_target["bit_accesses"]["counts"]["unsupported_targets"] == 1
    assert invalid_target["bit_accesses"]["items"] == []
    assert invalid_target["expressions"]["counts"]["unsupported_targets"] == 1

    good_lhs = n("ElementSelect",
                 value=named("222", "out"), selector=lit("0"))
    bad_rhs = n("ElementSelect",
                value=named("wrong", "a"), selector=lit("1"))
    invalid_rhs = build_dependency_graph(
        ast_with_assign(good_lhs, bad_rhs), expected_top="top"
    )
    item = invalid_rhs["bit_accesses"]["items"][0]
    assert item["coverage"] == "partial"
    assert item["reason"] == "unresolved_symbol_identity"
    assert item["source_segments"] == []


def test_conversion_arithmetic_and_unknown_width_remain_partial():
    for expr in (
        n("Conversion", operand=bit("a", lit("1"))),
        n("BinaryOp", op="Add", left=bit("a", lit("1")), right=lit("1")),
        n("Concatenation", operands=[bit("a", lit("1")), ref("b")]),
    ):
        result = graph(assign(ref("out"), expr))
        item = result["bit_accesses"]["items"][0]
        assert item["coverage"] == "partial", item
        assert item["source_segments"] == []


@pytest.mark.parametrize("top,source,pin", PINNED)
@pytest.mark.skipif(shutil.which("slang") is None, reason="slang réel absent")
def test_real_pinned_rtl_expression_and_bit_coverage(tmp_path, top, source, pin):
    if not source.is_file():
        pytest.skip("checkout épinglé absent")
    assert git_blob_sha1(source.read_bytes()) == pin
    manifest = tmp_path / "design.json"
    manifest.write_text(json.dumps({
        "top": top, "sources": [str(source)], "include_dirs": [], "defines": [],
    }), encoding="utf-8")
    out = tmp_path / "out"
    status = dependency_design(load_design(manifest), out, 90)
    assert status["status"] == "passed", status
    result = json.loads((out / "rtl_dependencies.json").read_text(encoding="utf-8"))
    expr = result["expressions"]["counts"]
    bits = result["bit_accesses"]["counts"]
    print("PR34_REAL_COVERAGE", top, json.dumps({
        "expressions": expr, "bit_accesses": bits,
    }, sort_keys=True))
    assert result["counts"]["warnings"] == 0, result["warnings"]
    assert result["coverage"]["design_coverage"] == "not_measured"
    assert expr["captured"] > 0
    if top == "axis_register":
        assert expr["partial_expressions"] < 17
    if top == "priority_encoder":
        assert expr["unsupported_targets"] == 0, expr
        assert expr["partial_expressions"] < 2, expr
        assert bits["partial"] < 7
    if top == "rxuart":
        assert expr["partial_expressions"] < 18
        assert bits["partial"] >= 1  # arithmetic transformation not positional

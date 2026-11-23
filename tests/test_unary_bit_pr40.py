"""PR40: bitwise-not can preserve source positions without preserving values.

This is syntactic origin metadata, never bit-value equality or a simulation
oracle. All unmodelled unary semantics must continue to produce 'partial'.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from rtlprep.bitaccess import build_bit_access_index
from rtlprep.dependencies import build_dependency_graph
from rtlprep.manifest import load_design
from rtlprep.runner import dependency_design

ROOT = Path(__file__).resolve().parents[1]
REAL_RTL = ROOT / "tests/fixtures/unary_bit_pr40.sv"


def n(kind, **kw):
    return {"kind": kind, **kw}


def r(name, address=None, typ="logic[7:0]", **kw):
    ids = {"bus": "101", "out": "102", "idx": "103", "en": "104"}
    return n("NamedValue", symbol=f"{address or ids[name]} {name}",
             type=typ, **kw)


def literal(value, typ=None):
    obj = n("IntegerLiteral", value=value)
    if typ is not None:
        obj["type"] = typ
    return obj


def bit(value, index):
    return n("ElementSelect", value=value, selector=literal(str(index)),
             type="logic")


def rng(value, hi, lo):
    return n("RangeSelect", value=value, left=literal(str(hi)),
             right=literal(str(lo)), type=f"logic[{hi}:{lo}]")


def cat(*xs):
    return n("Concatenation", operands=list(xs), type="logic[7:0]")


def unary(op, operand, typ=None):
    return n("UnaryOp", op=op, operand=operand,
             type=typ if typ is not None else operand.get("type"))


def assignment(rhs, lhs=None):
    return n("ContinuousAssign", assignment=n(
        "Assignment", left=lhs or r("out", typ="logic[7:0]"),
        right=rhs, isNonBlocking=False))


def design(*assignments):
    return {"design": n("Root", members=[
        n("Instance", name="top", body=n("InstanceBody", name="top",
            members=[
                n("Variable", name="bus", addr="101", type="logic[7:0]"),
                n("Variable", name="out", addr="102", type="logic[7:0]"),
                n("Variable", name="idx", addr="103", type="logic[2:0]"),
                n("Variable", name="en", addr="104", type="logic"),
                *assignments,
            ])),
    ])}


def first(rhs, lhs=None):
    g = build_bit_access_index(design(assignment(rhs, lhs)), expected_top="top")
    assert len(g["items"]) == 1, g
    return g["items"][0]


def test_bitwise_not_of_single_bit_keeps_origin_and_marks_inversion():
    row = first(unary("BitwiseNot", bit(r("bus"), 5)),
                bit(r("out", typ="logic[7:0]"), 2))
    assert row["coverage"] == "explicit_target_lanes"
    assert row["rhs_width"] == 1
    assert row["source_segments"] == [{
        "source": "top.bus", "selection": {"kind": "bit", "index": 5},
        "rhs_lsb": 0, "rhs_msb": 0,
        "target_lsb": 2, "target_msb": 2,
        "value_transform": "bitwise_not",
    }]
    assert "equality" not in json.dumps(row)
    assert "_value_transform" not in json.dumps(row)


def test_bitwise_not_of_range_is_same_positions_not_same_values():
    row = first(unary("BitwiseNot", rng(r("bus"), 7, 4)))
    assert row["coverage"] == "rhs_lanes_only"
    assert row["rhs_width"] == 4
    assert row["source_segments"] == [{
        "source": "top.bus",
        "selection": {"kind": "range", "msb": 7, "lsb": 4},
        "rhs_lsb": 0, "rhs_msb": 3,
        "value_transform": "bitwise_not",
    }]


def test_only_inverted_segment_is_marked_inside_concat():
    value = cat(rng(r("bus"), 7, 5),
                unary("BitwiseNot", bit(r("bus"), 4)),
                rng(r("bus"), 3, 0))
    row = first(value)
    assert row["rhs_width"] == 8
    assert row["coverage"] == "rhs_lanes_only"
    assert len(row["source_segments"]) == 3
    assert [x.get("value_transform") for x in row["source_segments"]] == [
        None, "bitwise_not", None,
    ]
    assert row["source_segments"][1]["rhs_lsb"] == 4
    assert row["source_segments"][1]["rhs_msb"] == 4
    assert row["source_segments"][1]["selection"] == {"kind": "bit", "index": 4}


def test_bitwise_not_over_concat_marks_each_segment_without_mixing_positions():
    operand = n("Concatenation", operands=[
        rng(r("bus"), 7, 6), rng(r("bus"), 1, 0),
    ], type="logic[3:0]")
    row = first(unary("BitwiseNot", operand))
    assert row["rhs_width"] == 4
    assert row["coverage"] == "rhs_lanes_only"
    assert [x["rhs_lsb"] for x in row["source_segments"]] == [2, 0]
    assert all(x["value_transform"] == "bitwise_not" for x in row["source_segments"])


def test_bitwise_not_over_single_typed_whole_signal_is_opaque_not_flat_bit_map():
    row = first(cat(literal("1'b0"),
                    unary("BitwiseNot", r("bus"))))
    assert row["rhs_width"] == 9
    assert row["source_segments"][1] == {
        "source": "top.bus", "selection": {"kind": "whole"},
        "rhs_lsb": 0, "rhs_msb": 7,
        "value_transform": "bitwise_not",
    }


@pytest.mark.parametrize("op", [
    "LogicalNot", "Minus", "UnaryMinus", "Plus",
    "BitwiseOr", "BitwiseAnd", "BitwiseXor",
    "Postincrement", "Predecrement", "RandomNew", "", None,
])
def test_other_unary_ops_remain_partial_even_with_identical_widths(op):
    row = first(unary(op, bit(r("bus"), 4)))
    assert row["coverage"] == "partial"
    assert row["reason"] == "unsupported_rhs_UnaryOp"
    assert row["source_segments"] == []


@pytest.mark.parametrize("width,operand_type", [
    ("logic[7:0]", "logic"),
    ("opcode_t", "logic"),
    ("logic", "opcode_t"),
    (None, "logic"),
    ("logic", None),
])
def test_bitwise_not_missing_or_changed_width_is_partial(width, operand_type):
    inp = bit(r("bus"), 4)
    inp["type"] = operand_type
    rhs = unary("BitwiseNot", inp)
    rhs["type"] = width
    row = first(rhs)
    assert row["coverage"] == "partial"
    assert row["reason"] == "bitwise_not_width_unproven_or_changed"


def test_bad_unary_operand_fails_closed():
    row = first(n("UnaryOp", op="BitwiseNot", operand=None, type="logic"),
                bit(r("out"), 1))
    assert row["coverage"] == "partial"
    assert row["reason"] == "bitwise_not_operand_missing"


def test_nested_inversion_is_not_silently_simplified_or_mislabelled():
    twice = unary("BitwiseNot", unary("BitwiseNot", bit(r("bus"), 4)))
    row = first(twice)
    assert row["coverage"] == "partial"
    assert row["reason"] == "nested_value_transforms_unmodeled"
    assert row["source_segments"] == []


def test_invalid_semantic_identity_is_not_hidden_by_bitwise_not():
    row = first(unary("BitwiseNot", bit(r("bus", address="999"), 4)))
    assert row["coverage"] == "partial"
    assert row["reason"] == "unresolved_symbol_identity"
    assert row["source_segments"] == []


def test_dynamic_selector_cannot_be_safely_inverted_positionally():
    row = first(unary("BitwiseNot", bit(r("bus"), r("idx", typ="logic[2:0]",
                                               constant="4"))))
    assert row["coverage"] == "partial"
    assert row["reason"] == "dynamic_or_unknown_index"


def test_not_of_literal_only_records_transform_not_a_calculated_bit_value():
    operand = literal("1'b0", typ="bit")
    row = first(cat(unary("BitwiseNot", operand),
                    rng(r("bus"), 6, 0)))
    assert row["coverage"] == "rhs_lanes_only"
    seg = row["source_segments"][0]
    assert seg["selection"] == {"kind": "literal", "width": 1}
    assert seg["value_transform"] == "bitwise_not"
    assert seg["source"] is None


def test_graph_and_coverage_do_not_claim_output_equality_or_full_coverage():
    rhs = unary("BitwiseNot", bit(r("bus"), 7))
    graph = build_dependency_graph(design(assignment(rhs)), expected_top="top")
    edges = {(e["source"], e["target"]) for e in graph["edges"]
             if e["kind"] == "data"}
    assert edges == {("top.bus", "top.out")}
    row = graph["bit_accesses"]["items"][0]
    assert row["source_segments"][0]["value_transform"] == "bitwise_not"
    assert graph["coverage"]["design_coverage"] == "not_measured"
    assert graph["coverage"]["analyzers"]["bit_accesses"]["observed_status_counts"][
        "rhs_lanes_only"] == 1


@pytest.mark.skipif(shutil.which("slang") is None, reason="real slang v12.1 unavailable")
def test_real_slang_unary_fixture_preserves_inversions_and_rejects_reductions(tmp_path):
    manifest = tmp_path / "design.json"
    manifest.write_text(json.dumps({
        "top": "unary_bit_pr40", "sources": [str(REAL_RTL)],
        "include_dirs": [], "defines": [],
    }), encoding="utf-8")
    out = tmp_path / "run"
    result = dependency_design(load_design(manifest), out, timeout=120)
    assert result["status"] == "passed", result
    graph = json.loads((out / "rtl_dependencies.json").read_text())
    bits = graph["bit_accesses"]
    rows = {x["target"]: x for x in bits["items"]}
    assert set(rows) == {
        "unary_bit_pr40.bit_o", "unary_bit_pr40.mix_o",
        "unary_bit_pr40.wide_o", "unary_bit_pr40.logical_o",
        "unary_bit_pr40.reduction_o",
    }, bits
    for name in ("bit_o", "mix_o", "wide_o"):
        row = rows[f"unary_bit_pr40.{name}"]
        assert row["coverage"] in ("rhs_lanes_only", "explicit_target_lanes"), row
        assert any(x.get("value_transform") == "bitwise_not"
                   for x in row["source_segments"]), row
    mix = rows["unary_bit_pr40.mix_o"]
    assert [x.get("value_transform") for x in mix["source_segments"]] == [
        None, "bitwise_not", None,
    ], mix
    for name in ("logical_o", "reduction_o"):
        row = rows[f"unary_bit_pr40.{name}"]
        assert row["coverage"] == "partial", row
        assert row["reason"] == "unsupported_rhs_UnaryOp", row
        assert row["source_segments"] == [], row
    assert bits["counts"]["precise"] == 3, bits
    assert bits["counts"]["partial"] == 2, bits
    assert graph["coverage"]["design_coverage"] == "not_measured"

"""PR39: exact symbol identity, typed source widths and bounded replication.

Widths are syntactic metadata; the tests do not establish dataflow
equivalence or the behavior of the generated RTL.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from rtlprep.bitaccess import build_bit_access_index, _packed_width
from rtlprep.dependencies import build_dependency_graph
from rtlprep.manifest import load_design
from rtlprep.runner import dependency_design

ROOT = Path(__file__).resolve().parents[1]
RTL = ROOT / "tests/fixtures/typed_segments_pr39.sv"


def n(kind, **props):
    return {"kind": kind, **props}


def ref(name, address, type="logic[7:0]", **kw):
    return n("NamedValue", symbol=f"{address} {name}", type=type, **kw)


def literal(value):
    return n("IntegerLiteral", value=value)


def part(value, upper, lower):
    return n("RangeSelect", value=value, left=literal(str(upper)),
             right=literal(str(lower)), type=f"logic[{upper}:{lower}]")


def cat(*operands):
    return n("Concatenation", operands=list(operands))


def repeat(count, *operands):
    return n("Replication", count=count, concat=cat(*operands))


def assignment(rhs, lhs=None):
    return n("ContinuousAssign", assignment=n("Assignment",
            left=lhs or ref("out", "102", "logic[15:0]"),
            right=rhs, isNonBlocking=False))


def tree(*nodes, with_constant=False):
    declarations = [
        n("Variable", name="bus", addr="101", type="logic[7:0]"),
        n("Variable", name="out", addr="102", type="logic[15:0]"),
        n("Variable", name="idx", addr="103", type="logic[2:0]"),
    ]
    roots = []
    if with_constant:
        roots.append(n("CompilationUnit", members=[
            n("Package", name="pkg", members=[
                n("EnumValue", name="Opcode", addr="400",
                  type="logic[2:0]"),
            ]),
        ]))
    roots.append(n("Instance", name="top", body=n("InstanceBody",
                   name="top", members=declarations + list(nodes))))
    return {"design": n("Root", members=roots)}


def bits(*nodes, with_constant=False):
    return build_bit_access_index(
        tree(*nodes, with_constant=with_constant), expected_top="top",
    )


def first(report):
    assert len(report["items"]) == 1, report
    return report["items"][0]


def test_strict_packed_width_parser_rejects_types_and_budget_overflow():
    for value, expected in (
        ("logic", 1), ("bit", 1),
        ("logic[7:0]", 8), ("logic[2:5]", 4),
        ("bit[31:0]", 32), ("logic[1023:0]", 1024),
        ("logic[1024:0]", None),
        ("logic[3:0][7:0]", None), ("config_pkg::word_t", None),
        ("enum logic[6:0]", None), ("int", None),
        ("logic [7:0]", None), (None, None), (9, None),
    ):
        assert _packed_width(value) == expected, value


def test_runtime_whole_source_uses_typed_width_but_no_subbit_offsets():
    rhs = cat(literal("4'b0"), ref("bus", "101"))
    report = bits(assignment(rhs))
    row = first(report)
    assert row["coverage"] == "rhs_lanes_only"
    assert row["rhs_width"] == 12
    assert row["source_segments"] == [
        {"source": None, "selection": {"kind": "literal", "width": 4},
         "rhs_lsb": 8, "rhs_msb": 11},
        {"source": "top.bus", "selection": {"kind": "whole"},
         "rhs_lsb": 0, "rhs_msb": 7},
    ]
    assert "target_lsb" not in json.dumps(row)


def test_runtime_constant_property_does_not_turn_a_signal_into_a_literal():
    rhs = cat(ref("bus", "101", constant="8'h00"), literal("1'b0"))
    row = first(bits(assignment(rhs)))
    assert row["coverage"] == "rhs_lanes_only"
    assert row["source_segments"][0]["source"] == "top.bus"


def test_enum_declaration_id_and_name_prove_constant_width():
    rhs = cat(literal("5'b0"), ref("Opcode", "400", "logic[2:0]"))
    report = bits(assignment(rhs), with_constant=True)
    row = first(report)
    assert row["coverage"] == "rhs_lanes_only"
    assert row["rhs_width"] == 8
    assert row["source_segments"][-1] == {
        "source": None, "selection": {
            "kind": "constant_reference", "width": 3,
        }, "rhs_lsb": 0, "rhs_msb": 2,
    }


@pytest.mark.parametrize("address,name", [
    ("401", "Opcode"), ("400", "WrongName"), ("101", "Opcode"),
])
def test_constant_name_or_identity_spoof_remains_partial(address, name):
    row = first(bits(assignment(cat(literal("5'b0"),
                     ref(name, address, "logic[2:0]"))), with_constant=True))
    assert row["coverage"] == "partial"
    assert row["source_segments"] == []
    assert row["reason"] == "unknown_or_non_signal_base"


@pytest.mark.parametrize("type_name", [
    "my_typedef_t", "logic[7:0][3:0]", "logic[1024:0]",
])
def test_unproven_source_type_width_remains_partial(type_name):
    rhs = cat(literal("1'b0"), ref("bus", "101", type_name))
    row = first(bits(assignment(rhs)))
    assert row["coverage"] == "partial"
    assert row["reason"] == "source_width_unknown"
    assert row["source_segments"] == []


def test_nested_replication_preserves_order_and_positional_lane_ranges():
    src = part(ref("bus", "101"), 7, 7)
    rhs = cat(repeat(literal("6"), src),
              part(ref("bus", "101"), 4, 0))
    target = part(ref("out", "102", "logic[15:0]"), 10, 0)
    row = first(bits(assignment(rhs, lhs=target)))
    assert row["coverage"] == "explicit_target_lanes", row
    assert row["rhs_width"] == 11
    assert len(row["source_segments"]) == 7
    assert all(segment["selection"] == {
        "kind": "range", "msb": 7, "lsb": 7,
    } for segment in row["source_segments"][:6])
    assert [(x["rhs_lsb"], x["target_lsb"]) for x in row["source_segments"][:6]] == [
        (10, 10), (9, 9), (8, 8), (7, 7), (6, 6), (5, 5),
    ]
    assert row["source_segments"][-1]["selection"] == {
        "kind": "range", "msb": 4, "lsb": 0,
    }
    assert row["source_segments"][-1]["target_lsb"] == 0


@pytest.mark.parametrize("count,reason", [
    (ref("idx", "103", "logic[2:0]", constant="3"),
     "replication_count_or_concat_unproven"),
    (literal("0"), "replication_count_out_of_bounds"),
    (literal("33"), "replication_count_out_of_bounds"),
])
def test_replication_count_does_not_trust_runtime_folded_constant(count, reason):
    row = first(bits(assignment(
        repeat(count, part(ref("bus", "101"), 7, 7)))))
    assert row["coverage"] == "partial"
    assert row["reason"] == reason
    assert row["source_segments"] == []


def test_replication_expansion_is_bounded():
    unit = (part(ref("bus", "101"), 7, 7),
            part(ref("bus", "101"), 6, 6))
    row = first(bits(assignment(repeat(literal("20"), *unit))))
    assert row["coverage"] == "partial"
    assert row["reason"] == "replication_segments_exceed_limit"


def test_replication_missing_concat_never_claims_precision():
    rhs = n("Replication", count=literal("6"),
            concat=ref("bus", "101"))
    row = first(bits(assignment(cat(rhs))))
    assert row["coverage"] == "partial"
    assert row["reason"] == "replication_count_or_concat_unproven"


def test_equal_width_conversion_is_positional_only():
    src = part(ref("bus", "101"), 7, 4)
    rhs = n("Conversion", operand=src, type="logic[3:0]")
    target = part(ref("out", "102", "logic[15:0]"), 3, 0)
    row = first(bits(assignment(rhs, lhs=target)))
    assert row["coverage"] == "explicit_target_lanes"
    assert row["rhs_width"] == 4
    assert row["source_segments"][0]["selection"] == {
        "kind": "range", "msb": 7, "lsb": 4,
    }


@pytest.mark.parametrize("conversion_type", [
    "logic[7:0]", "word_t", None,
])
def test_conversion_with_changed_or_unknown_width_stays_partial(conversion_type):
    src = part(ref("bus", "101"), 7, 4)
    rhs = n("SignedConversion", operand=src, type=conversion_type)
    row = first(bits(assignment(cat(rhs))))
    assert row["coverage"] == "partial"
    assert row["reason"] == "conversion_width_unproven_or_changed"
    assert row["source_segments"] == []


def test_unsupported_arithmetic_stays_partial_despite_a_known_type():
    src = part(ref("bus", "101"), 7, 4)
    rhs = n("BinaryOp", op="Add", left=src, right=literal("1"),
            type="logic[3:0]")
    row = first(bits(assignment(cat(rhs))))
    assert row["coverage"] == "partial"
    assert row["reason"] == "unsupported_rhs_BinaryOp"


@pytest.mark.skipif(shutil.which("slang") is None, reason="real slang unavailable")
def test_real_slang_fixture_uses_true_enum_and_repeated_bit_segments(tmp_path):
    manifest = tmp_path / "design.json"
    manifest.write_text(json.dumps({
        "top": "typed_segments_pr39",
        "sources": [str(RTL)], "include_dirs": [], "defines": [],
    }), encoding="utf-8")
    out = tmp_path / "reports"
    result = dependency_design(load_design(manifest), out, timeout=120)
    assert result["status"] == "passed", result
    graph = json.loads((out / "rtl_dependencies.json").read_text())
    rows = {item["target"]: item for item in graph["bit_accesses"]["items"]}
    assert len(rows) == 3, graph["bit_accesses"]
    fixture_status = {
        item["target"]: {
            "coverage": item["coverage"],
            "reason": item.get("reason"),
            "rhs_width": item.get("rhs_width"),
        } for item in graph["bit_accesses"]["items"]
    }
    if graph["bit_accesses"]["counts"]["precise"] != 3:
        ast = json.loads((out / "elaborated_ast.json").read_text())
        sample = []
        def walk(node):
            if isinstance(node, list):
                for item in node:
                    walk(item)
            elif isinstance(node, dict):
                if ((node.get("kind") == "NamedValue"
                     and str(node.get("symbol", "")).endswith(" OP_A"))
                    or (node.get("kind") in ("Parameter", "EnumValue")
                        and node.get("name") == "OP_A")):
                    sample.append({key: str(node.get(key, ""))[:160]
                                   for key in ("kind", "name", "symbol",
                                               "type", "constant", "value",
                                               "addr")})
                for key, value in node.items():
                    if key not in ("definition", "internalSymbol", "type"):
                        walk(value)
        walk(ast.get("design", {}))
        print("PR39_LOCAL_ENUM_AST", sample[:12])
    assert graph["bit_accesses"]["counts"]["precise"] == 3, fixture_status
    packed = rows["typed_segments_pr39.packed_o"]
    assert packed["rhs_width"] == 16 and packed["coverage"] == "rhs_lanes_only"
    assert {"source": None, "selection": {
        "kind": "constant_reference", "width": 3,
    }, "rhs_lsb": 0, "rhs_msb": 2} in packed["source_segments"]
    assert any(x["source"] == "typed_segments_pr39.bus_i"
               and x["selection"] == {"kind": "whole"}
               and x["rhs_lsb"] == 3 and x["rhs_msb"] == 10
               for x in packed["source_segments"])
    repeated = rows["typed_segments_pr39.repeated_o"]
    assert repeated["rhs_width"] == 8 and repeated["coverage"] == "rhs_lanes_only"
    assert len(repeated["source_segments"]) == 5
    assert graph["coverage"]["design_coverage"] == "not_measured"
    assert graph["bit_accesses"]["counts"]["partial"] == 0


def test_coverage_cannot_be_inferred_from_validated_syntax():
    g = build_dependency_graph(tree(assignment(cat(
        literal("5'b0"), ref("Opcode", "400", "logic[2:0]")
    )), with_constant=True), expected_top="top")
    assert g["bit_accesses"]["counts"]["precise"] == 1
    assert g["coverage"]["design_coverage"] == "not_measured"

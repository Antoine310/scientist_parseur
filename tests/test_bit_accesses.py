"""PR #22 : correspondances syntaxiques de bits, sans déductions de largeur."""
import json

import pytest

from rtlprep.bitaccess import build_bit_access_index
from rtlprep.dependencies import build_dependency_graph
from rtlprep.mcp_data import ReadOnlyRtl


def n(kind, **kwargs):
    return {"kind": kind, **kwargs}


def ref(name):
    return n("NamedValue", symbol="123 " + name)


def lit(number):
    return n("IntegerLiteral", value=str(number))


def bit(name, selector):
    return n("ElementSelect", value=ref(name), selector=selector)


def part(name, high, low):
    return n("RangeSelect", value=ref(name), left=high, right=low)


def assign(lhs, rhs):
    return n("ContinuousAssign", assignment=n(
        "Assignment", left=lhs, right=rhs, isNonBlocking=False,
        source_file_start="bit_fixture.sv", source_line_start=12,
    ))


def ast(*assignments):
    names = ("a", "b", "out", "picked", "idx")
    return {"design": n("Root", members=[
        n("Instance", name="top", body=n("InstanceBody", name="top",
            members=[n("Variable", name=name, type="logic") for name in names]
            + list(assignments)))
    ])}


def rows(value):
    return build_bit_access_index(value, expected_top="top")["items"]


def test_static_concat_reports_rhs_lanes_without_inventing_target_width():
    source = n("Concatenation", operands=[
        part("a", lit(7), lit(4)),
        part("b", lit(3), lit(0)),
    ])
    result = rows(ast(assign(ref("out"), source)))
    assert len(result) == 1
    row = result[0]
    assert row["target"] == "top.out"
    assert row["coverage"] == "rhs_lanes_only"
    assert row["rhs_width"] == 8
    assert row["source_segments"] == [
        {"source": "top.a", "selection": {"kind": "range", "msb": 7, "lsb": 4},
         "rhs_lsb": 4, "rhs_msb": 7},
        {"source": "top.b", "selection": {"kind": "range", "msb": 3, "lsb": 0},
         "rhs_lsb": 0, "rhs_msb": 3},
    ]
    assert not any("target_lsb" in x for x in row["source_segments"])


def test_explicit_target_range_maps_to_matching_source_range():
    row = rows(ast(assign(
        part("out", lit(7), lit(4)),
        part("a", lit(3), lit(0)),
    )))[0]
    assert row["coverage"] == "explicit_target_lanes"
    assert row["source_segments"][0]["target_lsb"] == 4
    assert row["source_segments"][0]["target_msb"] == 7
    assert row["source_segments"][0]["rhs_lsb"] == 0


def test_static_element_select_maps_one_bit():
    row = rows(ast(assign(bit("out", lit(2)), bit("a", lit(5)))))[0]
    assert row["coverage"] == "explicit_target_lanes"
    assert row["source_segments"][0]["target_lsb"] == 2
    assert row["source_segments"][0]["selection"] == {"kind": "bit", "index": 5}


def test_elaborated_constant_arithmetic_in_range():
    upper = n("BinaryOp", op="Subtract",
              left=n("NamedValue", symbol="124 WIDTH", constant="8"),
              right=lit(1))
    row = rows(ast(assign(ref("out"), part("a", upper, lit(4)))))[0]
    assert row["coverage"] == "rhs_lanes_only"
    assert row["source_segments"][0]["selection"] == {
        "kind": "range", "msb": 7, "lsb": 4,
    }


@pytest.mark.parametrize("rhs,reason", [
    (bit("a", ref("idx")), "dynamic_or_unknown_index"),
    (part("a", ref("idx"), lit(0)), "dynamic_or_unknown_range"),
    (n("Concatenation", operands=[part("a", lit(3), lit(0)), ref("b")]),
     "source_width_unknown"),
    (n("BinaryOp", op="Add", left=bit("a", lit(0)), right=lit(1)),
     "unsupported_rhs_BinaryOp"),
    (n("Concatenation", operands=[]), "malformed_or_large_concatenation"),
])
def test_unknown_or_dynamic_is_partial_and_never_invents_a_mapping(rhs, reason):
    row = rows(ast(assign(ref("picked"), rhs)))[0]
    assert row["coverage"] == "partial"
    assert row["reason"] == reason
    assert row["source_segments"] == []
    assert row["rhs_width"] is None


def test_mismatched_lhs_width_refuses_to_map_lanes():
    row = rows(ast(assign(part("out", lit(3), lit(0)),
                          part("a", lit(7), lit(0)))))[0]
    assert row["coverage"] == "partial"
    assert row["reason"] == "target_rhs_width_mismatch"
    assert row["source_segments"] == []


def test_ordinary_whole_signal_assignment_is_out_of_scope():
    graph = build_bit_access_index(ast(assign(ref("out"), ref("a"))),
                                   expected_top="top")
    assert graph["items"] == []
    assert graph["counts"]["assignments_seen"] == 1


def test_mcp_read_only_pagination_and_old_snapshots(tmp_path):
    graph = build_dependency_graph(ast(assign(
        ref("out"), part("a", lit(7), lit(4)))), expected_top="top")
    path = tmp_path / "rtl_dependencies.json"
    path.write_text(json.dumps(graph), encoding="utf-8")
    api = ReadOnlyRtl(graph_file=path)
    assert api.capabilities()["bit_accesses_available"] is True
    response = api.bit_accesses("top.out", limit=1, offset=0)
    assert response["total"] == 1
    assert response["items"][0]["rhs_width"] == 4
    assert response["source_snapshot_status"] == "unverifiable"
    assert api.bit_accesses("top.a")["total"] == 0
    for limit, offset in ((0, 0), (101, 0), (1, -1)):
        with pytest.raises(ValueError):
            api.bit_accesses("top.out", limit, offset)
    with pytest.raises(KeyError):
        api.bit_accesses("../escape")
    del graph["bit_accesses"]
    path.write_text(json.dumps(graph), encoding="utf-8")
    legacy = ReadOnlyRtl(graph_file=path)
    assert legacy.capabilities()["bit_accesses_available"] is False
    with pytest.raises(ValueError, match="régénérer"):
        legacy.bit_accesses("top.out")

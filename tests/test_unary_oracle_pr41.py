"""Independent PR41 validation: audited source-bit expectations vs slang index.

The expected placements are written manually from the fixture's RTL
contract, not calculated by RTLPrep or the internal bit_accesses walker.
The actual *values* are checked separately by Verilator/cocotb in CI.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from rtlprep.manifest import load_design
from rtlprep.runner import dependency_design
from rtlprep import simulation


ROOT = Path(__file__).resolve().parents[1]
GOOD = ROOT / "tests/fixtures/unary_bit_pr41_good_design.json"
BAD = ROOT / "tests/fixtures/unary_bit_pr41_mutant_design.json"


def test_only_reviewed_top_is_allowed_to_invoke_the_independent_oracle():
    assert simulation.TEST_SUITES["unary_bit_pr40"] == (
        "rtlprep.sim_tests.unary_bit_oracle"
    )
    good, bad = load_design(GOOD), load_design(BAD)
    assert good.top == bad.top == "unary_bit_pr40"
    assert len(good.sources) == len(bad.sources) == 1
    assert good.sources[0] != bad.sources[0]
    assert "test" not in good.top


def test_mutant_removes_only_the_inversion_of_bit_15():
    good, bad = load_design(GOOD), load_design(BAD)
    original = good.sources[0].read_text(encoding="utf-8")
    mutated = bad.sources[0].read_text(encoding="utf-8")
    needle = "bit_o = ~instr_i[15];"
    assert original.count(needle) == 1
    assert mutated.count("bit_o = instr_i[15];") == 1
    # Only the intended behavior is changed; comments can differ.
    assert "mix_o = {instr_i[7:5], ~instr_i[4], instr_i[3:0]};" in mutated
    assert "wide_o = ~instr_i[3:0];" in mutated
    assert "!instr_i[3]" in mutated and "&instr_i[7:4]" in mutated


def test_refuse_faked_xunit_pass_with_no_cases(tmp_path):
    xml_path = tmp_path / "results.xml"
    xml_path.write_text("<testsuites/>", encoding="utf-8")
    with pytest.raises(ValueError, match="aucun testcase"):
        simulation.parse_cocotb_results(xml_path)


@pytest.mark.skipif(shutil.which("slang") is None,
                    reason="real slang v12.1 unavailable")
def test_slang_index_matches_independently_audited_unary_wiring(tmp_path):
    out = tmp_path / "analysis"
    result = dependency_design(load_design(GOOD), out, timeout=120)
    assert result["status"] == "passed", result
    graph = json.loads((out / "rtl_dependencies.json").read_text(encoding="utf-8"))
    bits = graph["bit_accesses"]
    rows = {x["target"].rsplit(".", 1)[-1]: x for x in bits["items"]}
    assert {"bit_o", "mix_o", "wide_o", "logical_o", "reduction_o"} == set(rows)
    assert bits["counts"]["captured"] == 5
    # The 3 one-to-one positional constructs are supported; reductions
    # and logical-not are not reclassified as direct bit-origin mappings.
    assert bits["counts"]["precise"] == 3
    assert bits["counts"]["partial"] == 2

    bit_o = rows["bit_o"]
    assert bit_o["rhs_width"] == 1
    assert bit_o["coverage"] == "rhs_lanes_only"
    assert bit_o["source_segments"] == [{
        "source": "unary_bit_pr40.instr_i",
        "selection": {"kind": "bit", "index": 15},
        "rhs_lsb": 0, "rhs_msb": 0,
        "value_transform": "bitwise_not",
    }]

    mix = rows["mix_o"]
    assert mix["rhs_width"] == 8
    assert mix["source_segments"] == [
        {"source": "unary_bit_pr40.instr_i",
         "selection": {"kind": "range", "msb": 7, "lsb": 5},
         "rhs_lsb": 5, "rhs_msb": 7},
        {"source": "unary_bit_pr40.instr_i",
         "selection": {"kind": "bit", "index": 4},
         "rhs_lsb": 4, "rhs_msb": 4,
         "value_transform": "bitwise_not"},
        {"source": "unary_bit_pr40.instr_i",
         "selection": {"kind": "range", "msb": 3, "lsb": 0},
         "rhs_lsb": 0, "rhs_msb": 3},
    ]
    wide = rows["wide_o"]
    assert wide["source_segments"] == [{
        "source": "unary_bit_pr40.instr_i",
        "selection": {"kind": "range", "msb": 3, "lsb": 0},
        "rhs_lsb": 0, "rhs_msb": 3,
        "value_transform": "bitwise_not",
    }]
    assert wide["rhs_width"] == 4
    for target in ("logical_o", "reduction_o"):
        assert rows[target]["coverage"] == "partial"
        assert rows[target]["reason"] == "unsupported_rhs_UnaryOp"
        assert rows[target]["source_segments"] == []
    assert graph["coverage"]["design_coverage"] == "not_measured"

"""PR42: audited 2-state c.j reference and negative-control infrastructure.

These hermetic tests do not simulate CVA6. A separate CI workflow runs
actual pinned OpenHW RTL through Verilator/cocotb and demands that the
single permitted mutant fail for the expected decoded output reason.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rtlprep.cva6_cj_reference import encode_cj, expected_cj_jal
from scripts import run_cva6_cj_oracle as probe
from scripts.run_cva6_compressed_decoder import TOP, UPSTREAM_COMMIT


def test_cj_encoding_has_only_eleven_variable_low_bits():
    assert encode_cj(0) == 0xA001
    assert encode_cj(2047) == 0xBFFD
    for payload in range(2048):
        val = encode_cj(payload)
        assert (val & 0xE003) == 0xA001
        assert (val >> 2) & 0x7FF == payload
    assert TOP == "rtlprep_cva6_compressed_decoder"
    assert UPSTREAM_COMMIT == "742dc82a0c706e0a3bfb98b709fd3ee06d50d12a"


def test_known_jal_and_bit7_semantics_in_pure_reference():
    # C.J 0 immediate -> JAL x0, 0. Bit 7 is the inversion of
    # a fixed-one opcode bit15, hence zero.
    assert expected_cj_jal(encode_cj(0)) == 0x6F
    assert expected_cj_jal(encode_cj(0x400)) == (
        0x8000_0000 | (0x1FF << 12) | 0x6F
    )
    for payload in range(2048):
        word = expected_cj_jal(encode_cj(payload))
        assert 0 <= word < (1 << 32)
        assert (word & 0x7F) == 0x6F
        assert (word & 0x80) == 0  # original ~instr_i[15]


def test_upper_halfword_never_affects_expected_cj_decoding():
    for payload in (0, 1, 7, 63, 255, 511, 1023, 2047):
        ref = expected_cj_jal(encode_cj(payload, 0))
        for upper in (0, 1, 0xFFFF, 0xA5A5, 0x8000):
            assert expected_cj_jal(encode_cj(payload, upper)) == ref


@pytest.mark.parametrize("payload,upper", [
    (-1, 0), (2048, 0), (True, 0), (0, -1),
    (0, 0x10000), (0, False), ("1", 0),
])
def test_reference_rejects_bad_abstract_inputs(payload, upper):
    with pytest.raises(ValueError):
        encode_cj(payload, upper)


@pytest.mark.parametrize("value", [-1, 0, 0xA000, 0xFFFF_FFFF, 1 << 32, None, True])
def test_cj_reference_rejects_non_cj_or_out_of_range(value):
    with pytest.raises(ValueError):
        expected_cj_jal(value)


def test_mutation_is_single_exact_change_and_preserves_other_source_bytes():
    original = ("module compressed_decoder;\n"
                + probe.MUTATION_OLD + "\n"
                + "endmodule\n")
    changed = probe.mutate_decoder(original)
    assert changed == original.replace(probe.MUTATION_OLD,
                                       probe.MUTATION_NEW, 1)
    assert "~instr_i[15]" not in changed
    assert "instr_i[15]" in changed
    with pytest.raises(ValueError, match="missing or duplicated"):
        probe.mutate_decoder(changed)
    with pytest.raises(ValueError, match="missing or duplicated"):
        probe.mutate_decoder(original + probe.MUTATION_OLD)


def test_cocotb_xunit_requires_exact_mutant_output_failure(tmp_path):
    xml = tmp_path / "xunit.xml"
    xml.write_text(
        "<testsuites><testsuite>"
        "<testcase name='cj'><failure message='PR42_CJ_VALUE_MISMATCH "
        "bit7_diff=1'/></testcase></testsuite></testsuites>",
        encoding="utf-8",
    )
    assert probe._oracle_failure_evidence(xml) is True
    xml.write_text(
        "<testsuites><testsuite>"
        "<testcase name='cj'><failure message='unrelated build failure'/>"
        "</testcase></testsuite></testsuites>",
        encoding="utf-8",
    )
    assert probe._oracle_failure_evidence(xml) is False
    xml.write_text(
        "<testsuites><testsuite>"
        "<testcase name='cj'><failure message='PR42_CJ_VALUE_MISMATCH "
        "bit7_diff=0'/></testcase></testsuite></testsuites>",
        encoding="utf-8",
    )
    assert probe._oracle_failure_evidence(xml) is False


def test_non_pinned_checkout_does_not_run_verilator(tmp_path):
    with pytest.raises((FileNotFoundError, ValueError)):
        probe.run(tmp_path / "missing", tmp_path / "output", "gold")
    with pytest.raises(ValueError, match="variant"):
        probe.run(tmp_path / "missing", tmp_path / "output", "nonexistent")


def test_oracle_is_not_derived_from_bitaccess_graph_or_slang():
    source = Path(probe.__file__).resolve().parents[1] / (
        "rtlprep/cva6_cj_reference.py"
    )
    code = source.read_text(encoding="utf-8")
    assert "from .bitaccess import" not in code
    assert "import slang" not in code
    assert "build_dependency_graph(" not in code
    assert "get_runner(" not in code

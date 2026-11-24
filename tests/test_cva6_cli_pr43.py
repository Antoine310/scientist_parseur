"""PR43: independent C.LI reference tests, ISA/HINT domain and mutation gates.

Hermetic Python tests are not a simulator. The dedicated CI job separately
runs the *official pinned OpenHW CVA6 RTL* via Verilator/cocotb.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from rtlprep.cva6_cli_reference import (
    cli_encoding_class, encode_cli, expected_cli_addi,
)
from scripts import run_cva6_cli_oracle as probe
from scripts.run_cva6_compressed_decoder import TOP, UPSTREAM_COMMIT


def test_exact_cli_family_2048_low_halfword_encodings_and_isa_hints():
    assert encode_cli(0) == 0x4001
    assert encode_cli(0x7FF) == 0x5FFD
    assert TOP == "rtlprep_cva6_compressed_decoder"
    assert UPSTREAM_COMMIT == "742dc82a0c706e0a3bfb98b709fd3ee06d50d12a"
    seen = set()
    counts = {"valid_cli": 0, "hint_rd_zero": 0}
    for payload in range(2048):
        encoded = encode_cli(payload)
        seen.add(encoded)
        assert (encoded & 0xE003) == 0x4001
        assert (encoded >> 2) & 0x7FF == payload
        counts[cli_encoding_class(encoded)] += 1
    assert len(seen) == 2048
    assert counts == {"valid_cli": 1984, "hint_rd_zero": 64}


def test_independent_reference_sign_extension_registers_and_imm_bits():
    # ADDI x0,x0,0, a C.LI encoding with rd=x0 (ISA HINT).
    assert expected_cli_addi(encode_cli(0)) == 0x00000013
    # Variable low immediate bit2 becomes output immediate bit20.
    assert expected_cli_addi(encode_cli(1)) == 0x00100013
    # Variable source bit6 becomes output bit24 (NOT inverted in original).
    assert expected_cli_addi(encode_cli(0x10)) == 0x01000013
    # Variable rd x1 becomes output x1, with x0 as the source.
    assert expected_cli_addi(encode_cli(0x20)) == 0x00000093
    # Sign bit instr_i[12] is replicated into the 12-bit immediate.
    assert expected_cli_addi(encode_cli(0x400)) == 0xFE000013
    assert expected_cli_addi(encode_cli(0x420)) == 0xFE000093
    assert expected_cli_addi(encode_cli(0x7FF)) == 0xFFF00F93


def test_2048_reference_results_and_independent_field_invariants():
    for payload in range(2048):
        instruction = encode_cli(payload)
        result = expected_cli_addi(instruction)
        assert (result & 0x7F) == 0x13
        assert (result >> 12) & 0x7 == 0  # ADDI funct3
        assert (result >> 15) & 0x1F == 0  # source rs1=x0
        assert (result >> 7) & 0x1F == (payload >> 5) & 0x1F
        imm6 = (payload & 0x1F) | (((payload >> 10) & 1) << 5)
        expect_imm12 = imm6 | (0xFC0 if imm6 & 0x20 else 0)
        assert (result >> 20) & 0xFFF == expect_imm12
        assert (result >> 24) & 1 == (payload >> 4) & 1
    assert expected_cli_addi(encode_cli(0x10)) ^ expected_cli_addi(encode_cli(0)) == 1 << 24


def test_upper_halfword_does_not_modify_decode_for_selected_samples():
    for payload in (0, 0x10, 0x20, 0x400, 0x555, 0x7FF):
        baseline = expected_cli_addi(encode_cli(payload))
        for high in (0x0000, 0xFFFF, 0x1234, 0x8000):
            assert expected_cli_addi(encode_cli(payload, high)) == baseline
            assert cli_encoding_class(encode_cli(payload, high)) == (
                "hint_rd_zero" if ((payload >> 5) & 0x1F) == 0 else "valid_cli"
            )


@pytest.mark.parametrize("payload,upper", [
    (-1,0), (2048,0), (True,0), ("1",0), (0,-1),
    (0,1 << 16), (0,False), (0,1.0),
])
def test_encoding_refuses_malformed_inputs(payload, upper):
    with pytest.raises(ValueError):
        encode_cli(payload, upper)


@pytest.mark.parametrize("value", [
    -1, 0, 0x6001, 0xFFFF_FFFF, 1 << 32, None, True, "0x4001",
])
def test_reference_refuses_other_instruction_families(value):
    with pytest.raises(ValueError):
        expected_cli_addi(value)
    with pytest.raises(ValueError):
        cli_encoding_class(value)


def test_negative_control_mutates_only_a_single_variable_input_bit():
    # This is an exact source anchor from official CVA6, not a replacement
    # of a random occurrence of instr_i[6:2] elsewhere in the decoder.
    original = "module compressed_decoder;\n" + probe.MUTATION_OLD + "\nendmodule\n"
    mutated = probe.mutate_decoder(original)
    assert mutated == original.replace(probe.MUTATION_OLD, probe.MUTATION_NEW, 1)
    assert "              {~instr_i[6], instr_i[5:2]}," in mutated
    assert "              instr_i[6:2]," not in mutated
    assert probe.MUTATION_OLD.count("riscv::OpcodeC1Li") == 1
    with pytest.raises(ValueError, match="missing or duplicated"):
        probe.mutate_decoder(mutated)
    with pytest.raises(ValueError, match="missing or duplicated"):
        probe.mutate_decoder(original + probe.MUTATION_OLD)


def test_xml_only_accepts_real_bit24_mutant_failure(tmp_path):
    xml = tmp_path / "results.xml"
    header = "<testsuites><testsuite><testcase name='decode'>"
    footer = "</testcase></testsuite></testsuites>"
    xml.write_text(header + "<failure message='PR43_CLI_VALUE_MISMATCH "
                   "class=valid_cli bit24_diff=1'/>" + footer, encoding="utf-8")
    assert probe._oracle_failure_evidence(xml)
    for error in ("compiler error",
                  "PR43_CLI_VALUE_MISMATCH class=valid_cli bit24_diff=0",
                  "PR43_CLI_VALUE_MISMATCH class=hint_rd_zero bit24_diff=1",
                  "PR43_CLI_VALUE_MISMATCH bit24_diff=1",
                  "PR42_CJ_VALUE_MISMATCH class=valid_cli bit24_diff=1"):
        xml.write_text(header + f"<failure message='{error}'/>" + footer,
                       encoding="utf-8")
        assert not probe._oracle_failure_evidence(xml)
    xml.write_text(header + footer, encoding="utf-8")
    assert not probe._oracle_failure_evidence(xml)


def test_unknown_variant_or_checkout_refused_before_running_eda(tmp_path):
    with pytest.raises(ValueError, match="variant"):
        probe.run(tmp_path / "missing", tmp_path / "result", "other")
    with pytest.raises((FileNotFoundError, ValueError)):
        probe.run(tmp_path / "missing", tmp_path / "result", "gold")
    root = tmp_path / "upstream"
    root.mkdir()
    with pytest.raises(ValueError, match="output directory must not touch"):
        probe.run(root, root / "reports", "gold")


def test_reference_is_pure_and_does_not_calculate_expected_values_from_rtlprep():
    source = (Path(__file__).resolve().parents[1] /
              "rtlprep/cva6_cli_reference.py").read_text(encoding="utf-8")
    assert "from rtlprep.bitaccess import" not in source
    assert "import slang" not in source
    assert "build_dependency_graph(" not in source
    assert "get_runner(" not in source
    assert "import cocotb" not in source

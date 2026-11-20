"""Contrats de sécurité d'un laboratoire RTL contrôlé, sans outils EDA."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rtlprep.security_lab import validate_security_design
from rtlprep.manifest import load_design
from rtlprep.simulation import TEST_SUITES, simulate
from rtlprep.formal import PROOF_SUITES, formal_verify
from rtlprep.equivalence import validate_pair

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/security_csr"


def design(filename="design.json"):
    return load_design(FIXTURE / filename)


def test_three_approved_designs_have_same_top_and_distinct_sources():
    assert {design(x).top for x in (
        "design.json", "buggy_design.json", "refactored_design.json"
    )} == {"secure_csr"}
    assert len({str(design(x).sources[0]) for x in (
        "design.json", "buggy_design.json", "refactored_design.json"
    )}) == 3
    for name in ("design.json", "buggy_design.json", "refactored_design.json"):
        validate_security_design(design(name))


def test_simulation_and_formal_both_reuse_same_approved_benches(tmp_path, monkeypatch):
    assert TEST_SUITES["secure_csr"] == "rtlprep.sim_tests.secure_csr"
    assert PROOF_SUITES["secure_csr"] == ("secure_csr_properties.sv",
                                         "secure_csr_formal")
    from rtlprep import simulation, formal
    monkeypatch.setattr(simulation.shutil, "which", lambda _: None)
    monkeypatch.setattr(formal.shutil, "which", lambda _: None)
    for name in ("design.json", "buggy_design.json"):
        assert simulate(design(name), tmp_path / name)["status"] == "missing_tool"
        assert formal_verify(design(name), tmp_path / ("formal-" + name))["status"] == "missing_tool"


def test_eqy_gold_gate_pairs_allow_good_refactor_and_negative_control():
    validate_pair(design(), design("refactored_design.json"))
    validate_pair(design(), design("buggy_design.json"))
    with pytest.raises(ValueError, match="référence gold"):
        validate_pair(design("buggy_design.json"), design("refactored_design.json"))
    with pytest.raises(ValueError, match="variante gate"):
        validate_pair(design(), design())


def test_spoofed_top_source_does_not_gain_simulation_or_proof(tmp_path):
    bad_source = tmp_path / "secure_csr.sv"
    bad_source.write_text(FIXTURE.joinpath("secure_csr.sv").read_text())
    manifest = tmp_path / "design.json"
    manifest.write_text(json.dumps({
        "top": "secure_csr", "sources": ["secure_csr.sv"],
        "include_dirs": [], "defines": []
    }))
    d = load_design(manifest)
    with pytest.raises(ValueError, match="non approuvée"):
        validate_security_design(d)
    assert simulate(d, tmp_path / "sim")["status"] == "failed"
    assert formal_verify(d, tmp_path / "formal")["status"] == "failed"


def test_unprivileged_debug_unlocked_is_explicit_security_contract():
    spec = (ROOT / "rtlprep/formal_specs/secure_csr_properties.sv").read_text()
    good = (FIXTURE / "secure_csr.sv").read_text()
    bad = (FIXTURE / "secure_csr_buggy.sv").read_text()
    assert "assert(!write_accepted_o)" in spec
    assert "write_i && machine_mode_i && !debug_locked_i" in good
    assert "machine_mode_i || !debug_locked_i" in bad
    assert "initial assume(!rst_n)" in spec
    assert "cover(value_o == 8'hA5)" in spec

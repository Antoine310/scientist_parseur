"""Tests EQY de sécurité, statuts et non-réutilisation des résultats.

Tous ces tests fonctionnent sans outils EDA ; la CI lance EQY réel ailleurs.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from rtlprep import equivalence
from rtlprep.manifest import load_design

ROOT = Path(__file__).resolve().parents[1]


def counter_gold():
    return load_design(ROOT / "examples/counter/design.json")


def counter_gate(which="refactored_design.json"):
    return load_design(ROOT / "examples/counter" / which)


def fsm_gold():
    return load_design(ROOT / "examples/fsm/design.json")


def fsm_gate():
    return load_design(ROOT / "examples/fsm/refactored_design.json")


def test_config_proves_same_top_with_distinct_gold_gate_sources():
    cfg = equivalence.make_eqy_config(counter_gold(), counter_gate())
    assert "[gold]" in cfg and "[gate]" in cfg
    assert 'counter.sv"' in cfg and 'counter_refactored.sv"' in cfg
    assert "read_verilog -formal -sv" in cfg
    assert cfg.count("prep -top counter") == 2
    assert "[strategy induction]" in cfg
    assert "engine smtbmc z3" in cfg
    assert "depth 12" in cfg


def test_fsm_pair_allowed_and_unsupported_pair_denied():
    cfg = equivalence.make_eqy_config(fsm_gold(), fsm_gate())
    assert cfg.count("prep -top handshake_fsm") == 2
    with pytest.raises(ValueError, match="tops incompatibles"):
        equivalence.make_eqy_config(counter_gold(), fsm_gate())
    with pytest.raises(ValueError, match="non autorisée|non approuvés"):
        equivalence.make_eqy_config(
            load_design(ROOT / "examples/hierarchy/design.json"),
            counter_gate(),
        )


def test_unapproved_gold_and_gate_paths_denied():
    with pytest.raises(ValueError, match="référence gold"):
        equivalence.validate_pair(counter_gate(), counter_gate())
    with pytest.raises(ValueError, match="variante gate"):
        equivalence.validate_pair(counter_gold(), counter_gold())


def test_fake_pass_from_old_run_not_reused(tmp_path, monkeypatch):
    work = tmp_path / "eqy_work"
    work.mkdir()
    (work / "PASS").write_text("")
    (tmp_path / "equivalence.result.json").write_text('{"status":"passed"}')
    monkeypatch.setattr(equivalence.shutil, "which", lambda exe: None)
    result = equivalence.equivalence_check(counter_gold(), counter_gate(), tmp_path)
    assert result["status"] == "missing_tool"
    assert result["equivalent"] is None
    assert not work.exists()
    assert json.loads((tmp_path / "equivalence.result.json").read_text())["status"] == "missing_tool"


def test_conflicting_eqy_markers_cannot_pass(tmp_path):
    work = tmp_path / "eqy_work"
    work.mkdir()
    assert equivalence.read_eqy_verdict(work) is None
    (work / "PASS").touch()
    assert equivalence.read_eqy_verdict(work) == "PASS"
    (work / "FAIL").touch()
    assert equivalence.read_eqy_verdict(work) == "CONFLICT"


def test_invalid_timeout_does_not_call_eqy(tmp_path, monkeypatch):
    monkeypatch.setattr(equivalence.shutil, "which", lambda _: pytest.fail("tools should not run"))
    result = equivalence.equivalence_check(counter_gold(), counter_gate(), tmp_path, timeout=0)
    assert result["status"] == "failed"


def setup_mock(monkeypatch, *, marker="PASS", statuses=None, traces=False,
               code="passed", partitions=True):
    monkeypatch.setattr(equivalence.shutil, "which", lambda _: "/usr/bin/eqy")
    monkeypatch.setattr(equivalence.subprocess, "run",
                        lambda *a, **k: subprocess.CompletedProcess(
                            args=a[0], returncode=0, stdout="EQY 3.0", stderr=""
                        ))
    def fake_command(command, name, out, timeout):
        work = out / "eqy_work"
        work.mkdir()
        if marker:
            (work / marker).touch()
        if partitions:
            (work / "partition.list").write_text("counter.count\n")
        for i, status in enumerate(statuses or []):
            folder = work / "strategies" / f"partition{i}" / "induction"
            folder.mkdir(parents=True)
            (folder / "status").write_text(f"{status} 1 0\n")
            if traces:
                (folder / "trace.vcd").write_text("$date EQY $end\n")
        return {"status": code, "returncode": 0 if code == "passed" else 2,
                "elapsed_seconds": 0.1, "argv": command}
    monkeypatch.setattr(equivalence, "run_command", fake_command)


def test_pass_needs_valid_marker_and_partitions(tmp_path, monkeypatch):
    setup_mock(monkeypatch)
    result = equivalence.equivalence_check(counter_gold(), counter_gate(), tmp_path)
    assert result["status"] == "passed"
    assert result["equivalent"] is True
    assert result["partition_count"] == 1

    setup_mock(monkeypatch, partitions=False)
    result = equivalence.equivalence_check(counter_gold(), counter_gate(), tmp_path)
    assert result["status"] == "error"
    assert result["equivalent"] is None


def test_fail_with_real_partition_trace_is_non_equivalent(tmp_path, monkeypatch):
    setup_mock(monkeypatch, marker="FAIL", statuses=["FAIL"], traces=True, code="failed")
    result = equivalence.equivalence_check(
        counter_gold(), counter_gate("buggy_design.json"), tmp_path
    )
    assert result["status"] == "failed"
    assert result["equivalent"] is False
    assert Path(result["trace_files"][0]).is_file()
    assert result["partition_statuses"][0]["verdict"] == "FAIL"


def test_unknown_or_unproven_not_automatically_non_equivalent(tmp_path, monkeypatch):
    setup_mock(monkeypatch, marker="FAIL", statuses=["UNKNOWN"], code="failed")
    result = equivalence.equivalence_check(counter_gold(), counter_gate(), tmp_path)
    assert result["status"] == "inconclusive"
    assert result["equivalent"] is None


def test_missing_eqy_status_is_not_passed_even_on_exit_zero(tmp_path, monkeypatch):
    setup_mock(monkeypatch, marker=None)
    result = equivalence.equivalence_check(counter_gold(), counter_gate(), tmp_path)
    assert result["status"] == "error"
    assert result["equivalent"] is None


def test_process_timeout_stays_timeout(tmp_path, monkeypatch):
    setup_mock(monkeypatch, marker=None, code="timeout")
    result = equivalence.equivalence_check(counter_gold(), counter_gate(), tmp_path)
    assert result["status"] == "timeout"
    assert result["equivalent"] is None

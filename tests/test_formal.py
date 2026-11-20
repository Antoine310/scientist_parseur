"""Tests du moteur SBY hors EDA : statuts, preuves, couverture, faux succès."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rtlprep import formal
from rtlprep.manifest import load_design

ROOT = Path(__file__).resolve().parents[1]


def design(which="counter", *, bad=False):
    if which == "counter":
        path = "examples/counter/buggy_design.json" if bad else "examples/counter/design.json"
    else:
        path = "examples/fsm/design.json"
    return load_design(ROOT / path)


def test_config_has_no_unreviewed_script_and_selects_correct_properties():
    d = design("counter")
    cfg = formal.create_sby_config(
        d, task="prove", source=d.sources[0],
        properties=ROOT / "rtlprep/formal_specs/counter_properties.sv",
    )
    assert "[script]" in cfg
    assert "mode prove" in cfg
    assert "smtbmc z3" in cfg
    assert "prep -top counter_formal" in cfg
    assert "counter.sv" in cfg
    assert "[files]" in cfg
    with pytest.raises(ValueError):
        formal.create_sby_config(d, task="invalid", source=d.sources[0],
                                properties=ROOT / "rtlprep/formal_specs/counter_properties.sv")


@pytest.mark.parametrize("formal_status,exit_status,expected", [
    ("PASS", "passed", "passed"),
    ("PASS", "failed", "failed"),
    ("FAIL", "failed", "failed"),
    ("UNKNOWN", "failed", "inconclusive"),
    ("ERROR", "failed", "error"),
    ("TIMEOUT", "timeout", "timeout"),
    (None, "passed", "failed"),
])
def test_sby_status_contract(formal_status, exit_status, expected):
    assert formal._classify({"status": exit_status}, formal_status) == expected


def test_missing_tools_never_reuses_old_pass_or_trace(tmp_path, monkeypatch):
    out = tmp_path / "proofs"
    out.mkdir()
    (out / "formal.result.json").write_text('{"status": "passed"}')
    old = out / "formal_prove_work"
    old.mkdir()
    (old / "status").write_text("PASS")
    monkeypatch.setattr(formal.shutil, "which", lambda exe: None)
    report = formal.formal_verify(design(), out)
    assert report["status"] == "missing_tool"
    assert report["proof"] is None
    assert not old.exists()
    assert json.loads((out / "formal.result.json").read_text())["status"] == "missing_tool"


def test_missing_approved_suite_refuses_to_run_external_tools(tmp_path, monkeypatch):
    d = load_design(ROOT / "examples/hierarchy/design.json")
    monkeypatch.setattr(formal.shutil, "which",
                        lambda _: pytest.fail("no tool lookup for unknown top"))
    report = formal.formal_verify(d, tmp_path)
    assert report["status"] == "failed"
    assert "Aucun banc formel" in report["error"]


def mock_tools(monkeypatch, statuses):
    """Create true SBY-style work/status files without running EDA binaries."""
    monkeypatch.setattr(formal.shutil, "which", lambda exe: "/usr/bin/" + exe)
    class Version:
        stdout = "SBY 1.0\n"
    monkeypatch.setattr(formal.subprocess, "run", lambda *a, **kw: Version())
    def fake_run(argv, task, out, timeout):
        stage = "prove" if task.endswith("prove") else "cover"
        value = statuses[stage]
        work = out / (task + "_work")
        work.mkdir()
        (work / "status").write_text(value)
        if value == "FAIL":
            trace = work / "engine_0"
            trace.mkdir()
            (trace / "trace.vcd").write_text("$date formal test $end\n")
        return {"status": "passed" if value == "PASS" else "failed",
                "returncode": 0 if value == "PASS" else 2,
                "elapsed_seconds": 0.1}
    monkeypatch.setattr(formal, "run_command", fake_run)


def test_proved_and_covered_requires_two_passes(tmp_path, monkeypatch):
    mock_tools(monkeypatch, {"prove": "PASS", "cover": "PASS"})
    report = formal.formal_verify(design(), tmp_path)
    assert report["status"] == "passed"
    assert report["proof"]["sby_status"] == "PASS"
    assert report["cover"]["sby_status"] == "PASS"
    assert (tmp_path / "formal_prove.sby").exists()
    assert (tmp_path / "formal_cover.sby").exists()


def test_counterexample_preserved_on_mutant_failure(tmp_path, monkeypatch):
    mock_tools(monkeypatch, {"prove": "FAIL", "cover": "PASS"})
    report = formal.formal_verify(design(bad=True), tmp_path)
    assert report["status"] == "failed"
    assert report["proof"]["sby_status"] == "FAIL"
    assert len(report["proof"]["trace_files"]) == 1
    assert report["cover"] is None
    assert Path(report["proof"]["trace_files"][0]).exists()


def test_cover_unknown_not_a_success(tmp_path, monkeypatch):
    mock_tools(monkeypatch, {"prove": "PASS", "cover": "UNKNOWN"})
    report = formal.formal_verify(design("handshake_fsm"), tmp_path)
    assert report["status"] == "inconclusive"
    assert report["proof"]["status"] == "passed"
    assert report["cover"]["status"] == "inconclusive"


def test_zero_timeout_is_rejected_before_eda(tmp_path):
    report = formal.formal_verify(design(), tmp_path, timeout=0)
    assert report["status"] == "failed"
    assert "timeout" in report["error"]

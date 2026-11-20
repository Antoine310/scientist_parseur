"""Tests des statuts de simulation, sans besoin de Verilator ou cocotb."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from rtlprep.manifest import load_design
from rtlprep import simulation

ROOT = Path(__file__).resolve().parents[1]


def design(name="design.json"):
    return load_design(ROOT / "examples/counter" / name)


def xml(path: Path, *testcase_xml: str):
    path.write_text("<testsuites><testsuite>" + "".join(testcase_xml) +
                    "</testsuite></testsuites>", encoding="utf-8")


def test_parse_cocotb_xunit_passed(tmp_path):
    p = tmp_path / "simulation_results.xml"
    xml(p, '<testcase name="reset"/>', '<testcase name="wraparound"/>',
        '<testcase name="enable"/>')
    counts = simulation.parse_cocotb_results(p)
    assert (counts["tests"], counts["passed"], counts["failed"], counts["skipped"]) == (
        3, 3, 0, 0
    )


def test_parse_cocotb_xunit_failed_and_skipped(tmp_path):
    p = tmp_path / "simulation_results.xml"
    xml(p, '<testcase name="reset"><failure message="bad"/></testcase>',
        '<testcase name="other"><skipped/></testcase>',
        '<testcase name="fine"/>')
    counts = simulation.parse_cocotb_results(p)
    assert (counts["tests"], counts["passed"], counts["failed"], counts["skipped"]) == (
        3, 1, 1, 1
    )
    assert [x["status"] for x in counts["testcases"]] == [
        "failed", "skipped", "passed"
    ]


def test_xunit_without_testcases_cannot_pass(tmp_path):
    p = tmp_path / "simulation_results.xml"
    p.write_text("<testsuites/>")
    with pytest.raises(ValueError, match="aucun testcase"):
        simulation.parse_cocotb_results(p)


def test_simulation_requires_real_tools_and_deletes_stale_results(tmp_path, monkeypatch):
    for filename in ("simulation_results.xml", "simulation.result.json",
                     "simulation.stdout.log", "simulation.stderr.log"):
        (tmp_path / filename).write_text("stale")
    monkeypatch.setattr(simulation.shutil, "which", lambda name: None)
    monkeypatch.setattr(simulation.importlib.util, "find_spec", lambda name: None)
    result = simulation.simulate(design(), tmp_path)
    assert result["status"] == "missing_tool"
    assert not (tmp_path / "simulation_results.xml").exists()
    assert json.loads((tmp_path / "simulation.result.json").read_text())["status"] == "missing_tool"


def test_unsupported_top_does_not_run_compiler(tmp_path, monkeypatch):
    d = load_design(ROOT / "examples/hierarchy/design.json")
    monkeypatch.setattr(simulation.shutil, "which", lambda name: pytest.fail("should not test tools"))
    report = simulation.simulate(d, tmp_path)
    assert report["status"] == "failed"
    assert "Aucun banc cocotb approuvé" in report["error"]


def prepare_fake_runner(monkeypatch, result_xml):
    monkeypatch.setattr(simulation.shutil, "which", lambda name: "/usr/bin/" + name)
    monkeypatch.setattr(simulation.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(simulation.importlib.metadata, "version", lambda name: "2.0.1")
    monkeypatch.setattr(simulation.subprocess, "run",
                        lambda *args, **kwargs: subprocess.CompletedProcess(
                            args=args[0], returncode=0, stdout="Verilator 5.040", stderr=""
                        ))
    def fake_command(cmd, label, out, timeout):
        if result_xml is not None:
            (out / "simulation_results.xml").write_text(result_xml, encoding="utf-8")
        return {"status": "passed", "returncode": 0, "elapsed_seconds": 1.5,
                "argv": cmd}
    monkeypatch.setattr(simulation, "run_command", fake_command)


def test_xml_failure_overrides_successful_process(tmp_path, monkeypatch):
    prepare_fake_runner(monkeypatch,
                        '<testsuites><testsuite><testcase name="bad">'
                        '<failure message="wrong result"/></testcase></testsuite></testsuites>')
    result = simulation.simulate(design(), tmp_path)
    assert result["status"] == "failed"
    assert result["returncode"] == 0
    assert result["failed"] == 1
    assert result["tests"] == 1
    assert json.loads((tmp_path / "simulation.result.json").read_text())["status"] == "failed"


def test_missing_xml_after_exit_zero_is_not_passed(tmp_path, monkeypatch):
    prepare_fake_runner(monkeypatch, None)
    result = simulation.simulate(design(), tmp_path)
    assert result["status"] == "failed"
    assert "Aucun rapport xUnit" in result["error"]


def test_skipped_cocotb_test_is_inconclusive(tmp_path, monkeypatch):
    prepare_fake_runner(monkeypatch,
                        '<testsuites><testsuite><testcase name="skip">'
                        '<skipped/></testcase></testsuite></testsuites>')
    result = simulation.simulate(design(), tmp_path)
    assert result["status"] == "inconclusive"
    assert result["skipped"] == 1


def test_timeout_keeps_status_and_no_success(tmp_path, monkeypatch):
    prepare_fake_runner(monkeypatch, None)
    def timed_out(*args, **kwargs):
        return {"status": "timeout", "returncode": None,
                "elapsed_seconds": 2.0, "argv": args[0], "error": "Timeout de 2 s"}
    monkeypatch.setattr(simulation, "run_command", timed_out)
    result = simulation.simulate(design(), tmp_path, timeout=2)
    assert result["status"] == "timeout"
    assert result["returncode"] is None


def test_timeout_argument_rejected_before_build(tmp_path):
    result = simulation.simulate(design(), tmp_path, timeout=0)
    assert result["status"] == "failed"
    assert "timeout" in result["error"]

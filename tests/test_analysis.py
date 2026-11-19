import json

import pytest

from rtlprep.analysis import summarize_ast
from rtlprep.manifest import load_design
from rtlprep import runner


def _instance(name, module, members=None):
    return {"kind": "Instance", "name": name, "body": {
        "kind": "InstanceBody", "name": module, "members": members or [],
    }}


def test_hierarchy_tracks_distinct_instances():
    ast = {"design": {"kind": "Root", "name": "$root", "members": [
        _instance("hierarchy_top", "hierarchy_top", [
            _instance("first", "leaf", [
                {"kind": "Port", "name": "enable", "direction": "In", "type": "logic"}
            ]),
            _instance("second", "leaf"),
        ])
    ]}}
    got = summarize_ast(ast, expected_top="hierarchy_top")
    assert got["instance_count"] == 3
    assert [x["hierarchy_path"] for x in got["instances"]] == [
        "hierarchy_top", "hierarchy_top.first", "hierarchy_top.second"
    ]
    assert got["instances"][1]["ports"][0]["name"] == "enable"


@pytest.mark.parametrize("ast", [
    {}, {"design": []}, {"design": {"kind": "Root"}},
    {"design": {"kind": "Root", "members": []}},
    {"design": {"kind": "Root", "members": [_instance("top", "top", [])], "unused": None}},
])
def test_validation_of_malformed_or_wrong_top(ast):
    # Le dernier cas est valide structurellement, mais pas pour le top 'counter'.
    with pytest.raises(ValueError):
        summarize_ast(ast, expected_top="counter")


def test_duplicate_paths_rejected():
    ast = {"design": {"kind": "Root", "members": [
        _instance("top", "top", [_instance("leaf", "leaf"), _instance("leaf", "leaf")])
    ]}}
    with pytest.raises(ValueError, match="dupliqué"):
        summarize_ast(ast, expected_top="top")


def test_analyze_rejects_stale_ast_when_tool_missing(tmp_path, monkeypatch):
    from pathlib import Path
    manifest = Path(__file__).resolve().parents[1] / "examples/counter/design.json"
    d = load_design(manifest)
    out = tmp_path / "reports"
    out.mkdir()
    (out / "elaborated_ast.json").write_text('{"design": {"kind": "Root", "members": []}}')
    (out / "design_summary.json").write_text('{"fake": true}')
    monkeypatch.setattr(runner.shutil, "which", lambda name: None)
    got = runner.analyze(d, out, 1)
    assert got["status"] == "missing_tool"
    assert not (out / "design_summary.json").exists()
    assert not (out / "elaborated_ast.json").exists()


def test_analyze_rejects_schema_and_updates_report(tmp_path, monkeypatch):
    from pathlib import Path
    manifest = Path(__file__).resolve().parents[1] / "examples/counter/design.json"
    d = load_design(manifest)
    monkeypatch.setattr(runner.shutil, "which", lambda name: "/usr/bin/slang")

    class Dummy:
        returncode = 0
        stdout = "compiled"
        stderr = ""

    # Simule un slang qui retourne 0 mais exporte un JSON incompatible.
    def fake_run(cmd, **kwargs):
        Path(cmd[cmd.index("--ast-json") + 1]).write_text('{"unexpected": true}')
        return Dummy()

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    result = runner.analyze(d, tmp_path, 1)
    assert result["status"] == "failed"
    assert "design.kind=Root" in result["error"]
    saved = json.loads((tmp_path / "analyze.result.json").read_text())
    assert saved["status"] == "failed"
    assert not (tmp_path / "design_summary.json").exists()

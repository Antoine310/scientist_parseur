"""Tests du schéma d'index sans compilateur, avec fixtures non ambiguës."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from rtlprep.index import (build_index, get_instance, get_instance_tree,
                           get_module_summary, get_signal_info,
                           get_source_context, list_modules)
from rtlprep.manifest import load_design
from rtlprep.runner import index_design
from rtlprep import runner

ROOT = Path(__file__).resolve().parents[1]


def node(kind, name, **kwargs):
    return {"kind": kind, "name": name, "source_file": "example.sv",
            "source_line": 3, "source_column": 2, **kwargs}


def instance(name, mod, body):
    return node("Instance", name, body=node("InstanceBody", mod, members=body))


def sample_ast():
    p_in = node("Port", "in_a", direction="In", type="logic")
    p_out = node("Port", "out_z", direction="Out", type="logic")
    internal = node("Variable", "out_z", type="logic")
    leaf_body = [p_in, node("Net", "in_a", type="logic"), p_out, internal]
    return {"design": {"kind": "Root", "members": [
        instance("top", "top", [
            node("Port", "clk", direction="In", type="logic"),
            node("Net", "clk", type="logic"),
            instance("first", "leaf", leaf_body),
            instance("second", "leaf", leaf_body),
        ])
    ]}}


def test_build_index_groups_modules_but_keeps_instances():
    index = build_index(sample_ast(), expected_top="top")
    assert index["schema_version"] == 1
    assert index["counts"] == {"modules": 2, "instances": 3, "signals": 5}
    assert list_modules(index) == ["leaf", "top"]
    leaf = get_module_summary(index, "leaf")
    assert leaf["instance_paths"] == ["top.first", "top.second"]
    assert [x["path"] for x in leaf["instances"]] == ["top.first", "top.second"]
    assert get_instance(index, "top.first")["source"] == {
        "file": "example.sv", "line": 3, "column": 2
    }
    assert get_instance(index, "top.first")["definition_source"]["line"] == 3
    assert get_instance_tree(index)[-1]["parent"] == "top"


def test_port_and_signal_are_distinct_representations():
    index = build_index(sample_ast(), expected_top="top")
    info = get_signal_info(index, "top.first", "out_z")
    assert info["ports"][0]["direction"] == "Out"
    assert info["declarations"][0]["kind"] == "Variable"
    assert info["declarations"][0]["type"] == "logic"
    with pytest.raises(KeyError):
        get_signal_info(index, "top.first", "unknown")
    with pytest.raises(KeyError):
        get_instance(index, "top.unknown")


def test_bad_ast_and_source_metadata_not_guessed():
    with pytest.raises(ValueError):
        build_index(sample_ast(), expected_top="wrong")
    ast = sample_ast()
    del ast["design"]["members"][0]["body"]["members"][0]["source_file"]
    index = build_index(ast, expected_top="top")
    assert get_instance(index, "top")["ports"][0]["source"] is None


def test_source_context_requires_manifest_file_and_bounds(tmp_path):
    d = load_design(ROOT / "examples/counter/design.json")
    got = get_source_context(d.sources, "counter.sv", 7, radius=1)
    assert [x["line"] for x in got["lines"]] == [6, 7, 8]
    with pytest.raises(ValueError):
        get_source_context(d.sources, "README.md", 1)
    with pytest.raises(ValueError):
        get_source_context(d.sources, "counter.sv", 0)
    with pytest.raises(ValueError):
        get_source_context(d.sources, "counter.sv", 10000)
    with pytest.raises(ValueError):
        get_source_context(d.sources, "counter.sv", 1, radius=31)


def test_index_command_clears_stale_results_on_missing_compiler(tmp_path, monkeypatch):
    d = load_design(ROOT / "examples/counter/design.json")
    (tmp_path / "rtl_index.json").write_text('{"fake": true}')
    monkeypatch.setattr(runner.shutil, "which", lambda name: None)
    result = index_design(d, tmp_path, 1)
    assert result["status"] == "missing_tool"
    assert not (tmp_path / "rtl_index.json").exists()
    assert json.loads((tmp_path / "index.result.json").read_text())["status"] == "missing_tool"


def test_cli_query_and_source(tmp_path):
    f = tmp_path / "rtl_index.json"
    f.write_text(json.dumps(build_index(sample_ast(), expected_top="top")))
    out = subprocess.run([sys.executable, "-m", "rtlprep", "query", str(f), "modules"],
                         cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout) == ["leaf", "top"]
    out = subprocess.run([sys.executable, "-m", "rtlprep", "query", str(f),
                          "signal", "top.first", "out_z"],
                         cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout)["ports"][0]["direction"] == "Out"
    out = subprocess.run([sys.executable, "-m", "rtlprep", "source",
                          "examples/counter/design.json", "counter.sv", "--line", "7"],
                         cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert "always_ff" in json.dumps(json.loads(out.stdout))


def test_cli_rejects_index_version(tmp_path):
    f = tmp_path / "old.json"
    f.write_text('{"schema_version": 999}')
    out = subprocess.run([sys.executable, "-m", "rtlprep", "query", str(f), "modules"],
                         cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 2
    assert "non prise en charge" in out.stderr

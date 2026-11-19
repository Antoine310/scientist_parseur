import json
from pathlib import Path

from rtlprep.analysis import summarize_ast
from rtlprep.manifest import load_design
from rtlprep.runner import doctor, fingerprint, run_command

ROOT = Path(__file__).resolve().parents[1]


def test_sample_manifest():
    d = load_design(ROOT / "examples/counter/design.json")
    assert d.top == "counter"
    assert len(d.sources) == 1
    assert len(fingerprint(d)) == 64


def test_ast_summary_fixture():
    obj = {"design": {"kind": "Root", "members": [
        {"kind": "Instance", "name": "counter", "body": {"kind": "InstanceBody", "name": "counter", "members": [
            {"kind": "Port", "name": "clk", "direction": "In", "type": "logic"},
            {"kind": "Port", "name": "count", "direction": "Out", "type": "logic[7:0]"},
        ]}},
    ]}}
    got = summarize_ast(obj)
    assert got["instance_count"] == 1
    assert got["instances"][0]["ports"][1]["name"] == "count"


def test_missing_tool_clearly_reported(tmp_path):
    got = run_command(["missing_eda_tool_zz", "--version"], "test", tmp_path)
    assert got["status"] == "missing_tool"
    assert json.loads((tmp_path / "test.result.json").read_text())["status"] == "missing_tool"


def test_doctor_structure():
    got = doctor()
    assert "slang" in got["tools"]
    assert "cocotb" in got["python_modules"]

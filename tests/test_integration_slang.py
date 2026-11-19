"""Tests d'intégration réels : sautés si l'exécutable slang n'est pas installé."""
import shutil
from pathlib import Path

import pytest

from rtlprep.manifest import load_design
from rtlprep.runner import analyze

pytestmark = pytest.mark.skipif(shutil.which("slang") is None, reason="slang non installé")
ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("example,top,expected_paths", [
    ("counter", "counter", {"counter"}),
    ("hierarchy", "hierarchy_top", {
        "hierarchy_top", "hierarchy_top.first", "hierarchy_top.second"
    }),
])
def test_real_slang_ast(tmp_path, example, top, expected_paths):
    import json

    d = load_design(ROOT / "examples" / example / "design.json")
    result = analyze(d, tmp_path / example, timeout=90)
    assert result["status"] == "passed", result
    summary = json.loads(Path(result["summary"]).read_text(encoding="utf-8"))
    assert summary["top"] == top
    assert expected_paths.issubset({i["hierarchy_path"] for i in summary["instances"]})
    assert summary["instance_count"] >= len(expected_paths)

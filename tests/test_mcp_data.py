"""Sécurité des accès et granularité des résultats MCP, sans SDK ni EDA."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rtlprep.mcp_data import ReadOnlyRtl


def _save(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


@pytest.fixture
def sample(tmp_path):
    source = tmp_path / "known.sv"
    source.write_text("module test_top;\nlogic a;\nendmodule\n", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("private", encoding="utf-8")
    manifest = _save(tmp_path / "design.json", {
        "top": "test_top", "sources": ["known.sv"], "include_dirs": [],
        "defines": [],
    })
    index = _save(tmp_path / "rtl_index.json", {
        "schema_version": 1, "top": "test_top", "modules": [
            {"name": "test_top", "instance_paths": ["test_top"]},
        ],
        "instances": [{
            "name": "test_top", "path": "test_top", "module": "test_top",
            "parent": None,
            "ports": [{"name": "a", "direction": "Out", "type": "logic"}],
        }],
        "signals": [{"instance_path": "test_top", "name": "a",
                     "kind": "Variable", "type": "logic"}],
    })
    graph = _save(tmp_path / "rtl_dependencies.json", {
        "schema_version": 1, "top": "test_top",
        "nodes": ["test_top.a", "test_top.b"],
        "edges": [{
            "source": "test_top.b", "target": "test_top.a",
            "kind": "data", "detail": "sample",
        }],
        "warnings": [{"context": "test_top",
                      "reason": "Selection de bit approximative"}],
    })
    _save(tmp_path / "formal.result.json", {
        "task": "formal", "status": "passed", "proof": {"status": "passed"},
        "secret": "not_exposed",
    })
    return manifest, index, graph, tmp_path


def test_read_only_api_reuses_existing_index_and_graph(sample, monkeypatch):
    manifest, index, graph, root = sample
    snapshot = ReadOnlyRtl(index_file=index, graph_file=graph,
                           manifest_file=manifest, reports_dir=root)
    assert snapshot.capabilities()["runs_eda"] is False
    assert snapshot.capabilities()["edits_files"] is False
    assert snapshot.modules()["items"] == ["test_top"]
    assert snapshot.instances()["total"] == 1
    assert snapshot.module("test_top")["instances"]["total"] == 1
    assert snapshot.instance("test_top")["module"] == "test_top"
    assert snapshot.signal("test_top", "a")["ports"][0]["name"] == "a"
    result = snapshot.trace("test_top.a", "fanin", depth=3, max_edges=1)
    assert result["edges"][0]["source"] == "test_top.b"
    assert result["coverage"] == "partial"
    assert result["graph_warnings_count"] == 1
    assert "graph_warnings" not in result
    assert snapshot.warnings()["total"] == 1
    assert snapshot.source("known.sv", 2, 1)["selected_line"] == 2
    reports = snapshot.validations()
    assert reports["total"] == 1
    assert reports["items"][0]["origin"] == "stored_report_not_reexecuted"
    assert "secret" not in reports["items"][0]["data"]


@pytest.mark.parametrize("name", ["../secret.txt", "/etc/passwd",
                                  "subdir/known.sv", r"foo\\known.sv"])
def test_source_path_traversal_denied(sample, name):
    manifest, index, graph, root = sample
    snapshot = ReadOnlyRtl(index_file=index, manifest_file=manifest)
    with pytest.raises(ValueError):
        snapshot.source(name, 1)


def test_random_filename_not_in_manifest_is_denied(sample):
    manifest, index, graph, root = sample
    snapshot = ReadOnlyRtl(index_file=index, manifest_file=manifest)
    with pytest.raises(ValueError):
        snapshot.source("secret.txt", 1)


def test_limits_and_bad_queries_are_rejected(sample):
    _, index, graph, _ = sample
    api = ReadOnlyRtl(index_file=index, graph_file=graph)
    for limit, offset in ((0, 0), (101, 0), (2, -1), (True, 0)):
        with pytest.raises(ValueError):
            api.modules(limit, offset)
    with pytest.raises(ValueError):
        api.trace("test_top.a", max_edges=101)
    with pytest.raises(ValueError):
        api.trace("test_top.a", depth=7)
    with pytest.raises(ValueError):
        api.trace("test_top.a", direction="sideways")
    with pytest.raises(KeyError):
        api.trace("test_top.unknown")
    with pytest.raises(ValueError):
        api.source("known.sv", 2, 11)


def test_incompatible_tops_or_versions_not_accepted(sample):
    manifest, index, graph, root = sample
    raw = json.loads(graph.read_text())
    raw["top"] = "different"
    graph.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="top"):
        ReadOnlyRtl(index_file=index, graph_file=graph)
    raw["top"] = "test_top"
    raw["schema_version"] = 500
    graph.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="non compatible"):
        ReadOnlyRtl(graph_file=graph)


def test_missing_config_and_oversized_json_denied(sample):
    _, index, graph, root = sample
    with pytest.raises(ValueError, match="Fournir"):
        ReadOnlyRtl()
    index.write_text("x" * (12 * 1024 * 1024 + 1))
    with pytest.raises(ValueError, match="volumineux"):
        ReadOnlyRtl(index_file=index)


def test_signal_search_is_case_insensitive_bounded_and_deduplicated(sample):
    _, index, graph, _ = sample
    api = ReadOnlyRtl(index_file=index, graph_file=graph)
    matches = api.find_signals("TEST_TOP.A")
    assert matches["total"] == 1
    assert matches["items"][0]["name"] == "a"
    assert api.find_signals("does_not_exist")["total"] == 0
    assert api.find_signals("a", limit=1)["next_offset"] is None
    for query in ("", " ", "x" * 81, 5):
        with pytest.raises(ValueError):
            api.find_signals(query)
    with pytest.raises(ValueError):
        api.find_signals("a", limit=1000)


def test_source_fingerprint_detects_stale_rtl_and_prevents_stale_excerpts(sample):
    from rtlprep.runner import fingerprint
    from rtlprep.manifest import load_design

    manifest, index, graph, root = sample
    fp = fingerprint(load_design(manifest))
    for path in (index, graph):
        data = json.loads(path.read_text(encoding="utf-8"))
        data["source_fingerprint"] = fp
        path.write_text(json.dumps(data), encoding="utf-8")
    report = root / "formal.result.json"
    data = json.loads(report.read_text(encoding="utf-8"))
    data["source_fingerprint"] = fp
    report.write_text(json.dumps(data), encoding="utf-8")

    api = ReadOnlyRtl(index_file=index, graph_file=graph,
                      manifest_file=manifest, reports_dir=root)
    assert api.capabilities()["source_snapshot_status"] == "matching"
    assert api.source("known.sv", 2)["source_snapshot_status"] == "matching"
    assert api.validations()["items"][0]["source_relation"] == "matches_current_sources"

    # The server must not present a newly edited file beside stale graph data.
    (root / "known.sv").write_text("module test_top;\nlogic changed;\nendmodule\n",
                                   encoding="utf-8")
    assert api.capabilities()["source_snapshot_status"] == "stale"
    assert api.trace("test_top.a")["source_snapshot_status"] == "stale"
    assert api.validations()["items"][0]["source_relation"] == "stale_current_sources"
    with pytest.raises(ValueError, match="régénérer"):
        api.source("known.sv", 2)


def test_mismatched_index_and_graph_fingerprints_rejected(sample):
    _, index, graph, _ = sample
    idx = json.loads(index.read_text(encoding="utf-8"))
    idx["source_fingerprint"] = "first"
    index.write_text(json.dumps(idx), encoding="utf-8")
    g = json.loads(graph.read_text(encoding="utf-8"))
    g["source_fingerprint"] = "second"
    graph.write_text(json.dumps(g), encoding="utf-8")
    with pytest.raises(ValueError, match="empreintes"):
        ReadOnlyRtl(index_file=index, graph_file=graph)


def test_report_with_other_source_fingerprint_is_flagged(sample):
    _, index, graph, root = sample
    g = json.loads(graph.read_text(encoding="utf-8"))
    g["source_fingerprint"] = "expected"
    graph.write_text(json.dumps(g), encoding="utf-8")
    report = root / "formal.result.json"
    r = json.loads(report.read_text(encoding="utf-8"))
    r["source_fingerprint"] = "different"
    report.write_text(json.dumps(r), encoding="utf-8")
    api = ReadOnlyRtl(index_file=index, graph_file=graph, reports_dir=root)
    assert api.validations()["items"][0]["source_relation"] == "different_artifact"


def test_mcp_server_is_optional_when_dependency_missing(sample):
    # Access to already generated reports never needs the MCP package.
    _, index, _, _ = sample
    api = ReadOnlyRtl(index_file=index)
    assert api.modules()["total"] == 1

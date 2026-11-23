"""PR #25 : provenance des preuves, sans assertion par signal inventée."""
from __future__ import annotations

import json

import pytest

from rtlprep.evidence import build_evidence_view
from rtlprep.manifest import load_design
from rtlprep.mcp_data import ReadOnlyRtl
from rtlprep.runner import fingerprint


def _write(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _fixture(tmp_path):
    source = tmp_path / "unit.sv"
    source.write_text("module unit; logic q, clk; endmodule\n", encoding="utf-8")
    manifest = _write(tmp_path / "design.json", {
        "top": "unit", "sources": ["unit.sv"], "include_dirs": [], "defines": []
    })
    fp = fingerprint(load_design(manifest))
    graph = {
        "schema_version": 1, "top": "unit",
        "source_fingerprint": fp,
        "nodes": ["unit.q", "unit.clk"],
        "edges": [], "warnings": [],
        "expressions": {"schema_version": 1, "items": [
            {"target": "unit.q", "source": {"file": "unit.sv", "line": 1},
             "coverage": "syntax_supported"},
            {"target": "unit.clk",
             "source": {"file": "../secret.sv", "line": 1},
             "coverage": "partial"}
        ]},
        "register_flow": {"schema_version": 1, "items": [
            {"target": "unit.q", "source": {"file": "unit.sv", "line": 1},
             "coverage": "syntactic_paths_supported"},
        ]},
    }
    graph_path = _write(tmp_path / "rtl_dependencies.json", graph)
    return manifest, graph_path, fp, source


def _reports(tmp_path, fp):
    _write(tmp_path / "simulation.result.json", {
        "task": "simulation", "top": "unit", "source_fingerprint": fp,
        "status": "passed", "tests": 3, "passed": 3, "failed": 0, "skipped": 0,
        "secret": "MUST_NOT_LEAK", "argv": ["unexpected"],
    })
    _write(tmp_path / "formal.result.json", {
        "task": "formal", "top": "unit", "source_fingerprint": fp,
        "status": "passed",
        "assumptions": ["reset actif au démarrage"],
        "proof": {"status": "passed", "sby_status": "PASS",
                  "work_dir": "/very/private/path"},
        "cover": {"status": "passed", "sby_status": "PASS"},
    })
    _write(tmp_path / "equivalence.result.json", {
        "task": "equivalence", "status": "passed",
        "top_gold": "unit", "top_gate": "unit_candidate",
        "gold_fingerprint": fp, "gate_fingerprint": "another_snapshot",
        "eqy_verdict": "PASS", "equivalent": True, "partition_count": 3,
        "trace_files": ["/private/trace.vcd"],
    })


def _api(tmp_path, manifest, graph_path):
    return ReadOnlyRtl(graph_file=graph_path, manifest_file=manifest,
                       reports_dir=tmp_path)


def test_linked_provenance_assumptions_simulation_formal_and_eqy(tmp_path):
    manifest, graph, fp, _ = _fixture(tmp_path)
    _reports(tmp_path, fp)
    api = _api(tmp_path, manifest, graph)
    assert api.capabilities()["evidence_available"] is True
    response = api.evidence("unit.q", limit=2)
    assert response["source_snapshot_status"] == "matching"
    assert response["scope"] == "design_snapshot_report_association_only"
    assert response["origin"] == "stored_reports_not_reexecuted"
    assert response["total"] == 3 and response["next_offset"] == 2
    assert response["signal"] == "unit.q"
    assert len(response["rtl_anchors"]) == 2
    assert all(x["source_file"] == "unit.sv" for x in response["rtl_anchors"])
    assert response["hypotheses"] == [{
        "text": "reset actif au démarrage",
        "origin": "formal_report_declared_assumption",
        "relation": "matches_current_sources",
        "status": "reported_not_validated",
    }]
    results = response["items"] + api.evidence("unit.q", limit=2, offset=2)["items"]
    assert [x["kind"] for x in results] == ["simulation", "formal", "equivalence"]
    assert all(x["relation"] == "matches_current_sources" for x in results)
    assert all(x["usable_for_current_snapshot"] for x in results)
    assert results[0]["result"]["test_counts"]["passed"] == 3
    assert results[1]["result"]["tasks"]["proof"]["sby_status"] == "PASS"
    assert results[2]["role"] == "gold"
    assert results[2]["result"]["partition_count"] == 3
    assert all(x["association"] == "design_or_suite_only_not_signal_proof"
               for x in results)
    raw = json.dumps(response, ensure_ascii=False)
    assert "MUST_NOT_LEAK" not in raw
    assert "/very/private/path" not in raw
    assert "/private/trace.vcd" not in raw
    assert "proof_by_signal" not in raw


def test_absent_reports_are_not_fabricated(tmp_path):
    _, graph, _, _ = _fixture(tmp_path)
    api = ReadOnlyRtl(graph_file=graph)
    result = api.evidence()
    assert result["total"] == 3
    assert result["source_snapshot_status"] == "unverifiable"
    assert not result["hypotheses_available"]
    assert result["rtl_anchors"] == []
    assert all(x["available"] is False for x in result["items"])
    assert all(x["relation"] == "no_report" for x in result["items"])


def test_stale_sources_keep_historical_reports_but_block_current_link(tmp_path):
    manifest, graph, fp, source = _fixture(tmp_path)
    _reports(tmp_path, fp)
    api = _api(tmp_path, manifest, graph)
    source.write_text(source.read_text() + "// changed\n", encoding="utf-8")
    result = api.evidence("unit.q")
    assert result["source_snapshot_status"] == "stale"
    assert all(x["relation"] == "stale_current_sources" for x in result["items"])
    assert not any(x["usable_for_current_snapshot"] for x in result["items"])
    assert result["hypotheses"][0]["relation"] == "stale_current_sources"


def test_different_top_and_fingerprint_do_not_prove_anything(tmp_path):
    manifest, graph, fp, _ = _fixture(tmp_path)
    _reports(tmp_path, fp)
    p = tmp_path / "simulation.result.json"
    val = json.loads(p.read_text())
    val["top"] = "other"
    _write(p, val)
    p = tmp_path / "formal.result.json"
    val = json.loads(p.read_text())
    val["source_fingerprint"] = "unrelated"
    _write(p, val)
    p = tmp_path / "equivalence.result.json"
    val = json.loads(p.read_text())
    val["gold_fingerprint"] = "unrelated"
    _write(p, val)
    result = _api(tmp_path, manifest, graph).evidence()
    sim, formal, eqy = result["items"]
    assert sim["relation"] == "different_top"
    assert formal["relation"] == "different_artifact"
    assert eqy["relation"] == "different_design_or_role"
    assert not any(x["usable_for_current_snapshot"] for x in result["items"])
    assert result["hypotheses"][0]["relation"] == "different_artifact"


@pytest.mark.parametrize("changes", [
    {"simulation": {"status": "passed", "tests": 2, "passed": 1,
                    "failed": 0, "skipped": 0}},
    {"formal": {"status": "passed",
                "proof": {"status": "passed", "sby_status": "UNKNOWN"},
                "cover": {"status": "passed", "sby_status": "PASS"}}},
    {"equivalence": {"status": "passed", "equivalent": True,
                     "eqy_verdict": "FAIL", "partition_count": 3}},
])
def test_inconsistent_or_inconclusive_reports_never_gain_verdict(tmp_path, changes):
    manifest, graph, fp, _ = _fixture(tmp_path)
    _reports(tmp_path, fp)
    for kind, override in changes.items():
        p = tmp_path / (kind + ".result.json")
        original = json.loads(p.read_text())
        original.update(override)
        _write(p, original)
    response = _api(tmp_path, manifest, graph).evidence()
    affected = next(x for x in response["items"] if x["kind"] in changes)
    assert affected["relation"] == "matches_current_sources"
    assert affected["result"]["result_criteria_met"] is False
    assert affected["usable_for_current_snapshot"] is False


def test_old_missing_fingerprints_do_not_associate_based_on_top_only(tmp_path):
    manifest, graph, fp, _ = _fixture(tmp_path)
    _reports(tmp_path, fp)
    p = tmp_path / "formal.result.json"
    original = json.loads(p.read_text())
    del original["source_fingerprint"]
    _write(p, original)
    result = _api(tmp_path, manifest, graph).evidence()
    formal = result["items"][1]
    assert formal["relation"] == "unverifiable"
    assert formal["usable_for_current_snapshot"] is False


def test_without_manifest_the_link_is_snapshot_only_not_current_sources(tmp_path):
    _, graph, fp, _ = _fixture(tmp_path)
    _reports(tmp_path, fp)
    result = ReadOnlyRtl(graph_file=graph, reports_dir=tmp_path).evidence("unit.q")
    assert result["source_snapshot_status"] == "unverifiable"
    assert all(x["relation"] == "matches_artifacts_only" for x in result["items"])
    assert not any(x["usable_for_current_snapshot"] for x in result["items"])


def test_unknown_signal_and_bounds_fail_closed(tmp_path):
    manifest, graph, fp, _ = _fixture(tmp_path)
    _reports(tmp_path, fp)
    api = _api(tmp_path, manifest, graph)
    for name in ("unit.missing", "../escape"):
        with pytest.raises(KeyError):
            api.evidence(name)
    with pytest.raises(ValueError):
        api.evidence("")
    for limit, offset in ((0, 0), (101, 0), (1, -1), (True, 0)):
        with pytest.raises(ValueError):
            api.evidence("unit.q", limit=limit, offset=offset)
    assert api.evidence("unit.clk")["rtl_anchors"] == []


def test_assumptions_are_bounded_without_other_report_fields(tmp_path):
    manifest, graph, fp, _ = _fixture(tmp_path)
    _reports(tmp_path, fp)
    p = tmp_path / "formal.result.json"
    r = json.loads(p.read_text())
    r["assumptions"] = ["A" * 500] * 100 + ["SHOULD_NOT_APPEAR"]
    _write(p, r)
    result = _api(tmp_path, manifest, graph).evidence()
    assert len(result["hypotheses"]) == 16
    assert all(len(x["text"]) <= 160 for x in result["hypotheses"])
    assert "SHOULD_NOT_APPEAR" not in json.dumps(result)


def test_graph_required_and_bad_schema_fail_closed():
    with pytest.raises(ValueError, match="Graphe"):
        build_evidence_view(
            {"schema_version": 2}, {}, signal=None,
            artifact_fingerprint=None, source_snapshot_status="unverifiable"
        )

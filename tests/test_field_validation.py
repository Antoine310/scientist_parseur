"""Contrats de validation des RTL externes ; aucun téléchargement/EDA en unit tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rtlprep import field_validation as validation


def _case():
    return {
        "id": "new_block", "top": "other_top",
        "upstream": {
            "repository": "somewhere/project",
            "commit": "a" * 40, "checkout": "project",
        },
        "sources": [{"path": "rtl/new.v", "git_blob_sha1": "b" * 40}],
        "include_dirs": [], "defines": [],
        "probes": [{"id": "output", "signal": "other_top.out", "direction": "fanin"}],
    }


def _dataset():
    return {"schema_version": 1, "cases": [_case()]}


def _source(tmp_path):
    root = tmp_path / "external"
    path = root / "project" / "rtl" / "new.v"
    path.parent.mkdir(parents=True)
    source = b"module other_top (input wire in, output wire out); assign out = in; endmodule\n"
    path.write_bytes(source)
    case = _case()
    case["sources"][0]["git_blob_sha1"] = validation.git_blob_sha1(source)
    return root, path, case


def _artifacts(out: Path, manifest: Path):
    from rtlprep.manifest import load_design
    from rtlprep.runner import fingerprint

    fp = fingerprint(load_design(manifest))
    index = {
        "schema_version": 1, "top": "other_top", "source_fingerprint": fp,
        "instances": [{"path": "other_top"}],
        "counts": {"modules": 1, "instances": 1, "signals": 2},
    }
    analyzer = lambda: {
        "assessment": "no_reported_limits_within_scope", "captured": 1,
        "observed_status_counts": {"syntax_supported": 1},
        "excluded_from_records": {}, "truncated": False,
    }
    graph = {
        "schema_version": 1, "top": "other_top", "source_fingerprint": fp,
        "nodes": ["other_top.in", "other_top.out"],
        "edges": [{
            "source": "other_top.in", "target": "other_top.out", "kind": "data"
        }],
        "warnings": [],
        "counts": {"nodes": 2, "edges": 1, "warnings": 0},
        "coverage": {
            "schema_version": 1, "scope": "observed_analyzer_records_only",
            "design_coverage": "not_measured",
            "assessment": "no_reported_limits_within_scopes",
            "findings_total": 0,
            "analyzers": {
                "dependencies": analyzer(), "expressions": analyzer(),
                "register_flow": analyzer(), "bit_accesses": analyzer(),
            },
        },
    }
    (out / "rtl_index.json").write_text(json.dumps(index))
    (out / "rtl_dependencies.json").write_text(json.dumps(graph))
    return index, graph


def test_git_blob_hash_is_not_plain_sha1():
    raw = b"some SystemVerilog"
    assert validation.git_blob_sha1(raw) != __import__("hashlib").sha1(raw).hexdigest()


def test_suite_validation_rejects_bogus_provenance_and_duplicates():
    doc = _dataset()
    assert validation.validate_suite(doc)[0]["id"] == "new_block"
    doc["cases"].append(_case())
    with pytest.raises(validation.ValidationError, match="dupliqué"):
        validation.validate_suite(doc)
    doc = _dataset()
    doc["cases"][0]["upstream"]["commit"] = "main"
    with pytest.raises(validation.ValidationError, match="commit"):
        validation.validate_suite(doc)
    doc = _dataset()
    doc["cases"][0]["probes"][0]["signal"] = "other_top.*"
    with pytest.raises(validation.ValidationError, match="cible"):
        validation.validate_suite(doc)


def test_sources_are_verified_by_pinned_git_blob_not_file_presence(tmp_path):
    root, source, case = _source(tmp_path)
    evidence = validation.verify_sources(case, root)
    assert evidence["sources"] == [source]
    assert len(evidence["hashes"][0]["sha256"]) == 64
    source.write_text("module changed; endmodule\n")
    with pytest.raises(validation.ValidationError, match="différente"):
        validation.verify_sources(case, root)


def test_source_symlinks_cannot_escape_external_checkout(tmp_path):
    root, source, case = _source(tmp_path)
    outside = tmp_path / "secret"
    outside.write_text("secrets")
    source.unlink()
    source.symlink_to(outside)
    with pytest.raises(validation.ValidationError, match="hors de la racine"):
        validation.verify_sources(case, root)


def test_valid_snapshot_has_bounded_probes_and_does_not_claim_full_coverage(tmp_path):
    root, _, case = _source(tmp_path)
    out = tmp_path / "report"
    out.mkdir()
    manifest = out / "design.json"
    manifest.write_text(json.dumps({
        "top": "other_top", "sources": [str(root / "project/rtl/new.v")],
        "include_dirs": [], "defines": []
    }))
    index, graph = _artifacts(out, manifest)
    report = validation.audit_snapshot(
        index, graph, top="other_top", expected_fingerprint=index["source_fingerprint"],
        probes=case["probes"],
    )
    assert report["status"] == "observed_within_reported_scope"
    assert report["all_probes_present"] is True
    assert report["design_coverage"] == "not_measured"
    assert report["probes"][0]["budgets"] == [
        {"max_edges": b, "returned_edges": 1, "visited_nodes": 2, "truncated": False}
        for b in validation.QUERY_BUDGETS
    ]


def test_warnings_and_small_trace_budget_mark_limited_observation(tmp_path):
    root, _, case = _source(tmp_path)
    out = tmp_path / "report"
    out.mkdir()
    manifest = out / "design.json"
    manifest.write_text(json.dumps({
        "top": "other_top", "sources": [str(root / "project/rtl/new.v")],
        "include_dirs": [], "defines": [],
    }))
    index, graph = _artifacts(out, manifest)
    graph["warnings"].append({"context": "other_top", "reason": "unsupported"})
    graph["coverage"]["analyzers"]["expressions"]["assessment"] = "reported_limits"
    report = validation.audit_snapshot(
        index, graph, top="other_top", expected_fingerprint=index["source_fingerprint"],
        probes=case["probes"],
    )
    assert report["status"] == "observed_with_reported_limits"
    assert report["warnings_total"] == 1
    graph["warnings"] = []
    graph["coverage"]["analyzers"]["expressions"]["assessment"] = "no_reported_limits_within_scope"
    graph["nodes"] += ["other_top.a", "other_top.b", "other_top.c",
                       "other_top.d", "other_top.e", "other_top.f"]
    graph["edges"] += [
        {"source": f"other_top.{x}", "target": "other_top.out", "kind": "data"}
        for x in "abcdef"
    ]
    report = validation.audit_snapshot(
        index, graph, top="other_top", expected_fingerprint=index["source_fingerprint"],
        probes=case["probes"],
    )
    assert report["probes"][0]["budgets"][0]["truncated"] is True
    assert report["probes"][0]["budgets"][-1]["truncated"] is False
    assert report["status"] == "observed_with_reported_limits"


def test_incompatible_top_and_fingerprint_fail_even_if_records_exist(tmp_path):
    root, _, case = _source(tmp_path)
    out = tmp_path / "report"
    out.mkdir()
    manifest = out / "design.json"
    manifest.write_text(json.dumps({
        "top": "other_top", "sources": [str(root / "project/rtl/new.v")],
    }))
    index, graph = _artifacts(out, manifest)
    for target in ("wrong_top", "wrong_fingerprint"):
        broken = dict(index)
        broken["top" if target == "wrong_top" else "source_fingerprint"] = "wrong"
        with pytest.raises(validation.ValidationError, match="snapshot"):
            validation.audit_snapshot(
                broken, graph, top="other_top",
                expected_fingerprint=index["source_fingerprint"], probes=case["probes"],
            )


def test_no_fake_success_if_eda_is_missing(tmp_path, monkeypatch):
    root, _, case = _source(tmp_path)
    def fake_eda(*args, **kwargs):
        return {"status": "missing_tool", "error": "slang absent"}
    monkeypatch.setattr(validation, "dependency_design", fake_eda)
    result = validation.evaluate_case(
        case, sources_root=root, output=tmp_path / "reports",
    )
    assert result["execution"] == "missing_tool"
    assert result["status"] == "eda_or_analysis_failed"
    assert result["source_integrity"] == "verified_pinned_git_blobs"
    assert result["functional_correctness"] == "not_tested"
    assert (tmp_path / "reports/new_block/validation.case.json").exists()


def test_real_case_runner_interface_with_mocked_eda(tmp_path, monkeypatch):
    root, _, case = _source(tmp_path)
    def fake_eda(d, out, timeout):
        _artifacts(out, d.manifest)
        return {"status": "passed"}
    monkeypatch.setattr(validation, "dependency_design", fake_eda)
    report = validation.run_suite(
        {"schema_version": 1, "cases": [case]},
        sources_root=root, output=tmp_path / "reports",
    )
    assert report["all_elaborated"] is True
    assert report["all_probes_present"] is True
    assert report["failed_cases"] == 0
    assert report["cases"][0]["audit"]["design_coverage"] == "not_measured"
    assert report["benchmarked_llm"] is False
    assert report["accuracy"] == "not_measured_without_independent_exhaustive_oracle"
    assert (tmp_path / "reports/unknown_validation_report.json").exists()


def test_report_denies_overlapping_output_and_unknown_selection(tmp_path):
    root, _, case = _source(tmp_path)
    suite = {"schema_version": 1, "cases": [case]}
    with pytest.raises(validation.ValidationError, match="séparée"):
        validation.run_suite(
            suite, sources_root=root, output=root / "reports",
        )
    with pytest.raises(validation.ValidationError, match="inconnue"):
        validation.run_suite(
            suite, sources_root=root, output=tmp_path / "reports",
            selected={"not_in_corpus"},
        )


def test_missing_probe_is_recorded_not_silently_fabricated(tmp_path):
    root, _, case = _source(tmp_path)
    out = tmp_path / "report"
    out.mkdir()
    manifest = out / "design.json"
    manifest.write_text(json.dumps({
        "top": "other_top", "sources": [str(root / "project/rtl/new.v")],
    }))
    index, graph = _artifacts(out, manifest)
    report = validation.audit_snapshot(
        index, graph, top="other_top", expected_fingerprint=index["source_fingerprint"],
        probes=[{"id": "notfound", "signal": "other_top.unknown", "direction": "fanin"}],
    )
    assert report["all_probes_present"] is False
    assert report["status"] == "observed_with_reported_limits"
    assert report["probes"][0]["status"] == "missing_target"


def test_current_pinned_external_corpus_contains_new_unseen_repositories():
    path = Path(__file__).resolve().parents[1] / "benchmarks/unknown_designs_v1.json"
    doc = json.loads(path.read_text())
    cases = validation.validate_suite(doc)
    assert len(cases) == 3
    assert len({x["upstream"]["repository"] for x in cases}) == 2
    assert all(x["top"] in x["probes"][0]["signal"] for x in cases)

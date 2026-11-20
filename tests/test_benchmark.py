"""Benchmark unit tests: do not invent LLM accuracy or EDA success."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rtlprep import benchmark
from rtlprep.manifest import load_design
from rtlprep.runner import fingerprint


ROOT = Path(__file__).resolve().parents[1]


def test_labelled_metrics_are_scoped_to_manual_subset_not_entire_graph():
    graph = {"edges": [
        {"source": "a", "target": "b", "kind": "data"},
        {"source": "x", "target": "y", "kind": "control"},
        {"source": "a", "target": "d", "kind": "event"},
    ], "warnings": [{"context": "top", "reason": "partielle"}]}
    labels = [["a", "b", "data"], ["c", "d", "data"]]
    negatives = [["x", "y", "control"], ["c", "b", "event"]]
    m = benchmark.labelled_edge_scores(graph, labels, negatives)
    assert (m["tp"], m["fn"], m["fp"], m["tn"]) == (1, 1, 1, 1)
    assert m["precision_on_labels"] == .5
    assert m["recall_on_labels"] == .5
    assert m["specificity_on_labels"] == .5
    assert m["unlabelled_edges"] == 1
    assert m["warning_count"] == 1
    assert m["missing_positive"] == [["c", "d", "data"]]
    assert m["unexpected_negative"] == [["x", "y", "control"]]


def test_invalid_labels_cannot_claim_perfect_precision():
    g = {"edges": []}
    for pos, neg in (([], [["a", "b", "data"]]),
                     ([["a", "b", "data"]], []),
                     ([["a", "b", "data"]], [["a", "b", "data"]]),
                     ([["a", "b"]], [["x", "y", "data"]])):
        with pytest.raises(ValueError):
            benchmark.labelled_edge_scores(g, pos, neg)


def test_json_utf8_bytes_and_approximate_word_metric_are_explicit():
    x = {"alpha": "école", "text": "x y"}
    assert benchmark.compact_bytes(x) == len(json.dumps(
        x, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8"))
    assert benchmark.whitespace_words(x) >= 2


def test_payloads_compare_same_question_and_include_warning_caveat():
    d = load_design(ROOT / "examples/counter/design.json")
    idx = {"instances": [{
        "name": "counter", "path": "counter", "parent": None,
        "module": "counter",
        "ports": [{"name": "count", "direction": "Out", "type": "logic",
                   "source": {"file": str(d.sources[0]), "line": 5}}]
    }], "signals": []}
    graph = {"schema_version": 1,
             "nodes": ["counter.count", "counter.enable"],
             "edges": [{"source": "counter.enable", "target": "counter.count",
                        "kind": "control", "detail": "", "sequential": True,
                        "location": None}],
             "warnings": [{"context": "counter", "reason": "approximation"}]}
    q = {"id": "count", "question": "Qui pilote le compteur ?",
         "target": "counter.count", "expected_reachable": ["counter.enable"]}
    result = benchmark.context_sizes(d, idx, graph, q)
    assert result["expected_reachable"] == ["counter.enable"]
    assert result["found_reachable"] == ["counter.enable"]
    assert result["missing_reachable"] == []
    assert result["trace_edges"] == 1
    assert result["trace_truncated"] is False
    assert result["source_excerpt_available"] is True
    assert all(result["payload_bytes"][k] > 0
               for k in ("A_raw", "B_index", "C_hybrid"))
    assert "tokens" in result["interpretation"]


def test_context_source_excerpt_does_not_fake_missing_provenance():
    d = load_design(ROOT / "examples/counter/design.json")
    idx = {"instances": [{
        "name": "counter", "path": "counter", "parent": None, "module": "counter",
        "ports": [{"name": "count", "direction": "Out", "source": None}],
    }], "signals": []}
    graph = {"schema_version": 1, "nodes": ["counter.count"],
             "edges": [], "warnings": []}
    result = benchmark.context_sizes(d, idx, graph, {
        "id": "count", "question": "compteur ?", "target": "counter.count"
    })
    assert result["source_excerpt_available"] is False


def test_real_slang_status_is_required_and_never_imitated(tmp_path, monkeypatch):
    d = load_design(ROOT / "examples/counter/design.json")
    def fail(*args, **kwargs):
        return {"status": "missing_tool", "error": "slang absent"}
    monkeypatch.setattr(benchmark, "dependency_design", fail)
    with pytest.raises(RuntimeError, match="missing_tool"):
        benchmark.evaluate_case(d, tmp_path, name="counter", labels=None, repeat=1)


def test_repeat_must_be_bounded_before_execution(tmp_path):
    d = load_design(ROOT / "examples/counter/design.json")
    for value in (0, 9, -1, True):
        with pytest.raises(ValueError):
            benchmark.evaluate_case(d, tmp_path, name="counter",
                                    labels=None, repeat=value)


def test_non_deterministic_dependency_edges_are_not_silently_averaged(
        tmp_path, monkeypatch):
    d = load_design(ROOT / "examples/counter/design.json")
    count = 0
    def fake_runner(design, output, timeout):
        nonlocal count
        count += 1
        output.mkdir(parents=True, exist_ok=True)
        idx = {"top": design.top, "source_fingerprint": fingerprint(design),
               "counts": {"modules": 1, "instances": 1, "signals": 0}}
        graph = {"top": design.top, "source_fingerprint": fingerprint(design),
                 "counts": {"nodes": 2, "edges": 1, "warnings": 0},
                 "edges": [{"source": "counter.x" if count == 1 else "counter.y",
                            "target": "counter.count", "kind": "data"}]}
        (output / "rtl_index.json").write_text(json.dumps(idx))
        (output / "rtl_dependencies.json").write_text(json.dumps(graph))
        return {"status": "passed"}
    monkeypatch.setattr(benchmark, "dependency_design", fake_runner)
    with pytest.raises(AssertionError, match="diffère"):
        benchmark.evaluate_case(d, tmp_path, name="counter", labels=None, repeat=2)


def test_label_dataset_is_valid_and_explicitly_limited():
    f = ROOT / "benchmarks/rtl_questions_v1.json"
    doc = json.loads(f.read_text(encoding="utf-8"))
    assert doc["schema_version"] == 1
    assert len(doc["cases"]) == 4
    labels = sum(len(c["positive"]) for c in doc["cases"])
    negatives = sum(len(c["negative"]) for c in doc["cases"])
    assert (labels, negatives) == (35, 16)
    assert sum(len(c["questions"]) for c in doc["cases"]) == 7
    for c in doc["cases"]:
        benchmark.labelled_edge_scores({"edges": []}, c["positive"], c["negative"])

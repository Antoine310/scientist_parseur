"""PR #23 : rapport de couverture observée, exclusions et limites.

Ces tests ne déclenchent ni slang ni EDA ; le pourcentage de RTL couvert
n'est déduit d'aucun nombre d'enregistrements.
"""
import copy
import json

import pytest

from rtlprep.coverage import MAX_FINDINGS, build_coverage_summary
from rtlprep.dependencies import build_dependency_graph
from rtlprep.mcp_data import ReadOnlyRtl


def node(kind, **fields):
    return {"kind": kind, **fields}


def ref(name):
    return node("NamedValue", symbol="123 " + name)


def literal(value):
    return node("IntegerLiteral", value=str(value))


def synthetic_graph(rhs=None):
    if rhs is None:
        rhs = ref("input_a")
    ast = {"design": node("Root", members=[
        node("Instance", name="top", body=node("InstanceBody",
            name="top", members=[
                node("Variable", name="input_a", type="logic"),
                node("Variable", name="idx", type="logic"),
                node("Variable", name="result", type="logic"),
                node("ContinuousAssign", assignment=node("Assignment",
                    left=ref("result"), right=rhs, isNonBlocking=False)),
            ]))
    ])}
    return build_dependency_graph(ast, expected_top="top")


def test_report_shows_analyzer_scopes_without_invented_design_percentage():
    graph = synthetic_graph()
    report = graph["coverage"]
    assert report == build_coverage_summary(graph)
    assert report["schema_version"] == 1
    assert report["scope"] == "observed_analyzer_records_only"
    assert report["assessment"] == "no_reported_limits_within_scopes"
    assert report["design_coverage"] == "not_measured"
    assert report["findings_total"] == 0
    assert report["analyzers"]["dependencies"]["edges"] == 1
    assert report["analyzers"]["expressions"]["observed_status_counts"] == {
        "syntax_supported": 1, "partial": 0, "unknown": 0
    }
    assert report["analyzers"]["register_flow"]["assessment"] == "no_observed_records"
    assert report["analyzers"]["bit_accesses"]["assessment"] == "no_observed_records"
    assert all(item["design_coverage"] == "not_measured"
               for item in report["analyzers"].values())
    assert "percentage" not in json.dumps(report)


def test_dynamic_bit_index_is_partial_and_findings_are_explicit():
    graph = synthetic_graph(node("ElementSelect", value=ref("input_a"),
                                 selector=ref("idx")))
    report = graph["coverage"]
    assert report["assessment"] == "reported_limits"
    assert report["analyzers"]["dependencies"]["warnings"] >= 1
    bit = report["analyzers"]["bit_accesses"]
    assert bit["captured"] == 1
    assert bit["observed_status_counts"]["partial"] == 1
    assert any(item["analyzer"] == "bit_accesses"
               and item.get("target") == "top.result"
               and item["reason"] == "dynamic_or_unknown_index"
               for item in report["findings"])


def test_skipped_records_and_truncation_do_not_hide_as_supported():
    graph = synthetic_graph()
    graph["expressions"]["counts"]["unsupported_targets"] = 3
    graph["expressions"]["counts"]["truncated"] = True
    graph["register_flow"]["counts"]["partial_processes"] = 2
    report = build_coverage_summary(graph)
    assert report["assessment"] == "reported_limits"
    assert report["analyzers"]["expressions"]["excluded_from_records"][
        "unsupported_targets"
    ] == 3
    assert report["analyzers"]["expressions"]["truncated"] is True
    assert any(x["reason"] == "analysis_truncated" for x in report["findings"])
    assert any(x["reason"] == "partial_processes" and x["count"] == 2
               for x in report["findings"])


def test_unknown_record_state_is_reported_not_counted_as_supported():
    graph = synthetic_graph()
    graph["expressions"]["items"][0]["coverage"] = "future_state"
    report = build_coverage_summary(graph)
    observed = report["analyzers"]["expressions"]["observed_status_counts"]
    assert observed["syntax_supported"] == 0
    assert observed["unknown"] == 1
    assert report["assessment"] == "reported_limits"
    assert any(x["reason"] == "unknown_coverage_status" for x in report["findings"])


def test_findings_bounded_but_global_count_preserved():
    graph = synthetic_graph()
    graph["warnings"] = [
        {"context": "top", "reason": "r" * 1000}
        for _ in range(MAX_FINDINGS + 7)
    ]
    report = build_coverage_summary(graph)
    assert len(report["findings"]) == MAX_FINDINGS
    assert report["findings_total"] == MAX_FINDINGS + 7
    assert report["findings_truncated"] is True
    assert all(len(x["reason"]) <= 160 for x in report["findings"])


@pytest.mark.parametrize("change", [
    lambda g: g["expressions"]["counts"].update(captured=900),
    lambda g: g["expressions"]["counts"].update(unsupported_targets=-1),
    lambda g: g["bit_accesses"]["counts"].update(truncated="false"),
    lambda g: g.pop("register_flow"),
])
def test_malformed_accounting_fails_closed(change):
    graph = synthetic_graph()
    change(graph)
    with pytest.raises(ValueError):
        build_coverage_summary(graph)


def test_mcp_coverage_is_paged_exact_filtered_and_legacy_safe(tmp_path):
    graph = synthetic_graph(node("ElementSelect", value=ref("input_a"),
                                 selector=ref("idx")))
    path = tmp_path / "rtl_dependencies.json"
    path.write_text(json.dumps(graph), encoding="utf-8")
    api = ReadOnlyRtl(graph_file=path)
    assert api.capabilities()["coverage_available"] is True
    global_page = api.coverage(limit=1)
    assert global_page["total"] >= 1
    assert global_page["global_findings_total"] >= global_page["total"]
    assert global_page["design_coverage"] == "not_measured"
    assert global_page["source_snapshot_status"] == "unverifiable"
    scoped = api.coverage("top.result")
    assert scoped["finding_filter"] == "exact_target_only"
    assert scoped["total"] >= 1
    assert all(x["target"] == "top.result" for x in scoped["items"])
    assert api.coverage("top.idx")["total"] == 0
    # Zero constatations pour un signal ne vaut jamais une analyse exhaustive.
    assert api.coverage("top.idx")["design_coverage"] == "not_measured"
    for limit, offset in ((0, 0), (101, 0), (1, -1), (True, 0)):
        with pytest.raises(ValueError):
            api.coverage(limit=limit, offset=offset)
    with pytest.raises(KeyError):
        api.coverage("../private")
    with pytest.raises(ValueError):
        api.coverage("")

    old = copy.deepcopy(graph)
    del old["coverage"]
    path.write_text(json.dumps(old), encoding="utf-8")
    legacy = ReadOnlyRtl(graph_file=path)
    assert legacy.capabilities()["coverage_available"] is False
    with pytest.raises(ValueError, match="régénérer"):
        legacy.coverage()

import copy
import pytest
from rtlprep.analysis_budgets import AnalysisBudget, analyzer_summary
from rtlprep import expressions, complex_constructs
from rtlprep.dependencies import build_dependency_graph
from rtlprep.index import build_index
from rtlprep.row_budgets import effective_row_limit
from scripts.run_analyzer_row_budgets_pr68 import compare_graphs
from test_cv32e40p_diagnostics_pr67 import ast_fixture

@pytest.mark.parametrize("value",[0,-1,8193,True,False,1.5,"4096"])
def test_invalid_row_policy(value):
    with pytest.raises(ValueError,match="row limit"):
        AnalysisBudget(expression_rows=value)
    with pytest.raises(ValueError,match="row limit"):
        AnalysisBudget(complex_rows=value)

@pytest.mark.parametrize("value",[1,2000,4096,8192])
def test_valid_row_policy(value):
    b=AnalysisBudget(expression_rows=value,complex_rows=value)
    assert b.expression_rows==b.complex_rows==value
    assert effective_row_limit(value,4096)==value

def graphs():
    ast=ast_fixture()
    idx=build_index(ast,expected_top="top")
    legacy=build_dependency_graph(ast,expected_top="top",index=idx,
                                  budget=AnalysisBudget(expression_rows=1,complex_rows=1))
    expanded=build_dependency_graph(ast,expected_top="top",index=idx,
                                    budget=AnalysisBudget(expression_rows=4,complex_rows=4))
    return legacy,expanded

def test_default_limits():
    ast=ast_fixture()
    g=build_dependency_graph(ast,expected_top="top")
    assert g["expressions"]["row_limit"]==4096
    assert g["complex_constructs"]["row_limit"]==4096
    assert g["analysis_limits"]["analyzers"]["complex_constructs"]["configured_limits"]["MAX_NODES"]==50000

def test_effective_limits_are_reported():
    a,b=graphs()
    for graph,limit in ((a,1),(b,4)):
        r=graph["analysis_limits"]["analyzers"]
        assert r["expressions"]["configured_limits"]["MAX_EXPRESSIONS"]==limit
        assert r["complex_constructs"]["configured_limits"]["MAX_ROWS"]==limit
        assert graph["expressions"]["row_limit"]==graph["complex_constructs"]["row_limit"]==limit
        assert analyzer_summary(graph)["analyzers"]==r

def test_recovery_without_semantic_changes():
    a,b=graphs()
    delta=compare_graphs(a,b)
    assert delta["expressions"]["added_rows"]==1
    assert delta["complex_constructs"]["added_rows"]==1
    assert a["analysis_limits"]["truncated_analyzers"]==["expressions","complex_constructs"]
    assert b["analysis_limits"]["truncated_analyzers"]==[]
    assert b["expressions"]["truncation_events"]["row_cap_hits"]==0
    assert not b["complex_constructs"]["truncation_events"]["hits"]
    assert a["bit_dependency_graph"]==b["bit_dependency_graph"]

def test_independent_policies():
    ast=ast_fixture()
    g=build_dependency_graph(ast,expected_top="top",
                             budget=AnalysisBudget(expression_rows=1,complex_rows=4))
    assert g["analysis_limits"]["truncated_analyzers"]==["expressions"]
    assert expressions.MAX_EXPRESSIONS==complex_constructs.MAX_ROWS==4096

def test_direct_builders_validate_before_traversal():
    with pytest.raises(ValueError,match="row limit"):
        expressions.build_expression_index({},expected_top="top",row_limit=True)
    with pytest.raises(ValueError,match="row limit"):
        complex_constructs.build_complex_construct_index({},index={},row_limit=8193)

def test_report_rejects_inconsistent_limit():
    _,g=graphs()
    g["expressions"]["row_limit"]=1
    with pytest.raises(ValueError,match="captured rows exceed"):
        analyzer_summary(g)

def test_report_rejects_null_effective_limit():
    _,g=graphs()
    g["complex_constructs"]["row_limit"]=None
    with pytest.raises(ValueError,match="missing effective row"):
        analyzer_summary(g)

def test_duplicate_rows_not_lost():
    a,b=graphs()
    # Deliberately duplicate a captured row; multiset comparison must notice.
    a["expressions"]["items"].append(copy.deepcopy(a["expressions"]["items"][0]))
    with pytest.raises(ValueError,match="previous rows lost"):
        compare_graphs(a,b)

def test_reject_changed_signal_graph():
    a,b=graphs()
    b["edges"].pop()
    with pytest.raises(ValueError,match="non-target graph changed"):
        compare_graphs(a,b)

def test_reject_changed_old_row():
    a,b=graphs()
    b["expressions"]["items"][0]["coverage"]="invented"
    with pytest.raises(ValueError,match="previous rows lost"):
        compare_graphs(a,b)

def test_reject_reordered_constructs():
    a,b=graphs()
    b["complex_constructs"]["items"].reverse()
    with pytest.raises(ValueError,match="traversal order changed"):
        compare_graphs(a,b)

def test_node_cap_still_active(monkeypatch):
    ast=ast_fixture()
    idx=build_index(ast,expected_top="top")
    monkeypatch.setattr(complex_constructs,"MAX_NODES",4)
    r=complex_constructs.build_complex_construct_index(ast,index=idx,row_limit=8192)
    assert r["counts"]["truncated"]
    assert r["truncation_events"]["hits"]["list_queue_cap"]>=1
    assert "row_cap" not in r["truncation_events"]["hits"]

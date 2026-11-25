import copy
import json
import pytest

from rtlprep.analysis_budgets import (
    ANALYZERS, AnalysisBudget, AnalysisBudgetError, DEFAULT_BUDGET,
    analyzer_summary, build_analysis_limits, inspect_ast, measure_tree, read_ast,
)
from rtlprep.dependencies import build_dependency_graph

def empty_graph():
    graph={"warnings":[],"coverage":{"findings_truncated":False}}
    for name,(_,counter,_) in ANALYZERS.items():
        graph[name]={"schema_version":1,"scope":"test","items":[],
                     "counts":{counter:0,"truncated":False}}
    return graph

def row(graph,name,**fields):
    data=graph[name]
    data["items"].append(fields)
    data["counts"][ANALYZERS[name][1]]+=1

def test_count_json_values():
    assert measure_tree({"a":[1,{"b":2}],"c":None},stage="test",max_values=6,max_depth=3)=={
        "json_values":6,"json_depth":3}

def test_exact_boundary():
    assert inspect_ast([1,2],AnalysisBudget(max_ast_values=3,max_ast_depth=1))=={
        "json_values":3,"json_depth":1}

def test_value_limit():
    with pytest.raises(AnalysisBudgetError) as e:
        inspect_ast([1,2,3],AnalysisBudget(max_ast_values=3))
    assert e.value.details=={"stage":"ast_admission","metric":"json_values",
                             "limit":3,"observed_at_least":4}

def test_depth_limit():
    with pytest.raises(AnalysisBudgetError) as e:
        inspect_ast([[[0]]],AnalysisBudget(max_ast_depth=2))
    assert e.value.details["metric"]=="json_depth"
    assert e.value.details["observed_at_least"]==3

def test_cycle_rejected_by_depth():
    a=[]
    a.append(a)
    with pytest.raises(AnalysisBudgetError,match="json_depth"):
        inspect_ast(a,AnalysisBudget(max_ast_depth=3))

@pytest.mark.parametrize("kwargs",[
    {"max_ast_bytes":0},{"max_ast_values":True},{"max_ast_depth":257},
    {"max_graph_values":-1},{"max_graph_depth":1.5},
])
def test_invalid_budget(kwargs):
    with pytest.raises(ValueError):
        AnalysisBudget(**kwargs)

def test_file_size_before_decode(tmp_path):
    p=tmp_path/"ast.json"
    p.write_bytes(b"not JSON")
    with pytest.raises(AnalysisBudgetError) as e:
        read_ast(p,AnalysisBudget(max_ast_bytes=3))
    assert e.value.details["metric"]=="file_bytes"

def test_read_valid_ast(tmp_path):
    p=tmp_path/"ast.json"
    p.write_text(json.dumps({"x":[1,2]}))
    assert read_ast(p)=={"x":[1,2]}

def test_read_applies_tree_gate(tmp_path):
    p=tmp_path/"ast.json"
    p.write_text("[1,2,3]")
    with pytest.raises(AnalysisBudgetError,match="json_values"):
        read_ast(p,AnalysisBudget(max_ast_values=3))

def test_graph_admission_precedes_index():
    with pytest.raises(AnalysisBudgetError,match="ast_admission"):
        build_dependency_graph({"a":[1,2]},expected_top="u",budget=AnalysisBudget(max_ast_values=1))

def test_all_analyzers_reported_without_claiming_coverage():
    g=empty_graph()
    result=build_analysis_limits(g,{"json_values":1,"json_depth":0})
    assert len(result["analyzers"])==10
    assert result["assessment"]=="no_reported_limits_within_observed_scopes"
    assert result["design_coverage"]=="not_measured"
    assert result["analyzers"]["register_flow"]["configured_limits"]["MAX_PROCESSES"]==512

def test_late_analyzer_partial():
    g=empty_graph()
    row(g,"array_dependencies",coverage="partial",reason="runtime_index")
    r=analyzer_summary(g)
    assert r["limited_analyzers"]==["array_dependencies"]
    assert r["analyzers"]["array_dependencies"]["partial_reasons"]=={"runtime_index":1}
    assert r["assessment"]=="reported_limits"

def test_nested_truncation():
    g=empty_graph()
    row(g,"complex_constructs",coverage="syntax_observed",selectors=[{"truncated":True}])
    r=analyzer_summary(g)
    assert r["truncated_analyzers"]==["complex_constructs"]
    assert r["analyzers"]["complex_constructs"]["rows_with_nested_truncation"]==1

def test_inherited_truncation():
    g=empty_graph()
    for n in ("register_flow","sequential_candidates","intercycle_dependencies"):
        g[n]["counts"]["truncated"]=True
    r=analyzer_summary(g)
    assert r["assessment"]=="reported_truncation"
    assert r["truncated_analyzers"]==["register_flow","sequential_candidates","intercycle_dependencies"]
    assert r["analyzers"]["sequential_candidates"]["upstream_truncation"]=="register_flow"
    assert r["analyzers"]["intercycle_dependencies"]["upstream_truncation"]=="sequential_candidates"

def test_findings_truncation_is_not_analyzer_truncation():
    g=empty_graph()
    g["coverage"]["findings_truncated"]=True
    r=analyzer_summary(g)
    assert r["assessment"]=="reported_limits"
    assert r["truncated_analyzers"]==[]
    assert r["coverage_findings_truncated"]

def test_exclusions_and_warnings():
    g=empty_graph()
    g["warnings"]=[{"reason":"test"}]
    g["bit_accesses"]["counts"]["unsupported_targets"]=2
    r=analyzer_summary(g)
    assert r["signal_graph_warnings"]==1
    assert r["limited_analyzers"]==["bit_accesses"]

@pytest.mark.parametrize("bad",["missing","count","bool_count","truncated","row"])
def test_malformed_analyzer(bad):
    g=empty_graph()
    if bad=="missing":
        del g["function_dependencies"]
    elif bad=="count":
        g["function_dependencies"]["counts"]["captured"]=1
    elif bad=="bool_count":
        g["function_dependencies"]["counts"]["captured"]=False
    elif bad=="truncated":
        g["function_dependencies"]["counts"]["truncated"]=1
    else:
        g["function_dependencies"]["items"]=[None]
        g["function_dependencies"]["counts"]["captured"]=1
    with pytest.raises(ValueError):
        analyzer_summary(g)

def test_publication_gate_and_immutability():
    g=empty_graph()
    original=copy.deepcopy(g)
    with pytest.raises(AnalysisBudgetError,match="graph_publication"):
        build_analysis_limits(g,{},AnalysisBudget(max_graph_values=1))
    assert g==original
    build_analysis_limits(g,{},DEFAULT_BUDGET)
    assert g==original

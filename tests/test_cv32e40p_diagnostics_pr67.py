import copy
import pytest
from rtlprep import expressions, complex_constructs
from rtlprep.dependencies import build_dependency_graph
from rtlprep.index import build_index
from scripts.cv32e40p_pr67 import (UNKNOWN, owner_for, ast_inventory, summarize_rows,
    bit_inventory, diagnose)
from scripts.run_cv32e40p_diagnostics_pr67 import markdown

def ref(name,addr):
    return {"kind":"NamedValue","symbol":f"{addr} {name}","type":"logic[7:0]"}

def assignment(line,select=False):
    rhs=ref("a",10)
    if select:
        rhs={"kind":"RangeSelect","selectionKind":"Simple","type":"logic[7:0]",
             "value":rhs,"left":{"kind":"IntegerLiteral","value":"7"},
             "right":{"kind":"IntegerLiteral","value":"0"}}
    return {"kind":"ContinuousAssign","assignment":{"kind":"Assignment",
            "left":ref("y",20),"right":rhs,"isNonBlocking":False,
            "source_file_start":"fixture.sv","source_line_start":line}}

def ast_fixture():
    members=[
        {"kind":"Port","name":"a","direction":"In","type":"logic[7:0]"},
        {"kind":"Net","name":"a","addr":10,"type":"logic[7:0]"},
        {"kind":"Port","name":"y","direction":"Out","type":"logic[7:0]"},
        {"kind":"Variable","name":"y","addr":20,"type":"logic[7:0]"},
        assignment(4,True),assignment(5,True),
        {"kind":"GenerateBlock","name":"off","isUninstantiated":True,
         "members":[assignment(99)]},
    ]
    return {"design":{"kind":"Root","members":[{"kind":"Instance","name":"top",
              "body":{"kind":"InstanceBody","name":"top","members":members}}]}}

@pytest.fixture
def fixture():
    a=ast_fixture()
    i=build_index(a,expected_top="top")
    g=build_dependency_graph(a,expected_top="top",index=i)
    g["source_fingerprint"]="fixture"
    return a,i,g

@pytest.mark.parametrize("target,expected",[("top.a","top"),("top.child.a","top.child"),
    ("top.childish.a","top"),("not_top.a",UNKNOWN),(None,UNKNOWN)])
def test_owner(target,expected):
    assert owner_for(target,{"top","top.child"})==expected

def test_census_excludes_inactive_generate(fixture):
    a,i,g=fixture
    census=ast_inventory(a,{"top"})
    assert census["assignment_count"]==2
    assert census["by_instance"]["top"]["RangeSelect"]==2
    assert {r["source"]["line"] for r in census["assignment_sites"]}=={4,5}

def test_diagnostics_reconciles_all_ten(fixture):
    a,i,g=fixture
    result=diagnose(g,i,a)
    assert len(result["analyzers"])==10
    assert result["design_coverage"]=="not_measured"
    assert result["bit_inventory"]["counts"]==g["bit_dependency_graph"]["counts"]
    assert "top | top | 2" in markdown([result])

def test_row_count_mismatch(fixture):
    a,i,g=fixture
    g["expressions"]["counts"]["captured"]+=1
    with pytest.raises(ValueError,match="captured count"):
        summarize_rows(g,i)

def test_status_count_mismatch(fixture):
    a,i,g=fixture
    g["expressions"]["items"][0]["coverage"]="invented"
    with pytest.raises(ValueError,match="status count"):
        summarize_rows(g,i)

def test_warning_count_mismatch(fixture):
    a,i,g=fixture
    g["counts"]["warnings"]+=1
    with pytest.raises(ValueError,match="warning count"):
        diagnose(g,i,a)

def test_bit_join_reason_and_zero_edges():
    g={"bit_accesses":{"items":[{"target":"top.y","coverage":"partial","reason":"dynamic_or_unknown_index",
                                 "source":{"file":"a.sv","line":5}}]},
       "bit_dependency_graph":{"items":[{"assignment_id":0,"target":"top.y","coverage":"partial",
              "reason":"partial_bit_access","edge_count":0}],"edges":[],
              "counts":{"assignments":1,"supported":0,"partial":1,"edges":0,"truncated":False}}}
    inv=bit_inventory(g,{"top"})
    assert inv["partial_reasons"]=={"dynamic_or_unknown_index":1}
    assert inv["partial_assignments"][0]["source"]["line"]==5
    assert inv["partial_assignments"][0]["bit_graph_reason"]=="partial_bit_access"

@pytest.mark.parametrize("mode",["ordinal","target","edge_count","global_count","extra_row"])
def test_bit_join_rejects_inconsistency(mode):
    g={"bit_accesses":{"items":[{"target":"top.y"}]},
       "bit_dependency_graph":{"items":[{"assignment_id":0,"target":"top.y","coverage":"partial","edge_count":0}],
          "edges":[],"counts":{"assignments":1,"supported":0,"partial":1,"edges":0,"truncated":False}}}
    b=g["bit_dependency_graph"]
    if mode=="ordinal":
        b["items"][0]["assignment_id"]=3
    elif mode=="target":
        b["items"][0]["target"]="top.z"
    elif mode=="edge_count":
        b["items"][0]["edge_count"]=1
    elif mode=="global_count":
        b["counts"]["partial"]=2
    else:
        b["items"].append(copy.deepcopy(b["items"][0]))
    with pytest.raises(ValueError):
        bit_inventory(g,{"top"})

def test_expression_cap_hits(monkeypatch,fixture):
    a,i,g=fixture
    monkeypatch.setattr(expressions,"MAX_EXPRESSIONS",1)
    result=expressions.build_expression_index(a,expected_top="top",index=i)
    assert result["counts"]["captured"]==1
    assert result["counts"]["truncated"] is True
    assert result["truncation_events"]["row_cap_hits"]==1
    assert result["truncation_events"]["first"]["instance"]=="top"

def test_complex_row_cap(monkeypatch,fixture):
    a,i,g=fixture
    monkeypatch.setattr(complex_constructs,"MAX_ROWS",1)
    result=complex_constructs.build_complex_construct_index(a,index=i)
    assert result["counts"]["captured"]==1
    assert result["counts"]["truncated"] is True
    assert result["truncation_events"]["hits"]["row_cap"]==1

def test_complex_depth_cap(monkeypatch,fixture):
    a,i,g=fixture
    monkeypatch.setattr(complex_constructs,"MAX_DEPTH",1)
    result=complex_constructs.build_complex_construct_index(a,index=i)
    assert result["counts"]["truncated"] is True
    assert result["truncation_events"]["hits"]["depth_cap"]>=1

def test_complex_queue_cap(monkeypatch,fixture):
    a,i,g=fixture
    monkeypatch.setattr(complex_constructs,"MAX_NODES",4)
    result=complex_constructs.build_complex_construct_index(a,index=i)
    assert result["counts"]["truncated"] is True
    assert result["truncation_events"]["hits"]["list_queue_cap"]>=1

def test_no_cap_hits(fixture):
    a,i,g=fixture
    assert g["expressions"]["truncation_events"]["row_cap_hits"]==0
    assert g["complex_constructs"]["truncation_events"]["hits"]=={}

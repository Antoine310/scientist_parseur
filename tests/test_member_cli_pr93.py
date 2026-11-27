import copy
import json
import sys
import pytest
from rtlprep import __main__ as cli
from rtlprep import runner
from rtlprep import member_query as q

def graph():
    p={"relation":"packed_struct_position_candidate","target":"top.b","source":"top.a"}
    def endpoint(s):
        return {"signal":s,"coordinate_kind":"declared_index","position":0}
    row={"record_id":"pr79:edges:0","row_id":"pr79:0","producer":"pr79",
         "occurrence_ordinal":2,"instance":"top","context":"continuous","source_location":{"line":3},
         "source":endpoint("top.a"),"target":endpoint("top.b"),"payload":p}
    return {"schema_version":1,"top":"top","source_fingerprint":"abc",
            "member_position_candidates":{"schema_version":1,"truncated":False,"items":[row],
                 "counts":{"positions":1},"design_coverage":"not_measured",
                 "functional_influence":"not_proven","formal_proof":"not_performed"}}

def test_missing_distinct_from_empty():
    g=graph()
    r=q.query_members(g,category="local_constant")
    assert r["total"]==0 and r["category_published"] is False
    g["member_position_candidates"]["items"]=[]
    g["member_position_candidates"]["counts"]["positions"]=0
    r=q.query_members(g,category="position")
    assert r["total"]==0 and r["category_published"] is True

def test_filter_exact_and_provenance():
    g=graph()
    before=copy.deepcopy(g)
    for sig in ("top.a","top.b"):
        r=q.query_members(g,signal=sig)
        assert r["total"]==1 and r["items"][0]["category"]=="position"
        assert r["items"][0]["source_location"]=={"line":3} and r["source_fingerprint"]=="abc"
        r["items"][0]["payload"]["target"]="changed"
    assert q.query_members(g,signal="top")["total"]==0 and g==before

def test_pages():
    g=graph()
    c=g["member_position_candidates"]
    row=copy.deepcopy(c["items"][0])
    row["record_id"]="pr79:edges:1"
    c["items"].append(row)
    c["counts"]["positions"]=2
    p=q.query_members(g,limit=1)
    assert p["total"]==2 and p["next_offset"]==1
    p=q.query_members(g,limit=1,offset=1)
    assert p["items"][0]["record_id"]=="pr79:edges:1" and p["next_offset"] is None
    assert q.query_members(g,offset=5)["items"]==[]

@pytest.mark.parametrize("kwargs",[{"limit":0},{"limit":101},{"limit":True},{"offset":-1},{"offset":False},
    {"signal":""},{"category":"bad"}])
def test_bad_query(kwargs):
    with pytest.raises(ValueError):
        q.query_members(graph(),**kwargs)

@pytest.mark.parametrize("mode",["schema","count","truncated","producer","duplicate","endpoint","payload","claims"])
def test_bad_graph(mode):
    g=graph()
    c=g["member_position_candidates"]
    r=c["items"][0]
    if mode=="schema": g["schema_version"]=2
    elif mode=="count": c["counts"]["positions"]=True
    elif mode=="truncated": c["truncated"]=True
    elif mode=="producer": r["producer"]="pr80"
    elif mode=="duplicate": c["items"].append(copy.deepcopy(r));c["counts"]["positions"]=2
    elif mode=="endpoint": r["source"]["position"]=True
    elif mode=="payload": r["payload"]["target"]="wrong"
    else: c["formal_proof"]="proved"
    with pytest.raises(ValueError):
        q.query_members(g)

def test_bounded_load(tmp_path,monkeypatch):
    p=tmp_path/"g.json"
    p.write_text(json.dumps(graph()))
    assert q.load_member_graph(p)==graph()
    monkeypatch.setattr(q,"MAX_GRAPH_BYTES",5)
    with pytest.raises(ValueError,match="budget"):
        q.load_member_graph(p)

def test_cli_query(tmp_path,monkeypatch,capsys):
    p=tmp_path/"g.json"
    p.write_text(json.dumps(graph()))
    monkeypatch.setattr(sys,"argv",["rtlprep","member-evidence",str(p),"--category","position","--signal","top.b"])
    assert cli.main()==0
    assert json.loads(capsys.readouterr().out)["total"]==1

@pytest.mark.parametrize("flags,expected",[
    ([],(False,False,False)),(["--member-positions"],(True,False,False)),
    (["--member-combinational"],(False,True,False)),(["--member-sequential"],(False,False,True)),
    (["--member-all"],(True,True,True)),(["--member-positions","--member-sequential"],(True,False,True))])
def test_cli_deps_options(tmp_path,monkeypatch,flags,expected):
    from types import SimpleNamespace
    d=SimpleNamespace(top="top",sources=[],includes=[],defines=[])
    monkeypatch.setattr(cli,"load_design",lambda x:d)
    monkeypatch.setattr(cli,"fingerprint",lambda x:"hash")
    calls=[]
    def deps(d,out,timeout,**opts):
        calls.append(tuple(opts.values()))
        return {"status":"passed"}
    monkeypatch.setattr(cli,"dependency_design",deps)
    monkeypatch.setattr(sys,"argv",["rtlprep","deps","design.json","--out",str(tmp_path),*flags])
    assert cli.main()==0 and calls==[expected]

def test_failed_generation_removes_stale_graph(tmp_path,monkeypatch):
    p=tmp_path/"rtl_dependencies.json"
    p.write_text("{}")
    (tmp_path/"rtl_index.json").write_text("{}")
    from types import SimpleNamespace
    monkeypatch.setattr(runner,"index_design",lambda *a:{"status":"passed"})
    monkeypatch.setattr(runner,"read_ast",lambda *a:{})
    def fail(*a,**kw):
        raise ValueError("member budget")
    monkeypatch.setattr(runner,"build_dependency_graph",fail)
    result=runner.dependency_design(SimpleNamespace(top="top"),tmp_path,1,enable_member_positions=True)
    assert result["status"]=="failed" and not p.exists() and "dependencies" not in result

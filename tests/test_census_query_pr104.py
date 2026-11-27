import copy
import json
import sys
import pytest
from rtlprep import census_query as q
from rtlprep import __main__ as cli
from rtlprep.mcp_data import ReadOnlyRtl


def report():
    def v(cls,i=None,c=None):
        return {"classification":cls,"assignment_id":i,"position_coverage":c}
    base={"instance":"top","context":"continuous","source":{"file":"top.sv","line":1},
          "lhs_kind":"NamedValue","rhs_kind":"Call","selection_count":1,"call_argument_selection":True}
    rows=[dict(base,ast_path="/design/members/0",v1=v("captured",0,"partial"),v2=v("captured",1,"partial")),
          dict(base,ast_path="/design/members/1",v1=v("selection_gate_missed_syntax"),v2=v("captured",0,"partial")),
          dict(base,ast_path="/design/members/2",selection_count=0,call_argument_selection=False,
               v1=v("no_selection_syntax_in_operands"),v2=v("no_selection_syntax_in_operands"))]
    return {"schema_version":1,"scope":q.SCOPE,"top":"top","source_fingerprint":"abc",
            "input_sha256":{k:"a"*64 for k in q.INPUTS},"historical_projection_exact":True,
            "historical_replay_exact":True,"counts":{v:q._version_counts(rows,v) for v in ("v1","v2")},
            "new_partial_rows":1,"new_edges":0,"new_supported_rows":0,
            "design_coverage":"not_measured","functional_influence":"not_proven","items":rows}


def save(path,data):
    path.write_text(json.dumps(data))
    return path


def test_query_mapping_and_counts():
    r=q.validate(report())
    v1=q.query_census(r,version=1,classification="captured")
    v2=q.query_census(r,version=2,classification="captured")
    assert v1["total"]==1 and v2["total"]==2
    assert v1["items"][0]["v1"]["assignment_id"]==0
    assert v1["items"][0]["v2"]["assignment_id"]==1
    assert q.query_census(r,version=1,classification="selection_gate_missed_syntax")["total"]==1
    assert q.query_census(r,version=2,classification="selection_gate_missed_syntax")["total"]==0


def test_pages_isolated():
    r=report()
    before=copy.deepcopy(r)
    p=q.query_census(r,version=2,limit=1)
    assert p["next_offset"]==1 and p["total"]==3
    p["items"][0]["v2"]["assignment_id"]=99
    assert r==before
    assert q.query_census(r,version=2,limit=1,offset=2)["next_offset"] is None
    assert q.query_census(r,version=2,instance="top.unknown")["total"]==0


@pytest.mark.parametrize("kwargs",[{"version":3},{"version":True},{"version":"2"},{"limit":0},{"limit":101},
    {"limit":True},{"offset":-1},{"offset":False},{"classification":"wrong"},{"instance":""}])
def test_invalid_query(kwargs):
    args={"version":2,**kwargs}
    with pytest.raises(ValueError):
        q.query_census(report(),**args)


@pytest.mark.parametrize("bad",["schema","hash","claim","duplicate","id","count","new_support","lost","missing","boolid","extra_field"])
def test_invalid_report(bad):
    r=report()
    a,b,c=r["items"]
    if bad=="schema": r["schema_version"]=2
    elif bad=="hash": r["input_sha256"][q.INPUTS[0]]="bad"
    elif bad=="claim": r["functional_influence"]="proven"
    elif bad=="duplicate": b["ast_path"]=a["ast_path"]
    elif bad=="id": b["v2"]["assignment_id"]=a["v2"]["assignment_id"]
    elif bad=="count": r["counts"]["v1"]["captured"]=99
    elif bad=="new_support": b["v2"]["position_coverage"]="assignment_local_position_candidates"
    elif bad=="lost": a["v2"]=copy.deepcopy(c["v2"])
    elif bad=="missing": del a["v1"]
    elif bad=="boolid": a["v1"]["assignment_id"]=False
    else: a["extra"]="untrusted"
    with pytest.raises(ValueError):
        q.validate(r)


def test_load_and_response_budgets(tmp_path,monkeypatch):
    p=save(tmp_path/"r.json",report())
    assert q.load_report(p)==report()
    one=q.query_census(report(),version=2,limit=1)
    monkeypatch.setattr(q,"MAX_RESPONSE_BYTES",len(q._compact_bytes(one)))
    with pytest.raises(ValueError,match="response byte budget"):
        q.query_census(report(),version=2,limit=2)
    assert q.query_census(report(),version=2,limit=1)==one
    monkeypatch.setattr(q,"MAX_REPORT_BYTES",10)
    with pytest.raises(ValueError,match="byte budget"):
        q.load_report(p)


def test_cli_and_snapshot_parity(tmp_path,monkeypatch,capsys):
    p=save(tmp_path/"r.json",report())
    monkeypatch.setattr(sys,"argv",["rtlprep","selection-census",str(p),"--version","2","--limit","1"])
    assert cli.main()==0
    api=ReadOnlyRtl(census_file=p)
    assert api.capabilities()["selection_census_versions"]==[1,2]
    assert api.capabilities()["top"]=="top"
    assert json.loads(capsys.readouterr().out)==api.selection_census(2,limit=1)
    p.unlink()
    assert api.selection_census(1)["total"]==3


def test_absent_distinct_from_empty(tmp_path):
    api=ReadOnlyRtl(reports_dir=tmp_path)
    assert not api.capabilities()["selection_census_available"]
    with pytest.raises(ValueError,match="non configuré"):
        api.selection_census(2)


def test_mixed_artifact_refused(tmp_path):
    p=save(tmp_path/"r.json",report())
    idx=save(tmp_path/"i.json",{"schema_version":1,"top":"top","source_fingerprint":"abc"})
    with pytest.raises(ValueError,match="incompatibles"):
        ReadOnlyRtl(census_file=p,index_file=idx)


def test_no_overwrite(tmp_path):
    p=save(tmp_path/"existing.json",{"old":True})
    before=p.read_bytes()
    with pytest.raises(ValueError,match="output already exists"):
        q.export_report(tmp_path,p)
    assert p.read_bytes()==before


def test_cli_version_required(tmp_path,monkeypatch):
    p=save(tmp_path/"r.json",report())
    monkeypatch.setattr(sys,"argv",["rtlprep","selection-census",str(p)])
    with pytest.raises(SystemExit) as e:
        cli.main()
    assert e.value.code==2

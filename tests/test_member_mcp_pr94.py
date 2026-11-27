"""MCP member snapshot admission, query parity and response limits."""
import copy
import json
import pytest
from rtlprep import mcp_data as m
from rtlprep import member_query as q
from rtlprep.manifest import load_design
from rtlprep.runner import fingerprint


def graph():
    payload={"relation":"packed_struct_position_candidate","target":"top.b","source":"top.a"}
    def endpoint(s):
        return {"signal":s,"coordinate_kind":"declared_index","position":0}
    row={"record_id":"pr79:edges:0","row_id":"pr79:0","producer":"pr79",
         "occurrence_ordinal":2,"instance":"top","context":"continuous","source_location":{"line":3},
         "source":endpoint("top.a"),"target":endpoint("top.b"),"payload":payload}
    return {"schema_version":1,"top":"top","nodes":["top.a","top.b"],"source_fingerprint":"abc",
            "member_position_candidates":{"schema_version":1,"truncated":False,"items":[row],
            "counts":{"positions":1},"design_coverage":"not_measured",
            "functional_influence":"not_proven","formal_proof":"not_performed"}}


def save(path,g):
    path.write_text(json.dumps(g),encoding="utf-8")
    return path


def test_snapshot_query_parity(tmp_path):
    g=graph()
    p=save(tmp_path/"g.json",g)
    api=m.ReadOnlyRtl(graph_file=p)
    before=p.read_bytes()
    assert api.capabilities()["member_evidence_available"]
    assert api.capabilities()["member_query_limits"]["graph_bytes"]==64*1024*1024
    for signal in (None,"top.a","top.b"):
        page=api.member_evidence("position",signal,1,0)
        assert page=={**q.query_members(g,category="position",signal=signal,limit=1,offset=0),
                      "origin":"stored_member_candidates_not_reexecuted",
                      "source_snapshot_status":"unverifiable","artifact_fingerprint":"abc"}
        page["items"][0]["payload"]["source"]="mutated"
    assert api.graph==g and p.read_bytes()==before


def test_missing_vs_published_empty(tmp_path):
    g=graph()
    p=tmp_path/"g.json"
    del g["member_position_candidates"]
    api=m.ReadOnlyRtl(graph_file=save(p,g))
    assert not api.capabilities()["member_evidence_available"]
    assert api.member_evidence("position")["category_published"] is False
    g=graph()
    g["member_position_candidates"]["counts"]["positions"]=0
    g["member_position_candidates"]["items"]=[]
    api=m.ReadOnlyRtl(graph_file=save(p,g))
    assert api.capabilities()["member_evidence_available"]
    assert api.member_evidence("position")["category_published"] is True
    assert api.member_evidence("position")["total"]==0


def test_without_graph(tmp_path):
    api=m.ReadOnlyRtl(reports_dir=tmp_path)
    assert not api.capabilities()["member_evidence_available"]
    with pytest.raises(ValueError,match="Graphe non"):
        api.member_evidence()


@pytest.mark.parametrize("kwargs",[{"signal":"../secret"},{"signal":"top.unknown"},{"signal":""},
    {"category":"wrong"},{"limit":101},{"limit":True},{"offset":-1}])
def test_invalid_query(tmp_path,kwargs):
    api=m.ReadOnlyRtl(graph_file=save(tmp_path/"g.json",graph()))
    with pytest.raises(ValueError):
        api.member_evidence(**kwargs)


def test_admission_byte_gate(tmp_path,monkeypatch):
    p=save(tmp_path/"g.json",graph())
    monkeypatch.setattr(m,"MAX_GRAPH_BYTES",10)
    with pytest.raises(ValueError,match="volumineux"):
        m.ReadOnlyRtl(graph_file=p)


def test_admission_tree_gate(tmp_path,monkeypatch):
    from dataclasses import replace
    monkeypatch.setattr(m,"DEFAULT_BUDGET",replace(m.DEFAULT_BUDGET,max_graph_values=2))
    with pytest.raises(ValueError,match="mcp_graph_read"):
        m.ReadOnlyRtl(graph_file=save(tmp_path/"g.json",graph()))


def test_invalid_member_channel_at_startup(tmp_path):
    g=graph()
    g["member_position_candidates"]["counts"]["positions"]=99
    with pytest.raises(ValueError,match="count"):
        m.ReadOnlyRtl(graph_file=save(tmp_path/"g.json",g))


def test_response_budget_no_silent_truncation(tmp_path,monkeypatch):
    g=graph()
    c=g["member_position_candidates"]
    other=copy.deepcopy(c["items"][0])
    other["record_id"]="pr79:edges:1"
    c["items"].append(other)
    c["counts"]["positions"]=2
    api=m.ReadOnlyRtl(graph_file=save(tmp_path/"g.json",g))
    one=api.member_evidence(limit=1)
    cap=len(json.dumps(one,ensure_ascii=True,separators=(",",":"),allow_nan=False).encode())
    monkeypatch.setattr(m,"MAX_MEMBER_RESPONSE_BYTES",cap)
    with pytest.raises(ValueError,match="réduire limit"):
        api.member_evidence(limit=2)
    assert api.member_evidence(limit=1)==one and one["next_offset"]==1


def test_stale_source_status(tmp_path):
    rtl=tmp_path/"top.sv"
    rtl.write_text("module top; endmodule")
    manifest=save(tmp_path/"design.json",{"top":"top","sources":["top.sv"]})
    g=graph()
    g["source_fingerprint"]=fingerprint(load_design(manifest))
    api=m.ReadOnlyRtl(graph_file=save(tmp_path/"g.json",g),manifest_file=manifest)
    assert api.member_evidence()["source_snapshot_status"]=="matching"
    rtl.write_text("module top; logic x; endmodule")
    assert api.member_evidence()["source_snapshot_status"]=="stale"
    assert api.member_evidence()["total"]==1


def test_snapshot_not_reloaded(tmp_path):
    p=save(tmp_path/"g.json",graph())
    api=m.ReadOnlyRtl(graph_file=p)
    p.unlink()
    assert api.member_evidence()["total"]==1

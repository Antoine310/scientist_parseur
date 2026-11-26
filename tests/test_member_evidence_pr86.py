import copy
import pytest
from rtlprep.array_dependencies import Unsupported
from rtlprep.member_evidence import normalize, PRODUCERS, RELATIONS

def empty():
    return {name:{"scope":name,"counts":{"sites":0},"items":[],"edges":[],
                  "design_coverage":"not_measured","functional_influence":"not_proven",
                  "formal_proof":"not_performed","caveat":"original caveat"} for name,_ in PRODUCERS}

def example():
    reports=empty()
    for relation,(producer,collection,category) in RELATIONS.items():
        rep=reports[producer]
        sid=len(rep["items"])
        rep["items"].append({"site_id":sid,"instance":"top","context":"AlwaysComb",
                             "source":{"file":"same.sv","line":5},"coverage":"partial",
                             "reason":"original reason","conditional_operands":[{"proof":{"guard_value":0}}]})
        rep["counts"]["sites"]+=1
        v={"site_id":sid,"relation":relation,"target":"top.dst","target_bit":0}
        if collection=="edges":
            v.update(source="top.src",source_bit=1)
        else:
            v["value"]=0
        if relation=="local_packed_member_read_candidate":
            v.pop("target_bit")
            v.update(target_packed_offset=0,target_coordinates=[1,0],source_field_coordinates=[0,0])
        rep.setdefault(collection,[]).append(v)
    return reports

def test_empty_reports():
    result=normalize(empty())
    assert result["counts"]["producer_reports"]==7
    assert result["counts"]["candidate_records"]==result["counts"]["producer_rows"]==0

def test_all_relations_and_counts():
    r=normalize(example())
    assert r["counts"]=={"producer_reports":7,"producer_rows":12,"candidate_records":12,
                        "position":4,"logical_reference":1,"nba_sampled":1,
                        "local_constant":4,"nba_constant":1,"configuration_constant":1}

def test_lossless_and_input_immutable():
    reports=example()
    before=copy.deepcopy(reports)
    result=normalize(reports)
    for p in result["producers"]:
        name=p["producer"]
        reconstructed=copy.deepcopy(p["metadata"])
        reconstructed["items"]=[row["payload"] for row in result["rows"] if row["producer"]==name]
        for collection in p["present_collections"]:
            reconstructed[collection]=[v["payload"] for v in result["records"]
                                      if v["producer"]==name and v["collection"]==collection]
        assert reconstructed==reports[name]
    result["rows"][0]["payload"]["source"]["line"]=9
    assert reports==before

def test_no_merge_by_source_line():
    result=normalize(example())
    assert len({r["row_id"] for r in result["rows"]})==12
    assert {r["payload"]["source"]["line"] for r in result["rows"]}=={5}
    assert result["occurrence_identity"]=="producer_local_only"

def test_duplicate_candidate_preserved():
    reports=example()
    reports["pr79"]["edges"].append(copy.deepcopy(reports["pr79"]["edges"][0]))
    result=normalize(reports)
    assert result["counts"]["position"]==5
    assert len({r["record_id"] for r in result["records"]})==13

@pytest.mark.parametrize("mode",["missing_producer","extra_producer","scope","coverage_claim","row_count",
    "duplicate_row","orphan","boolean_site","unknown_relation","wrong_producer","wrong_collection",
    "bad_target","bad_bit","bad_coordinate","coordinate_as_bit","missing_source","constant_source",
    "constant_unknown","boolean_constant","count_disagreement"])
def test_fail_closed(mode):
    a=example()
    r=a["pr79"]
    e=r["edges"][0]
    if mode=="missing_producer": a.pop("pr85")
    elif mode=="extra_producer": a["unknown"]={}
    elif mode=="scope": r["scope"]=None
    elif mode=="coverage_claim": r["design_coverage"]="complete"
    elif mode=="row_count": r["counts"]["sites"]=99
    elif mode=="duplicate_row":
        r["items"].append(copy.deepcopy(r["items"][0]))
        r["counts"]["sites"]+=1
    elif mode=="orphan": e["site_id"]=99
    elif mode=="boolean_site": e["site_id"]=False
    elif mode=="unknown_relation": e["relation"]="unknown"
    elif mode=="wrong_producer": e["relation"]="fixed_member_position_candidate"
    elif mode=="wrong_collection":
        r["constants"]=[r["edges"].pop()]
    elif mode=="bad_target": e["target"]=""
    elif mode=="bad_bit": e["target_bit"]=-1
    elif mode in ("bad_coordinate","coordinate_as_bit"):
        v=a["pr82"]["edges"][0]
        if mode=="bad_coordinate": v["target_coordinates"]=[0]
        else: v["target_bit"]=0
    elif mode=="missing_source": e.pop("source")
    elif mode=="constant_source": a["pr80"]["constants"][0]["source"]="top.fake"
    elif mode=="constant_unknown": a["pr80"]["constants"][0]["value"]="x"
    elif mode=="boolean_constant": a["pr80"]["constants"][0]["value"]=False
    else: r["counts"]["edges"]=99
    with pytest.raises(Unsupported):
        normalize(a)

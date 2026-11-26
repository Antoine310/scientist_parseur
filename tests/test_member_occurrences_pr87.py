import copy
import pytest
from rtlprep.array_dependencies import Unsupported
from rtlprep.member_occurrences import occurrence_inventory,link

def ast():
    def assignment():
        return {"kind":"ContinuousAssign","assignment":{"kind":"Assignment",
                "source_file_start":"same.sv","source_line_start":5,
                "left":{"kind":"NamedValue"},"right":{"kind":"MemberAccess"}}}
    return {"design":{"members":[{"kind":"Instance","name":"top",
             "body":{"kind":"InstanceBody","members":[assignment(),assignment()]}}]}}

def row(producer,n,sid):
    return {"row_id":f"{producer}:{sid}","producer":producer,"payload":{
        "site_id":sid,"occurrence_ordinal":n,"instance":"top","context":"continuous",
        "source":{"file":"same.sv","line":5},"coverage":"partial"}}

def record(i,row_id,source="top.a",category="position",bit=0):
    return {"record_id":str(i),"row_id":row_id,"category":category,
            "payload":{"site_id":0,"source":source,"source_bit":0,"target":"top.dst",
                       "target_bit":bit,"relation":"test_relation"}}

def envelope():
    return {"rows":[row("pr79",0,0),row("pr79",1,1),row("pr83",0,0)],
            "records":[record(0,"pr79:0"),record(1,"pr79:1")]}

def test_same_line_distinct_occurrences():
    a=ast()
    inv=occurrence_inventory(a)
    assert list(inv)==[0,1] and inv[0]["source"]==inv[1]["source"]
    r=link(a,envelope())
    assert r["counts"]["occurrences"]==2 and r["counts"]["producer_rows"]==3
    assert r["counts"]["distinct_exact_records"]==2
    assert r["counts"]["duplicate_records"]==0

def test_exact_duplicates_only_within_occurrence():
    e=envelope()
    e["records"].append(record(2,"pr83:0"))
    r=link(ast(),e)
    assert r["counts"]["duplicate_records"]==1
    assert r["exact_duplicate_groups"]==[{"occurrence_ordinal":0,"record_ids":["0","2"]}]

def test_distinct_source_same_lane_disagreement():
    e=envelope()
    e["records"].append(record(2,"pr83:0","top.b"))
    r=link(ast(),e)
    assert r["counts"]["overlap_groups"]==r["counts"]["candidate_disagreement_groups"]==1

def test_logical_reference_multiplicity_is_not_conflict():
    e=envelope()
    e["records"]=[record(0,"pr79:0",category="logical_reference"),
                  record(1,"pr83:0","top.b",category="logical_reference")]
    r=link(ast(),e)
    assert r["counts"]["overlap_groups"]==r["counts"]["candidate_disagreement_groups"]==0
    assert r["counts"]["occurrences_without_records"]==1

def test_mixed_coordinate_systems_not_equated():
    e=envelope()
    v=record(2,"pr83:0")
    v["payload"].pop("target_bit")
    v["payload"]["target_packed_offset"]=0
    e["records"].append(v)
    r=link(ast(),e)
    assert r["counts"]["mixed_coordinate_groups"]==1
    assert r["counts"]["overlap_groups"]==0

def test_input_immutable():
    a,e=ast(),envelope()
    before=copy.deepcopy((a,e))
    link(a,e)
    assert (a,e)==before

@pytest.mark.parametrize("mode",["missing_ordinal","wrong_ordinal","boolean_ordinal","source","owner","context",
                                "duplicate_row","missing_census","orphan","duplicate_record"])
def test_fail_closed(mode):
    e=envelope()
    p=e["rows"][0]["payload"]
    if mode=="missing_ordinal": p.pop("occurrence_ordinal")
    elif mode=="wrong_ordinal": p["occurrence_ordinal"]=99
    elif mode=="boolean_ordinal": p["occurrence_ordinal"]=False
    elif mode=="source": p["source"]["line"]=9
    elif mode=="owner": p["instance"]="other"
    elif mode=="context": p["context"]="AlwaysFF"
    elif mode=="duplicate_row": e["rows"].append(copy.deepcopy(e["rows"][0]))
    elif mode=="missing_census": e["rows"].pop(1)
    elif mode=="orphan": e["records"][0]["row_id"]="missing"
    else: e["records"].append(copy.deepcopy(e["records"][0]))
    with pytest.raises(Unsupported):
        link(ast(),e)

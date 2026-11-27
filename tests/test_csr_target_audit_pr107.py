import pytest
from rtlprep.csr_target_audit import ordinal_index, classify_target, select_existing


class Resolver:
    def __init__(self,path):
        self.path=path
    def resolve(self,owner,node):
        return self.path
    def resolve_exact(self,owner,node):
        return self.path


def named(name="q",typ="logic"):
    return {"kind":"NamedValue","symbol":"123 "+name,"type":typ}


def test_exact_scoped_target():
    sig="top.gen.q"
    assert classify_target(named(),"top",set(),Resolver(sig),{sig:"logic"},{sig:["gen"]})=={
        "reason":"generate_scoped_target_outside_legacy_flat_gate","exact_target":sig,
        "field":None,"legacy_base_reason":"unknown_or_non_signal_base"}


def test_shadowed_name_not_flattened():
    sig="top.gen.q"
    r=classify_target(named(),"top",{"q"},Resolver(sig),{sig:"logic"},{sig:["gen"]})
    assert r["legacy_base_reason"]=="unresolved_symbol_identity" and r["exact_target"]==sig


def test_member_target():
    lhs={"kind":"MemberAccess","member":"321 f","value":named("bundle","struct")}
    r=classify_target(lhs,"top",{"bundle"},Resolver("top.bundle"),{"top.bundle":"struct"},{})
    assert r=={"reason":"member_access_outside_legacy_target_gate","exact_target":"top.bundle","field":"f"}


@pytest.mark.parametrize("path,types",[(None,{}),("top.gen.q",{}),("top.gen.q",{"top.gen.q":"bit"})])
def test_identity_refused(path,types):
    assert classify_target(named(),"top",set(),Resolver(path),types,{})["reason"]=="unproven_exact_declaration"


def test_actual_gate_must_refuse():
    with pytest.raises(ValueError,match="historical_target_refusal"):
        classify_target(named(),"top",{"q"},Resolver("top.q"),{"top.q":"logic"},{})


def test_other_shape():
    assert classify_target({"kind":"Concatenation"},"top",set(),Resolver(None),{}, {})["reason"]=="other_target_shape"


def test_other_named_target():
    assert classify_target(named(),"top",set(),Resolver("top.q"),{"top.q":"logic"}, {})["reason"]=="other_named_target_refusal"


def test_identity_ordinals_not_source_lines():
    a={"kind":"Assignment"}
    b=dict(a)
    assert ordinal_index([("top","Always",a),("top","Always",b)])=={
        ("top",id(a)):(0,"Always"),("top",id(b)):(1,"Always")}


def test_duplicate_identity():
    a={}
    with pytest.raises(ValueError,match="duplicate_assignment_identity"):
        ordinal_index([("top","Always",a),("top","Always",a)])


def position():
    return {"occurrence_ordinal":2,"record_id":"pr80:edges:0","row_id":"pr80:0",
            "producer":"pr80","category":"position","source":{"signal":"top.data","position":1},
            "target":{"signal":"top.bundle","field":"f","coordinate_kind":"packed_struct_offset","position":0}}


def test_existing_position_not_new():
    p=position()
    r=select_existing(2,{"exact_target":"top.bundle","field":"f"},[p])
    assert r==[{k:p[k] for k in ("record_id","row_id","producer","source","target")}]


@pytest.mark.parametrize("bad",["ordinal","target","field","coordinate","category","duplicate"])
def test_overlap_refusals(bad):
    p=position()
    rows=[p]
    if bad=="ordinal": p["occurrence_ordinal"]=3
    elif bad=="target": p["target"]["signal"]="top.other"
    elif bad=="field": p["target"]["field"]="g"
    elif bad=="coordinate": p["target"]["coordinate_kind"]="declared_index"
    elif bad=="category": p["category"]="logical_reference"
    else: rows.append(dict(p))
    with pytest.raises(ValueError):
        select_existing(2,{"exact_target":"top.bundle","field":"f"},rows)


def test_absence_not_an_edge():
    assert select_existing(0,{"exact_target":"top.gen.q","field":None},[])==[]


def test_runner_uses_declared_fixture_top(monkeypatch,tmp_path):
    from scripts import run_csr_target_audit_pr107 as runner
    import re
    declared=re.findall(r"(?m)^module\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",runner.FIXTURE.read_text())
    assert declared==["csr_target_audit_pr107"]
    calls=[]
    monkeypatch.setattr(runner,"extract",lambda directory,top,sources:calls.append((directory,top,sources)))
    runner.extract_fixture(tmp_path)
    assert calls==[(tmp_path,declared[0],[runner.FIXTURE])]

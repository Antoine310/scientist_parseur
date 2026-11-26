import copy
import pytest
from rtlprep.array_dependencies import Unsupported
from rtlprep import member_sequential as m
from rtlprep import member_combinational as c

def node():
    return {"kind":"Assignment","isNonBlocking":True,"type":"1 p::T",
            "left":{"kind":"NamedValue","type":"1 p::T"},
            "right":{"kind":"StructuredAssignmentPattern","type":"1 p::T"}}

def row():
    return {"context":"AlwaysFF","coverage":"nba_assignment_candidates","kind":"StructuredAssignmentPattern"}

def test_exact_nba_statement():
    n=node()
    assert m.check_nba_node(n,"AlwaysFF",row()) is n["left"]

@pytest.mark.parametrize("mode",["blocking","missing_nba","timing","compound","wrong_context",
    "wrong_row","partial","wrong_kind","bad_lhs","bad_rhs","type_disagreement"])
def test_refuse_unproven_nba(mode):
    n,r,context=node(),row(),"AlwaysFF"
    if mode=="blocking": n["isNonBlocking"]=False
    elif mode=="missing_nba": n.pop("isNonBlocking")
    elif mode=="timing": n["timingControl"]={}
    elif mode=="compound": n["op"]="Add"
    elif mode=="wrong_context": context="AlwaysComb"
    elif mode=="wrong_row": r["context"]="Always"
    elif mode=="partial": r["coverage"]="partial"
    elif mode=="wrong_kind": r["kind"]="Concatenation"
    elif mode=="bad_lhs": n["left"]["kind"]="MemberAccess"
    elif mode=="bad_rhs": n["right"]["kind"]="Concatenation"
    else: n["right"]["type"]="2 p::T"
    with pytest.raises(Unsupported):
        m.check_nba_node(n,context,r)

def partition():
    lay={"kind":"packed_struct_offset","members":{"a":[0,[[0]]],"b":[1,[[0]]]}}
    items=[{"target":{"signal":"top.q","coordinate_kind":"packed_struct_offset","position":i}} for i in (0,1)]
    return lay,items

def test_complete_partition():
    lay,items=partition()
    before=copy.deepcopy((lay,items))
    assert m.validate_partition(items,lay,"top.q")==2
    assert (lay,items)==before

@pytest.mark.parametrize("mode",["missing","duplicate","outside","wrong_target","wrong_unit","wrong_layout"])
def test_bad_partition(mode):
    lay,items=partition()
    if mode=="missing": items.pop()
    elif mode=="duplicate": items.append(copy.deepcopy(items[0]))
    elif mode=="outside": items[1]["target"]["position"]=2
    elif mode=="wrong_target": items[0]["target"]["signal"]="top.other"
    elif mode=="wrong_unit": items[0]["target"]["coordinate_kind"]="declared_index"
    else: lay["kind"]="declared_index"
    with pytest.raises(Unsupported):
        m.validate_partition(items,lay,"top.q")

@pytest.mark.parametrize("positions,combinational,sequential",[(True,True,True),(False,False,True),(True,False,True),(False,True,False)])
def test_single_collection(monkeypatch,positions,combinational,sequential):
    calls=[]
    evidence,linked=object(),object()
    def collect(ast,index):
        calls.append("collect")
        return evidence,{},linked
    def builder(name):
        def build(ast,index,graph,e,l):
            assert e is evidence and l is linked
            calls.append(name)
            return name
        return build
    monkeypatch.setattr(c,"collect_linked",collect)
    monkeypatch.setattr(c,"_build_combinational",builder("comb"))
    monkeypatch.setattr(c,"_build_member_positions",builder("pos"))
    monkeypatch.setattr(m,"_build_sequential",builder("seq"))
    result=c.build_member_channels({}, {}, {},positions=positions,combinational=combinational,sequential=sequential)
    assert calls==["collect"]+(["comb"] if combinational else [])+(["pos"] if positions else [])+(["seq"] if sequential else [])
    assert set(result)=={k for flag,k in ((positions,"member_position_candidates"),(combinational,"member_combinational_candidates"),(sequential,"member_sequential_candidates")) if flag}

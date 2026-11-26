import copy
import pytest
from rtlprep import member_occurrences as m
from rtlprep.array_dependencies import Unsupported
from rtlprep.member_evidence import PRODUCERS

def assignment(left,right):
    return {"kind":"ContinuousAssign","assignment":{"kind":"Assignment","left":left,"right":right,
              "source_file_start":"same.sv","source_line_start":5}}

def named():
    return {"kind":"NamedValue","name":"x","type":"logic"}

def member():
    return {"kind":"MemberAccess","value":named(),"type":"logic","member":"1 a"}

def make_ast(nodes):
    return {"design":{"members":[{"kind":"Instance","name":"top",
             "body":{"kind":"InstanceBody","members":nodes}}]}}

def empty_index():
    return {"instances":[{"path":"top","ports":[]}],"signals":[]}

def test_empty_collection_matches_independent():
    a=make_ast([assignment(named(),named())])
    index=empty_index()
    before=copy.deepcopy((a,index))
    assert m.collect_linked(a,index)==m.collect_linked(a,index,shared=False)
    assert (a,index)==before

def test_sparse_ordinals_not_renumbered():
    a=make_ast([assignment(named(),named()),assignment(named(),member()),
                assignment(named(),named()),assignment(member(),named())])
    ctx=m._SharedAudit(a,empty_index())
    assert len(ctx.sites)==4 and [i for i,_ in ctx.member_assignments]==[1,3]
    assert ctx.inventory==m.occurrence_inventory(a)

def test_same_line_and_unsupported_members_preserved():
    a=make_ast([assignment(named(),member()),assignment(named(),named()),assignment(member(),named())])
    index=empty_index()
    shared=m.collect_linked(a,index)
    assert shared==m.collect_linked(a,index,shared=False)
    assert [x["occurrence_ordinal"] for x in shared[2]["occurrences"]]==[0,2]

def test_uninstantiated_and_function_not_active():
    a=make_ast([{"kind":"GenerateBlock","isUninstantiated":True,"members":[assignment(named(),member())]},
                {"kind":"Function","body":assignment(named(),member())},assignment(named(),named())])
    assert not m._SharedAudit(a,empty_index()).member_assignments

def test_nested_assignment_separate_site():
    nested={"kind":"Assignment","left":named(),"right":member()}
    a=make_ast([assignment(named(),nested)])
    ctx=m._SharedAudit(a,empty_index())
    assert len(ctx.sites)==2 and [i for i,_ in ctx.member_assignments]==[1]

def test_identity_checked():
    a,i=make_ast([]),empty_index()
    ctx=m._SharedAudit(a,i)
    ctx.check_inputs(a,i)
    with pytest.raises(Unsupported):
        ctx.check_inputs(copy.deepcopy(a),i)
    with pytest.raises(Unsupported):
        ctx.check_inputs(a,copy.deepcopy(i))

def test_budget_not_skipped_for_empty_member_census(monkeypatch):
    a=make_ast([assignment(named(),named()),assignment(named(),named())])
    monkeypatch.setattr(m,"MAX_OCCURRENCES",1)
    for shared in (True,False):
        with pytest.raises(Unsupported,match="occurrence_inventory_budget"):
            m.collect_linked(a,empty_index(),shared=shared)

def test_context_not_reused_across_calls():
    a,i=make_ast([]),empty_index()
    c,d=m._SharedAudit(a,i),m._SharedAudit(a,i)
    assert c.types is c.types and c.types is not d.types
    assert c.resolver is c.resolver and c.resolver is not d.resolver

def test_single_shared_assignment_traversal(monkeypatch):
    a,i=make_ast([]),empty_index()
    original=m.assignment_sites
    calls=[]
    def counted(ast):
        calls.append(ast)
        yield from original(ast)
    monkeypatch.setattr(m,"assignment_sites",counted)
    m.collect_linked(a,i)
    assert calls==[a]

def test_shared_package_observations_once(monkeypatch):
    from rtlprep import packed_members
    a,i=make_ast([]),empty_index()
    original=packed_members.observed_members
    calls=[]
    def counted(ast,types):
        calls.append(ast)
        return original(ast,types)
    monkeypatch.setattr(packed_members,"observed_members",counted)
    m.collect_linked(a,i)
    assert calls==[a]

def test_standalone_audit_unchanged_shape():
    a,i=make_ast([]),empty_index()
    for _,audit in PRODUCERS:
        assert audit(a,i)==audit(a,i,include_occurrence=True)

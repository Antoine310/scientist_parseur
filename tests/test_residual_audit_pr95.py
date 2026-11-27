import copy
import pytest
from rtlprep import residual_audit as m

def graph():
    accesses=[{"target":"top.a","source":{"line":1},"coverage":"partial","reason":"unsupported_rhs_BinaryOp"},
              {"target":"top.a","source":{"line":1},"coverage":"partial","reason":"dynamic_or_unknown_index"},
              {"target":"top.b","source":{"line":2},"coverage":"rhs_lanes_only"}]
    rows=[{"assignment_id":i,"target":a["target"],"source_location":a["source"],
           "assignment_kind":"continuous","coverage":"partial" if i<2 else "assignment_local_position_candidates",
           "reason":"partial_bit_access"} for i,a in enumerate(accesses)]
    g={"bit_accesses":{"items":accesses,"counts":{"captured":3,"truncated":False}},
       "bit_dependency_graph":{"items":rows,"counts":{"assignments":3,"supported":1,"partial":2,"truncated":False}}}
    for k in m.CHANNELS:
        g[k]={"items":[],"counts":{"captured":0,"truncated":False}}
    for k in m.CHANNELS[:2]:
        g[k]={"items":[{"flat_assignment_id":0,"target":"top.a","source_location":{"line":1},"coverage":"candidate"}],
              "counts":{"captured":1,"truncated":False}}
    return g

def test_union_and_same_line_distinct():
    g=graph()
    before=copy.deepcopy(g)
    s,r,left,links,channels,unlinked=m.exact_links(g)
    assert (s,r,left)==({2},{0},{1})
    assert len(links[0])==2 and not links[1]
    assert channels[m.CHANNELS[1]]["new_ids"]==0 and g==before

def test_unlinked_not_guessed():
    g=graph()
    k=m.CHANNELS[0]
    g[k]["items"][0].pop("flat_assignment_id")
    g[m.CHANNELS[1]]["items"].clear()
    g[m.CHANNELS[1]]["counts"]["captured"]=0
    _,r,left,_,_,unlinked=m.exact_links(g)
    assert not r and left=={0,1} and unlinked[k]=={"candidate":1}

@pytest.mark.parametrize("bad",["id","source","context","count","truncated","link_id","link_source","link_count","link_truncated"])
def test_refuse_bad_links(bad):
    g=graph()
    a=g["bit_accesses"]
    f=g["bit_dependency_graph"]
    c=g[m.CHANNELS[0]]
    if bad=="id": f["items"][0]["assignment_id"]=True
    elif bad=="source": f["items"][0]["source_location"]={"line":99}
    elif bad=="context": f["items"][0]["assignment_kind"]="procedural"
    elif bad=="count": a["counts"]["captured"]=2
    elif bad=="truncated": f["counts"]["truncated"]=True
    elif bad=="link_id": c["items"][0]["flat_assignment_id"]=True
    elif bad=="link_source": c["items"][0]["source_location"]={"line":99}
    elif bad=="link_count": c["counts"]["captured"]=0
    else: c["counts"]["truncated"]=True
    with pytest.raises(ValueError):
        m.exact_links(g)

def test_detailed_reason_only_for_generic_refusal():
    a={"coverage":"partial","reason":"unsupported_rhs_BinaryOp"}
    assert m.detailed_reason({"reason":"partial_bit_access"},a)==a["reason"]
    assert m.detailed_reason({"reason":"unproven_packed_layout"},a)=="unproven_packed_layout"
    with pytest.raises(ValueError):
        m.detailed_reason({"reason":"partial_bit_access"},{"coverage":"partial"})

def test_capture_identity_not_value_equality():
    a=graph()["bit_accesses"]
    rows=a["items"]
    c=[(i,row,{"kind":"Assignment"},"top",{},False) for i,row in enumerate(rows)]
    assert set(m.reconcile_capture(a,list(reversed(c))))=={0,1,2}
    bad=list(c)
    bad[0]=(0,copy.deepcopy(rows[0]),c[0][2],"top",{},False)
    with pytest.raises(ValueError):
        m.reconcile_capture(a,bad)
    with pytest.raises(ValueError):
        m.reconcile_capture(a,c[:-1])
    with pytest.raises(ValueError):
        m.reconcile_capture(a,c+[c[0]])

def test_nested_operators_and_metadata():
    leaf={"kind":"NamedValue"}
    add={"kind":"BinaryOp","op":"Add","left":leaf,"right":leaf}
    node={"kind":"Conversion","operand":{"kind":"BinaryOp","op":"Subtract","left":add,"right":add},
          "type":{"kind":"BinaryOp","op":"Fake"}}
    result=m.syntax(node)
    assert result["root_kind"]=="Conversion" and result["root_after_conversions"]=="BinaryOp"
    assert result["root_operator"]=="Subtract" and result["leading_conversions"]==1
    assert result["operators"]=={"BinaryOp:Add":2,"BinaryOp:Subtract":1}
    assert result["scan_complete"]

def test_scan_budget_is_explicit(monkeypatch):
    monkeypatch.setattr(m,"MAX_SCAN",2)
    result=m.syntax({"kind":"BinaryOp","op":"Add","left":{},"right":{}})
    assert not result["scan_complete"] and result["scan_limitation"]=="syntax_scan_budget"

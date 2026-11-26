import pytest
from rtlprep import dynamic_dependencies as dyn
from rtlprep.array_dependencies import Unsupported,layout
from rtlprep.dependencies import build_dependency_graph

def n(kind,**kw):
    return {"kind":kind,**kw}
def ref(name,addr,typ):
    return n("NamedValue",symbol=f"{addr} {name}",type=typ)
def num(v):
    return n("IntegerLiteral",type="int",value=str(v))
SIGNALS=[("p",10,"logic[3:0][3:0]"),("d",20,"logic[3:0]"),
         ("idx",30,"logic[1:0]"),("q",40,"logic[3:0]"),
         ("u",50,"logic[3:0]$[0:3]"),("s",60,"logic"),
         ("idx2",70,"logic[1:0]")]
def symbol(name):
    addr,typ=next((a,t) for nm,a,t in SIGNALS if nm==name)
    return ref(name,addr,typ)
def element(base,index=None,typ="logic[3:0]"):
    return n("ElementSelect",type=typ,value=base,selector=symbol("idx") if index is None else index)
def assignment(lhs=None,rhs=None,typ="logic[3:0]"):
    return n("Assignment",type=typ,isNonBlocking=False,left=symbol("q") if lhs is None else lhs,
             right=element(symbol("p")) if rhs is None else rhs)
def expand(a,signals=SIGNALS):
    declared={f"top.{name}":layout(typ) for name,_,typ in signals}
    symbols={f"{addr} {name}":f"top.{name}" for name,addr,_ in signals}
    return dyn.expand(a,lambda e:symbols.get(e.get("symbol")),declared,{})
def graph(a,enabled=True):
    members=[n("Variable",name=name,addr=addr,type=typ) for name,addr,typ in SIGNALS]
    members.append(n("ContinuousAssign",assignment=a))
    ast={"design":n("Root",members=[n("Instance",name="top",
        body=n("InstanceBody",name="top",members=members))])}
    return build_dependency_graph(ast,expected_top="top",enable_dynamic=enabled)

def edges_of(edges,role,aid):
    return [e for e in edges if e["relation"]==role and e["alternative_id"]==aid]

@pytest.mark.parametrize("name,kind", [("p","packed"),("u","unpacked")])
@pytest.mark.parametrize("role",["read","write"])
def test_word_alternatives(name,kind,role):
    expr=element(symbol(name))
    a=assignment(rhs=expr) if role=="read" else assignment(lhs=expr,rhs=symbol("d"))
    edges,domain,alternatives=expand(a)
    assert domain["role"]==role and domain["dimension_kind"]==kind
    assert domain["indices"]==list(range(4)) and not domain["numeric_out_of_range_possible"]
    assert domain["unknown_selector_possible"]
    assert len(edges)==48 and len(alternatives)==4
    for i in range(4):
        data=edges_of(edges,"index_data_candidate",i)
        control=edges_of(edges,"index_control_candidate",i)
        assert len(data)==4 and len(control)==8
        assert {(e["source_bit"],e["target_bit"]) for e in data}=={(b,b) for b in range(4)}
        field=("source" if role=="read" else "target")+"_"+kind+"_indices"
        assert all(e[field]==[i] for e in data)
        assert {(e["source"],e["source_bit"],e["target_bit"]) for e in control}=={
            ("top.idx",j,b) for j in range(2) for b in range(4)}
        assert alternatives[i]=={"alternative_id":i,"selector_value":i,"constant_target_positions":[]}

def test_dynamic_bit_in_fixed_word():
    a=assignment(lhs=symbol("s"),rhs=element(element(symbol("p"),num(2)),typ="logic"),typ="logic")
    edges,d,_=expand(a)
    assert d["dimension_kind"]=="bit" and d["dimension_ordinal"]==1
    assert {(e["alternative_id"],tuple(e["source_packed_indices"]),e["source_bit"],e["target_bit"])
        for e in edges if e["relation"]=="index_data_candidate"}=={(i,(2,),i,0) for i in range(4)}

def test_constant_write_is_alternative_local():
    a=assignment(lhs=element(symbol("p")),rhs=n("UnbasedUnsizedIntegerLiteral",type="logic[3:0]",value="4'b1111"))
    edges,d,alts=expand(a)
    assert len(edges)==32 and d["role"]=="write"
    assert all(e["relation"]=="index_control_candidate" for e in edges)
    for i,alt in enumerate(alts):
        assert [(p["target_packed_indices"],p["target_bit"]) for p in alt["constant_target_positions"]]==[([i],b) for b in range(4)]
        assert all("value" not in p for p in alt["constant_target_positions"])

def test_unsigned_index_width_limits_domain():
    # A one-bit index can address only values 0 and 1 even in a larger declaration.
    sig=[(nm,a,"logic" if nm=="idx" else t) for nm,a,t in SIGNALS]
    a=assignment(rhs=element(symbol("p"),ref("idx",30,"logic")))
    edges,d,_=expand(a,sig)
    assert d["indices"]==[0,1] and len(edges)==16

def test_nonzero_bounds_and_out_of_range():
    sig=[(nm,a,"logic[3:1][3:0]" if nm=="p" else t) for nm,a,t in SIGNALS]
    a=assignment(rhs=element(ref("p",10,"logic[3:1][3:0]")))
    edges,d,_=expand(a,sig)
    assert d["indices"]==[1,2,3] and d["numeric_out_of_range_possible"] and len(edges)==36

def test_ascending_lanes_and_fixed_range():
    sig=[(nm,a,"logic[0:3][0:3]" if nm=="p" else "logic[1:0]" if nm=="q" else t) for nm,a,t in SIGNALS]
    rhs=n("RangeSelect",type="logic[1:2]",selectionKind="Simple",
          value=element(ref("p",10,"logic[0:3][0:3]"),typ="logic[0:3]"),left=num(1),right=num(2))
    a=assignment(lhs=ref("q",40,"logic[1:0]"),rhs=rhs,typ="logic[1:0]")
    edges,d,_=expand(a,sig)
    assert d["declared_bounds"]==[0,3]
    assert [(e["source_bit"],e["target_bit"]) for e in edges_of(edges,"index_data_candidate",0)]==[(2,0),(1,1)]

@pytest.mark.parametrize("mode",["two_sides","two_dimensions","signed","unknown_type","wrong_identity",
    "wrong_selection_type","aggregate","indexed_part","opaque_selector","constant_unproven","wrong_assignment_type",
    "compound","timed","wrong_data_width","no_dynamic","out_of_bounds_fixed"])
def test_refuse_unproven(mode):
    a=assignment()
    if mode=="two_sides": a["left"]=element(symbol("u"))
    elif mode=="two_dimensions":
        a=assignment(lhs=symbol("s"),rhs=element(element(symbol("p")),symbol("idx2"),"logic"),typ="logic")
    elif mode=="signed": a["right"]["selector"]["type"]="logic signed[1:0]"
    elif mode=="unknown_type": a["right"]["selector"]["type"]="index_t"
    elif mode=="wrong_identity": a["right"]["selector"]["symbol"]="999 idx"
    elif mode=="wrong_selection_type": a["right"]["type"]="logic[2:0]"
    elif mode=="aggregate": a["right"]=symbol("p")
    elif mode=="indexed_part": a["right"]=n("RangeSelect",type="logic[3:0]",selectionKind="IndexedUp",value=symbol("d"),left=symbol("idx"),right=num(4))
    elif mode=="opaque_selector": a["right"]["selector"]=n("Call",type="logic[1:0]",subroutine="f")
    elif mode=="constant_unproven": a["right"]["selector"]=n("IntegerLiteral",type="logic[1:0]",value="2'bxx")
    elif mode=="wrong_assignment_type": a["type"]="logic[2:0]"
    elif mode=="compound": a["op"]="Add"
    elif mode=="timed": a["timingControl"]={}
    elif mode=="wrong_data_width": a["left"]=symbol("s"); a["type"]="logic"
    elif mode=="no_dynamic": a["right"]["selector"]=num(2)
    elif mode=="out_of_bounds_fixed": a["right"]["selector"]=num(4)
    with pytest.raises(Unsupported): expand(a)

def test_previous_channels_unchanged():
    a=assignment()
    old,new=graph(a,False),graph(a)
    excluded={"dynamic_dependencies","analysis_limits"}
    assert {k:v for k,v in old.items() if k not in excluded}=={k:v for k,v in new.items() if k not in excluded}
    d=new["dynamic_dependencies"]
    assert d["counts"]=={"captured":1,"supported":1,"partial":0,"edges":48,"truncated":False}
    assert d["items"][0]["flat_assignment_id"]==0

@pytest.mark.parametrize("limit,value,reason",[("MAX_CHOICES",3,"choice_budget_exceeded"),
    ("MAX_ROW_PAIRS",47,"row_pair_budget"),("MAX_EDGES",47,"edge_budget_exceeded")])
def test_atomic_budget(monkeypatch,limit,value,reason):
    monkeypatch.setattr(dyn,limit,value)
    g=graph(assignment())
    d=g["dynamic_dependencies"]
    assert d["counts"]["truncated"] and not d["edges"]
    assert d["items"][0]["reason"]==reason and "alternatives" not in d["items"][0]
    assert "dynamic_dependencies" in g["analysis_limits"]["truncated_analyzers"]

def test_legacy_graph_inventory_readable():
    from rtlprep.analysis_budgets import analyzer_summary
    g=graph(assignment())
    g.pop("dynamic_dependencies")
    assert len(analyzer_summary(g)["analyzers"])==12

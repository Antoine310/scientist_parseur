import copy
import pytest
from rtlprep.array_dependencies import layout
from rtlprep.localparam_range_concat_candidates import expand,range_model,historical_agreement,Unsupported


def setup(lo=15):
    typ="logic signed[31:0]"
    def named(n,t,a):
        return {"kind":"NamedValue","type":t,"symbol":f"{a} {n}"}
    def param(n,a,v):
        return {"kind":"Parameter","name":n,"addr":a,"type":typ,"value":str(v),
                "isLocal":True,"isPort":False,"isBody":True,
                "initializer":{"kind":"Conversion","type":typ,
                    "operand":{"kind":"IntegerLiteral","type":"int","value":str(v)}}}
    hi=lo+4
    part={"kind":"RangeSelect","type":f"logic[{hi}:{lo}]","selectionKind":"Simple",
          "value":named("instr","logic[31:0]",2),
          "left":{**named("HI",typ,10),"constant":str(hi)},
          "right":{**named("LO",typ,11),"constant":str(lo)}}
    node={"kind":"Assignment","type":"logic[5:0]","isNonBlocking":False,
          "left":named("dst","logic[5:0]",1),
          "right":{"kind":"Concatenation","type":"logic[5:0]",
                   "operands":[named("fp","logic",3),part]}}
    raw={"top.dst":"logic[5:0]","top.instr":"logic[31:0]","top.fp":"logic"}
    resolve=lambda owner,e:{"1 dst":"top.dst","2 instr":"top.instr","3 fp":"top.fp"}.get(e.get("symbol"))
    inv=({"top":None},{"10":("top",param("HI",10,hi)),"11":("top",param("LO",11,lo))})
    return [node,"AlwaysComb","top",resolve,raw,{n:layout(t) for n,t in raw.items()},inv]


@pytest.mark.parametrize("lo",[0,7,15,20,27])
@pytest.mark.parametrize("context",["continuous","AlwaysComb"])
def test_positive(lo,context):
    a=setup(lo); a[1]=context; old=copy.deepcopy(a[0]); x=expand(*a)
    assert x["model"]==range_model(lo+4,lo)
    assert x["pairs"]==[{"source":"top.instr","source_bit":lo+j,"target":"top.dst","target_bit":j}
                         for j in range(5)]+[{"source":"top.fp","source_bit":0,"target":"top.dst","target_bit":5}]
    assert x["bounds"]==[{"instance":"top","parameter":n,"value":v,"method":"direct_typed_literal_localparam"}
                          for n,v in [("HI",lo+4),("LO",lo)]]
    assert a[0]==old and x["potential_pairs"]==6


@pytest.mark.parametrize("hi,lo",[(4,-1),(32,28),(3,5),(6,0),(True,0),(4,False)])
def test_bounds(hi,lo):
    with pytest.raises(Unsupported): range_model(hi,lo)


BAD=["context","nba","timing","compound","order","arity","result_width","part_type","part_kind",
     "scalar_type","base_type","bound_kind","bound_type","bound_identity","bound_name","bound_tag",
     "bound_runtime","decl_owner","decl_local","decl_port","decl_body","decl_missing","decl_value",
     "init_kind","init_type","init_tag","init_unknown","init_oob","range_width","runtime_tag",
     "target_identity","raw_layout","declared_layout"]


@pytest.mark.parametrize("bad",BAD)
def test_refusals(bad):
    a=setup(); n=a[0]; rhs=n["right"]; scalar,part=rhs["operands"]; ref=part["left"]
    decl=a[6][1]["10"][1]; init=decl["initializer"]
    if bad=="context": a[1]="AlwaysFF"
    elif bad=="nba": n["isNonBlocking"]=True
    elif bad=="timing": n["timingControl"]={}
    elif bad=="compound": n["op"]="Add"
    elif bad=="order": rhs["operands"].reverse()
    elif bad=="arity": rhs["operands"].append(scalar)
    elif bad=="result_width": rhs["type"]="logic[6:0]"
    elif bad=="part_type": part["type"]="logic[4:0]"
    elif bad=="part_kind": part["selectionKind"]="IndexedUp"
    elif bad=="scalar_type": scalar["type"]="bit"
    elif bad=="base_type": part["value"]["type"]="logic[63:0]"
    elif bad=="bound_kind": ref["kind"]="IntegerLiteral"
    elif bad=="bound_type": ref["type"]="int"
    elif bad=="bound_identity": ref["symbol"]="99 HI"
    elif bad=="bound_name": ref["symbol"]="10 WRONG"
    elif bad=="bound_tag": ref["constant"]="20"
    elif bad=="bound_runtime": a[3]=lambda o,e:"top.signal"
    elif bad=="decl_owner": a[6][1]["10"]=("other",decl)
    elif bad=="decl_local": decl["isLocal"]=False
    elif bad=="decl_port": decl["isPort"]=True
    elif bad=="decl_body": decl["isBody"]=False
    elif bad=="decl_missing": del a[6][1]["10"]
    elif bad=="decl_value": decl["value"]="20"
    elif bad=="init_kind": init["kind"]="NamedValue"
    elif bad=="init_type": init["operand"]["type"]="logic"
    elif bad=="init_tag": init["constant"]="20"
    elif bad=="init_unknown": init["operand"]["value"]="32'bx"
    elif bad=="init_oob": init["operand"]["value"]="32"
    elif bad=="range_width":
        init["operand"]["value"]=decl["value"]=ref["constant"]="20"
    elif bad=="runtime_tag": part["constant"]="5'd0"
    elif bad=="target_identity": n["left"]["symbol"]="99 dst"
    elif bad=="raw_layout": a[4]["top.instr"]="logic[63:0]"
    elif bad=="declared_layout": a[5]["top.instr"]=layout("logic[63:0]")
    with pytest.raises(Unsupported): expand(*a)


@pytest.mark.parametrize("supported",[False,True])
def test_historical_agreement(supported):
    x=expand(*setup())
    hist={"coverage":"assignment_local_position_candidates" if supported else "partial",
          "edge_count":6 if supported else 0,"constant_target_bits":[]}
    edges=[{**p,"value_transform":"position_only","assignment_id":2} for p in x["pairs"]] if supported else []
    assert historical_agreement(x,hist,list(reversed(edges)),2)==6*supported


@pytest.mark.parametrize("bad",["bit","target","transform","duplicate","missing","constant","partial"])
def test_historical_refusal(bad):
    x=expand(*setup())
    hist={"coverage":"assignment_local_position_candidates","edge_count":6,"constant_target_bits":[]}
    edges=[{**p,"value_transform":"position_only","assignment_id":2} for p in x["pairs"]]
    if bad=="bit": edges[0]["source_bit"]=0
    elif bad=="target": edges[0]["target"]="other"
    elif bad=="transform": edges[0]["value_transform"]="invert"
    elif bad=="duplicate": edges[-1]=edges[0]
    elif bad=="missing": edges.pop()
    elif bad=="constant": hist["constant_target_bits"]=[0]
    elif bad=="partial": hist.update(coverage="partial",edge_count=0)
    with pytest.raises(Unsupported): historical_agreement(x,hist,edges,2)


@pytest.mark.parametrize("supported",[False,True])
def test_report_contract(monkeypatch,supported):
    import rtlprep.localparam_range_concat_candidates as m
    from types import SimpleNamespace
    a=setup(); n=a[0]; x=expand(*a)
    occ={"ast_path":"/node","instance":"top","context":"AlwaysComb","source":{},
         "historical_status":"captured","flat_assignment_id":0}
    access={"items":[{"target_selection":{"kind":"whole"}}]}
    hist={"target":"top.dst","coverage":"assignment_local_position_candidates" if supported else "partial",
          "edge_count":6 if supported else 0,"constant_target_bits":[]}
    edges=[{**p,"value_transform":"position_only","assignment_id":0} for p in x["pairs"]] if supported else []
    graph={"bit_accesses":access,"bit_dependency_graph":{"items":[hist],"edges":edges}}
    monkeypatch.setattr(m,"audit_capture",lambda *x:{"items":[occ],"counts":{"ast_occurrences":1,"historical_rows":1}})
    monkeypatch.setattr(m,"exact_links",lambda *x:(None,None,set() if supported else {0},None,None,None))
    def replay(*x,**kw):
        kw["captured_assignments"].append((0,access["items"][0],n,"top",{},False))
        return access
    monkeypatch.setattr(m,"build_bit_access_index",replay)
    monkeypatch.setattr(m,"reconcile_capture",lambda *x:{0:(n,"top",False)})
    monkeypatch.setattr(m,"SignalResolver",lambda *x:SimpleNamespace(resolve_exact=a[3]))
    monkeypatch.setattr(m,"raw_layouts",lambda *x:a[4])
    monkeypatch.setattr(m,"layouts",lambda *x:a[5])
    monkeypatch.setattr(m,"inventory",lambda *x:a[6])
    r=m.audit_localparam_range_concat({"node":n},{"top":"top"},graph)
    c=r["counts"]
    assert len(r["items"])==c["roots"]==c["supported"]==1
    assert c["potential_pairs"]==6 and c["matched_historical_edges"]==6*supported
    assert c["residual_candidate_pairs"]==6*(not supported)
    monkeypatch.setattr(m,"MAX_COORDINATES",5)
    with pytest.raises(ValueError,match="budget"): m.audit_localparam_range_concat({"node":n},{"top":"top"},graph)

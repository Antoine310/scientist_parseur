import copy
import pytest
from rtlprep.array_dependencies import layout
from rtlprep.arithmetic_range_candidates import expand,range_model,historical_agreement,Unsupported


def setup(case="upper"):
    typ="logic signed[31:0]"
    def named(n,t,a):
        return {"kind":"NamedValue","type":t,"symbol":f"{a} {n}"}
    def lit(v):
        return {"kind":"IntegerLiteral","type":"int","value":str(v)}
    def conv(v):
        return {"kind":"Conversion","type":typ,"operand":lit(v)}
    def param(n,a,v):
        return {"kind":"Parameter","name":n,"addr":a,"type":typ,"value":str(v),
                "isLocal":True,"isPort":False,"isBody":True,"initializer":conv(v)}
    def binary(op,left,right):
        return {"kind":"BinaryOp","type":typ,"op":op,"left":left,"right":right}
    flags=named("C_FFLAG",typ,10); rm=named("C_RM",typ,11)
    if case=="upper":
        hi,lo=7,5; upper=binary("Add",rm,flags); lower=copy.deepcopy(flags)
    elif case=="flags":
        hi,lo=4,0; upper=flags; lower=lit(0)
    else:
        hi,lo=2,0; upper=rm; lower=lit(0)
    width=hi-lo+1; dst=f"logic[{width-1}:0]"
    rhs={"kind":"RangeSelect","type":f"logic[{hi}:{lo}]","selectionKind":"Simple",
         "value":named("src","logic[31:0]",2),"left":binary("Subtract",upper,conv(1)),"right":lower}
    node={"kind":"Assignment","type":dst,"isNonBlocking":False,
          "left":named("dst",dst,1),"right":rhs}
    raw={"top.dst":dst,"top.src":"logic[31:0]"}
    resolve=lambda owner,e:{"1 dst":"top.dst","2 src":"top.src"}.get(e.get("symbol")) if owner=="top" else None
    inv=({"top":None},{"10":("top",param("C_FFLAG",10,5)),"11":("top",param("C_RM",11,3))})
    return [node,"AlwaysComb","top",resolve,raw,{n:layout(t) for n,t in raw.items()},inv]


@pytest.mark.parametrize("case,hi,lo",[("flags",4,0),("rm",2,0),("upper",7,5)])
@pytest.mark.parametrize("context",["AlwaysComb","continuous"])
def test_positive(case,hi,lo,context):
    a=setup(case); a[1]=context; before=copy.deepcopy(a[0]); x=expand(*a)
    assert x["model"]==range_model(hi,lo)
    assert x["pairs"]==[{"source":"top.src","source_bit":b,"target":"top.dst","target_bit":b-lo}
                        for b in range(lo,hi+1)]
    assert x["bound_proofs"]["msb"]["kind"]=="Subtract"
    assert x["bound_proofs"]["msb"]["value"]==hi and x["bound_proofs"]["lsb"]["value"]==lo
    assert {p["parameter"]:p["value"] for p in x["parameter_proofs"]}==(
        {"C_FFLAG":5,"C_RM":3} if case=="upper" else {"C_FFLAG":5} if case=="flags" else {"C_RM":3})
    assert x["permanent_constant"]=="not_inferred" and a[0]==before


@pytest.mark.parametrize("hi,lo",[(4,-1),(32,28),(3,5),(6,0),(True,0),(4,False),(0,0)])
def test_range_refusal(hi,lo):
    with pytest.raises(Unsupported): range_model(hi,lo)


BAD=["context","nba","timing","compound","lhs_type","rhs_type","source_type","source_kind",
     "range_kind","runtime_tag","target_tag","source_tag","operator","op_type","child_type",
     "nested_op","nested_type","nested_tag","upper_tag","literal_type","literal_kind","literal_tag",
     "conversion_kind","conversion_type","conversion_tag","negative","intermediate","parameter_type",
     "parameter_identity","parameter_name","parameter_tag","parameter_owner","parameter_local",
     "parameter_port","parameter_body","parameter_value","parameter_init","parameter_init_tag",
     "lower_tag","lower_kind","no_parameters","out_of_bounds","width_mismatch","source_identity",
     "target_identity","raw_layout","declared_layout"]


@pytest.mark.parametrize("bad",BAD)
def test_refusal(bad):
    a=setup(); n=a[0]; rhs=n["right"]; hi=rhs["left"]; add=hi["left"]; conv=hi["right"]
    prm=add["right"]; decl=a[6][1]["10"][1]
    if bad=="context": a[1]="AlwaysFF"
    elif bad=="nba": n["isNonBlocking"]=True
    elif bad=="timing": n["timingControl"]={}
    elif bad=="compound": n["op"]="Add"
    elif bad=="lhs_type": n["left"]["type"]="logic[4:0]"
    elif bad=="rhs_type": rhs["type"]="logic[2:0]"
    elif bad=="source_type": rhs["value"]["type"]="logic[63:0]"
    elif bad=="source_kind": rhs["value"]["kind"]="Call"
    elif bad=="range_kind": rhs["selectionKind"]="IndexedUp"
    elif bad=="runtime_tag": rhs["constant"]="3'd0"
    elif bad=="target_tag": n["left"]["constant"]="3'd0"
    elif bad=="source_tag": rhs["value"]["constant"]="32'd0"
    elif bad=="operator": hi["op"]="Multiply"
    elif bad=="op_type": hi["type"]="logic[31:0]"
    elif bad=="child_type": conv["type"]="int"
    elif bad=="nested_op": add["op"]="Power"
    elif bad=="nested_type": add["type"]="int"
    elif bad=="nested_tag": add["constant"]="9"
    elif bad=="upper_tag": hi["constant"]="8"
    elif bad=="literal_type": conv["operand"]["type"]="logic"
    elif bad=="literal_kind": conv["operand"]["kind"]="Call"
    elif bad=="literal_tag": conv["operand"]["constant"]="2"
    elif bad=="conversion_kind": conv["kind"]="SignedConversion"
    elif bad=="conversion_type": conv["type"]="logic[31:0]"
    elif bad=="conversion_tag": conv["constant"]="2"
    elif bad=="negative": conv["operand"]["value"]="9"
    elif bad=="intermediate":
        add["left"]=copy.deepcopy(conv); add["left"]["operand"]["value"]="64"
    elif bad=="parameter_type": prm["type"]="int"
    elif bad=="parameter_identity": prm["symbol"]="99 C_FFLAG"
    elif bad=="parameter_name": prm["symbol"]="10 WRONG"
    elif bad=="parameter_tag": prm["constant"]="6"
    elif bad=="parameter_owner": a[6][1]["10"]=("other",decl)
    elif bad=="parameter_local": decl["isLocal"]=False
    elif bad=="parameter_port": decl["isPort"]=True
    elif bad=="parameter_body": decl["isBody"]=False
    elif bad=="parameter_value": decl["value"]="6"
    elif bad=="parameter_init": decl["initializer"]["operand"]["kind"]="Call"
    elif bad=="parameter_init_tag": decl["initializer"]["constant"]="6"
    elif bad=="lower_tag": rhs["right"]["constant"]="6"
    elif bad=="lower_kind": rhs["right"]["kind"]="Call"
    elif bad=="no_parameters":
        for k in ("left","right"): add[k]=copy.deepcopy(conv)
        rhs["right"]={"kind":"IntegerLiteral","type":"int","value":"0"}
    elif bad=="out_of_bounds":
        decl["value"]=decl["initializer"]["operand"]["value"]="31"
    elif bad=="width_mismatch": conv["operand"]["value"]="2"
    elif bad=="source_identity": rhs["value"]["symbol"]="99 src"
    elif bad=="target_identity": n["left"]["symbol"]="99 dst"
    elif bad=="raw_layout": a[4]["top.src"]="logic[63:0]"
    elif bad=="declared_layout": a[5]["top.src"]=layout("logic[63:0]")
    with pytest.raises(Unsupported): expand(*a)


def test_corroborated_tags():
    a=setup(); r=a[0]["right"]
    r["left"]["constant"]="7"; r["left"]["left"]["constant"]="8"; r["right"]["constant"]="5"
    assert expand(*a)["potential_pairs"]==3


@pytest.mark.parametrize("limit",["MAX_BOUND_DEPTH","MAX_BOUND_NODES","MAX_REFERENCES"])
def test_bound_budget(monkeypatch,limit):
    import rtlprep.arithmetic_range_candidates as m
    monkeypatch.setattr(m,limit,1)
    with pytest.raises(ValueError,match="budget"): expand(*setup())


@pytest.mark.parametrize("supported",[False,True])
def test_historical_agreement(supported):
    x=expand(*setup())
    hist={"coverage":"assignment_local_position_candidates" if supported else "partial",
          "edge_count":3 if supported else 0,"constant_target_bits":[]}
    edges=[{**p,"value_transform":"position_only","assignment_id":2} for p in x["pairs"]] if supported else []
    assert historical_agreement(x,hist,list(reversed(edges)),2)==3*supported


@pytest.mark.parametrize("bad",["edge","duplicate","constant","unexpected_partial"])
def test_historical_refusal(bad):
    x=expand(*setup())
    hist={"coverage":"assignment_local_position_candidates","edge_count":3,"constant_target_bits":[]}
    edges=[{**p,"value_transform":"position_only","assignment_id":2} for p in x["pairs"]]
    if bad=="edge": edges[0]["source_bit"]=0
    elif bad=="duplicate": edges[2]=edges[0]
    elif bad=="constant": hist["constant_target_bits"]=[0]
    else: hist.update(coverage="partial",edge_count=0)
    with pytest.raises(Unsupported): historical_agreement(x,hist,edges,2)


@pytest.mark.parametrize("supported",[False,True])
def test_report_contract(monkeypatch,supported):
    import rtlprep.arithmetic_range_candidates as m
    from types import SimpleNamespace
    a=setup(); n=a[0]; x=expand(*a)
    occ={"ast_path":"/node","instance":"top","context":"AlwaysComb","source":{},
         "historical_status":"captured","flat_assignment_id":0}
    access={"items":[{"target_selection":{"kind":"whole"}}]}
    hist={"target":"top.dst","coverage":"assignment_local_position_candidates" if supported else "partial",
          "edge_count":3 if supported else 0,"constant_target_bits":[]}
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
    r=m.audit_arithmetic_range({"node":n},{"top":"top"},graph)
    c=r["counts"]
    assert len(r["items"])==c["roots"]==c["supported"]==1
    assert c["potential_pairs"]==3 and c["matched_historical_edges"]==3*supported
    assert c["residual_candidate_pairs"]==3*(not supported)
    monkeypatch.setattr(m,"MAX_COORDINATES",2)
    with pytest.raises(ValueError,match="budget"): m.audit_arithmetic_range({"node":n},{"top":"top"},graph)

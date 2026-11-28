import copy
import pytest
from rtlprep.array_dependencies import layout
from rtlprep.parameter_mux_candidates import expand,inventory,mux_model,parameter_chain,Unsupported


def setup(v=0,lane=1):
    typ="logic signed[31:0]"
    word="logic[31:0]"
    def named(name,kind,addr):
        return {"kind":"NamedValue","type":kind,"symbol":f"{addr} {name}"}
    def param(name,addr,init):
        return {"kind":"Parameter","name":name,"addr":addr,"type":typ,"value":str(v),
                "isPort":True,"isLocal":False,"isBody":False,"initializer":init}
    root=param("ROOT",10,{"kind":"Conversion","type":typ,
                          "operand":{"kind":"IntegerLiteral","type":"int","value":str(v)}})
    child=param("CFG",11,{**named("ROOT",typ,10),"constant":str(v)})
    cond={"expr":{"kind":"UnaryOp","type":"logic","op":"LogicalNot",
                  "operand":{**named("CFG",typ,11),"constant":str(v)},"constant":f"1'b{1-v}"}}
    alt={"kind":"ElementSelect","type":word,"value":named("data","logic[1:0][31:0]",2),
         "selector":{"kind":"IntegerLiteral","type":"int","value":str(lane)}}
    zero={"kind":"Conversion","type":word,"operand":{"kind":"IntegerLiteral","type":"bit[31:0]","value":"32'd0"}}
    node={"kind":"Assignment","type":word,"isNonBlocking":False,"left":named("dst",word,1),
          "right":{"kind":"ConditionalOp","type":word,"conditions":[cond],"left":zero,"right":alt}}
    raw={"top.u.dst":word,"top.u.data":"logic[1:0][31:0]"}
    resolve=lambda owner,e:{"1 dst":"top.u.dst","2 data":"top.u.data"}.get(e.get("symbol")) if owner=="top.u" else None
    inv=({"top":None,"top.u":"top"},{ "10":("top",root),"11":("top.u",child)})
    return [node,"AlwaysComb","top.u",resolve,raw,{n:layout(t) for n,t in raw.items()},inv]


@pytest.mark.parametrize("v",[0,1])
@pytest.mark.parametrize("lane",[0,1])
def test_positive(v,lane):
    a=setup(v,lane); before=copy.deepcopy(a[0]); x=expand(*a)
    assert x["model"]==mux_model(v,lane)
    assert x["parameter_chain"]==[{"instance":"top.u","parameter":"CFG","method":"immediate_parent_reference"},
                                  {"instance":"top","parameter":"ROOT","method":"typed_literal_initializer"}]
    pairs=[{"source":"top.u.data","source_packed_indices":[lane],"source_bit":b,
            "target":"top.u.dst","target_bit":b} for b in range(32)]
    assert x["pairs"]==(pairs if v else [])
    assert x["alternative_positions"]==([] if v else pairs)
    assert x["local_values"]==([] if v else [{"target":"top.u.dst","target_bit":b,"value":0} for b in range(32)])
    assert x["potential_pairs"]==32*v and x["permanent_constant"]=="not_inferred"
    assert a[0]==before


@pytest.mark.parametrize("v,lane",[(2,0),(-1,1),(True,0),(0,2),(0,-1),(1,True)])
def test_model_bounds(v,lane):
    with pytest.raises(Unsupported): mux_model(v,lane)


BAD=["context","nba","compound","type","pattern","condition_tag","condition_type","reference_tag",
     "reference_identity","reference_name","reference_type","runtime_reference","parameter_owner",
     "parameter_local","parameter_not_port","parameter_body","parameter_missing","parameter_decl_value",
     "parameter_init_type","parent_identity","parent_wrong_owner","parent_tag","terminal_value",
     "terminal_kind","terminal_type","zero_nonzero","zero_unknown","zero_tag","zero_type",
     "alt_layout","alt_index","alt_dynamic","alt_tag","target_identity","raw_layout","declared_layout"]


@pytest.mark.parametrize("bad",BAD)
def test_refusals(bad):
    a=setup(); node=a[0]; rhs=node["right"]; test=rhs["conditions"][0]["expr"]; ref=test["operand"]
    root=a[6][1]["10"][1]; child=a[6][1]["11"][1]
    zero=rhs["left"]; alt=rhs["right"]
    if bad=="context": a[1]="AlwaysFF"
    elif bad=="nba": node["isNonBlocking"]=True
    elif bad=="compound": node["op"]="Add"
    elif bad=="type": rhs["type"]="logic[30:0]"
    elif bad=="pattern": rhs["conditions"][0]["pattern"]={}
    elif bad=="condition_tag": test["constant"]="1'b0"
    elif bad=="condition_type": test["type"]="bit"
    elif bad=="reference_tag": ref["constant"]="1"
    elif bad=="reference_identity": ref["symbol"]="99 CFG"
    elif bad=="reference_name": ref["symbol"]="11 WRONG"
    elif bad=="reference_type": ref["type"]="int"
    elif bad=="runtime_reference": a[3]=lambda owner,e:"top.u.signal"
    elif bad=="parameter_owner": a[6][1]["11"]=("top",child)
    elif bad=="parameter_local": child["isLocal"]=True
    elif bad=="parameter_not_port": child["isPort"]=False
    elif bad=="parameter_body": child["isBody"]=True
    elif bad=="parameter_missing": del a[6][1]["11"]
    elif bad=="parameter_decl_value": child["value"]="1"
    elif bad=="parameter_init_type": child["initializer"]["type"]="int"
    elif bad=="parent_identity": child["initializer"]["symbol"]="99 ROOT"
    elif bad=="parent_wrong_owner": a[6][1]["10"]=("top.u",root)
    elif bad=="parent_tag": child["initializer"]["constant"]="1"
    elif bad=="terminal_value": root["initializer"]["operand"]["value"]="2"
    elif bad=="terminal_kind": root["initializer"]["operand"]["kind"]="Call"
    elif bad=="terminal_type": root["initializer"]["operand"]["type"]="logic"
    elif bad=="zero_nonzero": zero["operand"]["value"]="32'd1"
    elif bad=="zero_unknown": zero["operand"]["value"]="32'bx"
    elif bad=="zero_tag": zero["constant"]="32'd1"
    elif bad=="zero_type": zero["operand"]["type"]="logic[31:0]"
    elif bad=="alt_layout": alt["value"]["type"]="logic[31:0][1:0]"
    elif bad=="alt_index": alt["selector"]["value"]="2"
    elif bad=="alt_dynamic": alt["selector"]["kind"]="NamedValue"
    elif bad=="alt_tag": alt["constant"]="32'd0"
    elif bad=="target_identity": node["left"]["symbol"]="99 dst"
    elif bad=="raw_layout": a[4]["top.u.data"]="logic[63:0]"
    elif bad=="declared_layout": a[5]["top.u.data"]=layout("logic[63:0]")
    with pytest.raises(Unsupported): expand(*a)


def ast_for_inventory():
    a=setup()
    root=a[6][1]["10"][1]; child=a[6][1]["11"][1]
    return {"design":{"members":[{"kind":"Instance","name":"top","body":{"members":[root,
        {"kind":"Instance","name":"u","body":{"members":[child]}}]}}]}}


def test_inventory_exact():
    a=setup(); inv=inventory(ast_for_inventory())
    assert inv==a[6]


def test_inventory_duplicate_address():
    ast=ast_for_inventory(); members=ast["design"]["members"][0]["body"]["members"]
    members.append(copy.deepcopy(members[0]))
    inv=inventory(ast)
    assert "10" not in inv[1]
    a=setup(); a[6]=inv
    with pytest.raises(Unsupported): expand(*a)


def test_inventory_no_generate_lookup():
    ast=ast_for_inventory(); members=ast["design"]["members"][0]["body"]["members"]
    members[1]={"kind":"GenerateBlock","members":[members[1]]}
    assert inventory(ast)[0]=={"top":None}


def test_inventory_budget(monkeypatch):
    import rtlprep.parameter_mux_candidates as m
    monkeypatch.setattr(m,"MAX_MEMBERS",1)
    with pytest.raises(ValueError,match="budget"): inventory(ast_for_inventory())


def test_chain_budget(monkeypatch):
    import rtlprep.parameter_mux_candidates as m
    monkeypatch.setattr(m,"MAX_CHAIN",1)
    with pytest.raises(ValueError,match="budget"): expand(*setup())


@pytest.mark.parametrize("v",[0,1])
def test_report_contract(monkeypatch,v):
    import rtlprep.parameter_mux_candidates as m
    from types import SimpleNamespace
    a=setup(v); n=a[0]; ast={"node":n}
    occ={"ast_path":"/node","instance":"top.u","context":"AlwaysComb","source":{},
         "historical_status":"captured","flat_assignment_id":0}
    access={"items":[{"target_selection":{"kind":"whole"}}]}
    graph={"bit_accesses":access,"bit_dependency_graph":{"items":[{"target":"top.u.dst"}]}}
    monkeypatch.setattr(m,"audit_capture",lambda *x:{"items":[occ],"counts":{"ast_occurrences":1,"historical_rows":1}})
    monkeypatch.setattr(m,"exact_links",lambda *x:(None,None,{0},None,None,None))
    def replay(*x,**kw):
        kw["captured_assignments"].append((0,access["items"][0],n,"top.u",{},False))
        return access
    monkeypatch.setattr(m,"build_bit_access_index",replay)
    monkeypatch.setattr(m,"reconcile_capture",lambda *x:{0:(n,"top.u",False)})
    monkeypatch.setattr(m,"SignalResolver",lambda *x:SimpleNamespace(resolve_exact=a[3]))
    monkeypatch.setattr(m,"raw_layouts",lambda *x:a[4])
    monkeypatch.setattr(m,"layouts",lambda *x:a[5])
    monkeypatch.setattr(m,"inventory",lambda *x:a[6])
    r=m.audit_parameter_mux(ast,{"top":"top"},graph)
    assert len(r["items"])==r["counts"]["roots"]==r["counts"]["supported_residual"]==1
    assert r["counts"]["potential_pairs"]==32*v
    assert r["counts"]["local_value_records"]==r["counts"]["inactive_alternative_positions"]==32*(1-v)
    assert r["counts"]["stored_coordinates"]==64-32*v
    monkeypatch.setattr(m,"MAX_COORDINATES",1)
    with pytest.raises(ValueError,match="budget"): m.audit_parameter_mux(ast,{"top":"top"},graph)

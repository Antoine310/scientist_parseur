import copy
import pytest
from rtlprep.array_dependencies import layout
from rtlprep.parameter_concat_mux_candidates import expand,concat_mux_model,Unsupported


def setup(v=0,widths=(3,5)):
    typ="logic signed[31:0]"; word="logic[31:0]"
    def named(n,t,a):
        return {"kind":"NamedValue","type":t,"symbol":f"{a} {n}"}
    def param(n,a,init):
        return {"kind":"Parameter","name":n,"addr":a,"type":typ,"value":str(v),
                "isLocal":False,"isPort":True,"isBody":False,"initializer":init}
    root=param("ROOT",10,{"kind":"Conversion","type":typ,"operand":{"kind":"IntegerLiteral","type":"int","value":str(v)}})
    child=param("FPU",11,{**named("ROOT",typ,10),"constant":str(v)})
    test={"kind":"BinaryOp","op":"Equality","type":"logic","left":{**named("FPU",typ,11),"constant":str(v)},
          "right":{"kind":"Conversion","type":typ,"operand":{"kind":"IntegerLiteral","type":"int","value":"1"}},
          "constant":f"1'b{v}"}
    n=32-sum(widths)
    leaves=[named("frm" if w==3 else "flags",f"logic[{w-1}:0]",2 if w==3 else 3) for w in widths]
    concat={"kind":"Concatenation","type":word,"operands":[
        {"kind":"IntegerLiteral","type":f"bit[{n-1}:0]","value":f"{n}'d0"},*leaves]}
    zero={"kind":"UnbasedUnsizedIntegerLiteral","type":word,"value":"32'd0"}
    node={"kind":"Assignment","type":word,"isNonBlocking":False,"left":named("dst",word,1),
          "right":{"kind":"ConditionalOp","type":word,"conditions":[{"expr":test}],"left":concat,"right":zero}}
    raw={"top.u.dst":word,"top.u.frm":"logic[2:0]","top.u.flags":"logic[4:0]"}
    resolve=lambda owner,e:{"1 dst":"top.u.dst","2 frm":"top.u.frm","3 flags":"top.u.flags"}.get(e.get("symbol")) if owner=="top.u" else None
    inv=({"top":None,"top.u":"top"},{"10":("top",root),"11":("top.u",child)})
    return [node,"AlwaysComb","top.u",resolve,raw,{n:layout(t) for n,t in raw.items()},inv]


@pytest.mark.parametrize("v",[0,1])
@pytest.mark.parametrize("widths",[(5,),(3,),(3,5)])
def test_positive(v,widths):
    a=setup(v,widths); old=copy.deepcopy(a[0]); x=expand(*a)
    assert x["model"]==concat_mux_model(v,widths)
    offset=0; pairs=[]
    for w in reversed(widths):
        pairs.extend({"source":"top.u."+("frm" if w==3 else "flags"),"source_bit":b,
                      "target":"top.u.dst","target_bit":offset+b} for b in range(w))
        offset+=w
    zeros=lambda start:[{"target":"top.u.dst","target_bit":b,"value":0} for b in range(start,32)]
    assert x["pairs"]==(pairs if v else [])
    assert x["alternative_positions"]==([] if v else pairs)
    assert x["local_values"]==zeros(offset if v else 0)
    assert x["inactive_zero_prefix_values"]==([] if v else zeros(offset))
    assert x["potential_pairs"]==v*sum(widths) and a[0]==old
    assert x["parameter_chain"]==[{"instance":"top.u","parameter":"FPU","method":"immediate_parent_reference"},
                                  {"instance":"top","parameter":"ROOT","method":"typed_literal_initializer"}]
    assert x["permanent_constant"]=="not_inferred"


@pytest.mark.parametrize("v,widths",[(2,[5]),(True,[3]),(0,[]),(1,[5,3]),(1,[3,3]),(0,[True]),(0,[8]),(1,[5,5,5])])
def test_model_refusal(v,widths):
    with pytest.raises(Unsupported): concat_mux_model(v,widths)


BAD=["context","nba","timing","compound","result_type","pattern","condition_type","condition_op",
     "condition_tag","compare_kind","compare_type","compare_value","compare_tag","parameter_ref",
     "parameter_tag","parameter_owner","parameter_value","parameter_init","zero_kind","zero_type",
     "zero_nonzero","zero_x","zero_tag","prefix_kind","prefix_type","prefix_nonzero","prefix_x",
     "prefix_tag","operand_order","operand_arity","operand_type","operand_kind","operand_tag",
     "concat_tag","rhs_tag","target_tag","target_identity","source_identity","raw_layout","declared_layout"]


@pytest.mark.parametrize("bad",BAD)
def test_refusal(bad):
    a=setup(); n=a[0]; rhs=n["right"]; cond=rhs["conditions"][0]; test=cond["expr"]; cmp=test["right"]
    concat=rhs["left"]; prefix,frm,flags=concat["operands"]; zero=rhs["right"]
    root=a[6][1]["10"][1]; child=a[6][1]["11"][1]
    if bad=="context": a[1]="AlwaysFF"
    elif bad=="nba": n["isNonBlocking"]=True
    elif bad=="timing": n["timingControl"]={}
    elif bad=="compound": n["op"]="Add"
    elif bad=="result_type": rhs["type"]="logic[30:0]"
    elif bad=="pattern": cond["pattern"]={}
    elif bad=="condition_type": test["type"]="bit"
    elif bad=="condition_op": test["op"]="Inequality"
    elif bad=="condition_tag": test["constant"]="1'b1"
    elif bad=="compare_kind": cmp["operand"]["kind"]="Call"
    elif bad=="compare_type": cmp["type"]="logic[31:0]"
    elif bad=="compare_value": cmp["operand"]["value"]="0"
    elif bad=="compare_tag": cmp["constant"]="0"
    elif bad=="parameter_ref": test["left"]["symbol"]="99 FPU"
    elif bad=="parameter_tag": test["left"]["constant"]="1"
    elif bad=="parameter_owner": a[6][1]["11"]=("top",child)
    elif bad=="parameter_value": child["value"]="1"
    elif bad=="parameter_init": root["initializer"]["operand"]["value"]="2"
    elif bad=="zero_kind": zero["kind"]="IntegerLiteral"
    elif bad=="zero_type": zero["type"]="logic"
    elif bad=="zero_nonzero": zero["value"]="32'd1"
    elif bad=="zero_x": zero["value"]="32'bx"
    elif bad=="zero_tag": zero["constant"]="32'd1"
    elif bad=="prefix_kind": prefix["kind"]="UnbasedUnsizedIntegerLiteral"
    elif bad=="prefix_type": prefix["type"]="bit[24:0]"
    elif bad=="prefix_nonzero": prefix["value"]="24'd1"
    elif bad=="prefix_x": prefix["value"]="24'bx"
    elif bad=="prefix_tag": prefix["constant"]="24'd1"
    elif bad=="operand_order": concat["operands"]=[prefix,flags,frm]
    elif bad=="operand_arity": concat["operands"].append(flags)
    elif bad=="operand_type": frm["type"]="logic[3:0]"
    elif bad=="operand_kind": frm["kind"]="ElementSelect"
    elif bad=="operand_tag": frm["constant"]="3'd0"
    elif bad=="concat_tag": concat["constant"]="32'd0"
    elif bad=="rhs_tag": rhs["constant"]="32'd1"
    elif bad=="target_tag": n["left"]["constant"]="32'd0"
    elif bad=="target_identity": n["left"]["symbol"]="99 dst"
    elif bad=="source_identity": flags["symbol"]="99 flags"
    elif bad=="raw_layout": a[4]["top.u.frm"]="logic[3:0]"
    elif bad=="declared_layout": a[5]["top.u.frm"]=layout("logic[3:0]")
    with pytest.raises(Unsupported): expand(*a)


@pytest.mark.parametrize("v",[0,1])
def test_report_contract(monkeypatch,v):
    import rtlprep.parameter_concat_mux_candidates as m
    from types import SimpleNamespace
    a=setup(v); n=a[0]
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
    r=m.audit_parameter_concat_mux({"node":n},{"top":"top"},graph)
    c=r["counts"]
    assert len(r["items"])==c["roots"]==c["supported_residual"]==1
    assert c["potential_pairs"]==8*v and c["inactive_alternative_positions"]==8*(1-v)
    assert c["local_value_records"]==32-8*v and c["inactive_zero_prefix_records"]==24*(1-v)
    assert c["stored_coordinates"]==64-32*v
    monkeypatch.setattr(m,"MAX_COORDINATES",1)
    with pytest.raises(ValueError,match="budget"): m.audit_parameter_concat_mux({"node":n},{"top":"top"},graph)


def test_valid_zero_tags():
    a=setup(); r=a[0]["right"]
    r["constant"]="32'd0"; r["right"]["constant"]="32'd0"; r["left"]["operands"][0]["constant"]="24'd0"
    assert expand(*a)["potential_pairs"]==0

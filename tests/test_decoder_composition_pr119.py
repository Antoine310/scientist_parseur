import copy
from types import SimpleNamespace
import pytest
from rtlprep.decoder_composition_candidates import expand,decoder_model,Unsupported


def setup(k=7):
    def named(name,typ,addr):
        return {"kind":"NamedValue","type":typ,"symbol":f"{addr} {name}"}
    def conv(operand,typ):
        return {"kind":"Conversion","type":typ,"operand":operand}
    selector={**named("gidx","integer",4),"constant":str(k)}
    target=named("dec","logic[31:0]",1)
    addr=named("addr","logic[5:0]",2)
    enable=named("en","logic",3)
    lhs={"kind":"ElementSelect","type":"logic","value":target,"selector":selector}
    idx={**conv(copy.deepcopy(selector),"logic[31:0]"),"constant":f"32'd{k}"}
    eq={"kind":"BinaryOp","type":"logic","op":"Equality","left":conv(addr,"logic[31:0]"),"right":idx}
    zero=conv({"kind":"IntegerLiteral","type":"bit[0:0]","value":"1'b0","constant":"1'b0"},"logic")
    rhs={"kind":"ConditionalOp","type":"logic","conditions":[{"expr":eq}],"left":enable,"right":zero}
    node={"kind":"Assignment","isNonBlocking":False,"type":"logic","left":lhs,"right":rhs}
    return [node,"continuous",lambda e:{"1 dec":"dut.dec","2 addr":"dut.addr","3 en":"dut.en"}.get(e.get("symbol")),
            {"dut.dec":"logic[31:0]","dut.addr":"logic[5:0]","dut.en":"logic"},{"4":("gidx",k)}]


@pytest.mark.parametrize("k",[0,1,15,16,31])
def test_composition(k):
    a=setup(k); before=copy.deepcopy(a[0]); r=expand(*a)
    assert r["target"]=="dut.dec" and r["target_bit"]==k
    assert r["model"]==decoder_model(k) and r["potential_pairs"]==7
    assert [(p["source"],p["source_bit"],p["target_bit"]) for p in r["pairs"]]==[
        *(("dut.addr",b,k) for b in range(6)),("dut.en",0,k)]
    assert r["model_domain"]=="defined_binary_inputs_only"
    assert a[0]==before


@pytest.mark.parametrize("k",[-1,32,True,None])
def test_invalid_model(k):
    with pytest.raises(Unsupported): decoder_model(k)


@pytest.mark.parametrize("bad",["context","nba","compound","timing","target_type","result_type","selector_kind",
    "selector_missing","selector_tag","index_out_of_range","index_identity","index_tag","compare_op","compare_width",
    "address_width","address_signed","address_tag","address_identity","enable_type","enable_tag","enable_identity",
    "false_nonzero","false_unknown","false_tag","false_nested","conditional_pattern","runtime_tag","alias"])
def test_refusal(bad):
    a=setup(32 if bad=="index_out_of_range" else 7); n=a[0]; lhs=n["left"]; rhs=n["right"]
    eq=rhs["conditions"][0]["expr"]; addr=eq["left"]["operand"]; idx=eq["right"]; zero=rhs["right"]
    if bad=="context": a[1]="AlwaysComb"
    elif bad=="nba": n["isNonBlocking"]=True
    elif bad=="compound": n["op"]="Add"
    elif bad=="timing": n["timingControl"]={}
    elif bad=="target_type": lhs["value"]["type"]="logic[15:0]"
    elif bad=="result_type": n["type"]="bit"
    elif bad=="selector_kind": lhs["selector"]["kind"]="IntegerLiteral"
    elif bad=="selector_missing": a[4].clear()
    elif bad=="selector_tag": lhs["selector"]["constant"]="8"
    elif bad=="index_identity": idx["operand"]["symbol"]="9 gidx"
    elif bad=="index_tag": idx["constant"]="32'd8"
    elif bad=="compare_op": eq["op"]="Inequality"
    elif bad=="compare_width": eq["left"]["type"]="logic[15:0]"
    elif bad=="address_width": addr["type"]="logic[4:0]"
    elif bad=="address_signed": addr["type"]="logic signed[5:0]"
    elif bad=="address_tag": addr["constant"]="6'b0"
    elif bad=="address_identity": addr["symbol"]="9 addr"
    elif bad=="enable_type": rhs["left"]["type"]="bit"
    elif bad=="enable_tag": rhs["left"]["constant"]="1'b1"
    elif bad=="enable_identity": rhs["left"]["symbol"]="9 en"
    elif bad=="false_nonzero": zero["operand"]["value"]="1'b1"
    elif bad=="false_unknown": zero["operand"]["value"]="1'bx"
    elif bad=="false_tag": zero["constant"]="1'b1"
    elif bad=="false_nested": zero["operand"]["kind"]="Conversion"
    elif bad=="conditional_pattern": rhs["conditions"][0]["pattern"]={}
    elif bad=="runtime_tag": eq["constant"]="1'b0"
    elif bad=="alias":
        a[2]=lambda e:{"1 dec":"dut.dec","2 addr":"dut.addr","3 en":"dut.addr"}.get(e.get("symbol"))
    with pytest.raises(Unsupported): expand(*a)


@pytest.mark.parametrize("refused",[False,True])
def test_report_contract(monkeypatch,refused):
    import rtlprep.decoder_composition_candidates as m
    a=setup(); n=a[0]
    if refused: n["right"]["conditions"][0]["expr"]["right"]["constant"]="32'd8"
    ast={"node":n}
    occ={"ast_path":"/node","instance":"dut","context":"continuous","source":{},
         "historical_status":"captured","flat_assignment_id":0}
    access={"items":[{"target_selection":{"kind":"bit","index":7}}]}
    graph={"bit_accesses":access,"bit_dependency_graph":{"items":[{"target":"dut.dec"}]}}
    monkeypatch.setattr(m,"audit_capture",lambda *x:{"items":[occ],"counts":{"ast_occurrences":1,"historical_rows":1}})
    monkeypatch.setattr(m,"exact_links",lambda *x:(None,None,{0},None,None,None))
    def replay(*x,**kw):
        kw["captured_assignments"].append((0,access["items"][0],n,"dut",a[4],False))
        return access
    monkeypatch.setattr(m,"build_bit_access_index",replay)
    monkeypatch.setattr(m,"reconcile_capture",lambda *x:{0:(n,"dut",False)})
    monkeypatch.setattr(m,"SignalResolver",lambda *x:SimpleNamespace(resolve_exact=lambda owner,e:a[2](e)))
    monkeypatch.setattr(m,"raw_layouts",lambda *x:a[3])
    r=m.audit_decoder_composition(ast,{"top":"dut"},graph)
    assert len(r["items"])==r["counts"]["roots"]==1
    assert r["counts"]["partial"]==int(refused)
    assert r["counts"]["supported_residual"]==int(not refused)
    assert r["counts"]["potential_pairs"]==(0 if refused else 7)
    assert ("candidate" in r["items"][0])!=refused

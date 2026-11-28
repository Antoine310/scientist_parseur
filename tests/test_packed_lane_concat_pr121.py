import copy
from types import SimpleNamespace
import pytest
from rtlprep.array_dependencies import layout
from rtlprep.packed_lane_concat_candidates import expand,lane_model,Unsupported


def setup(k=3,b=16,v=1):
    def named(name,typ,addr):
        return {"kind":"NamedValue","type":typ,"symbol":f"{addr} {name}"}
    def sel(n,typ,i):
        return {"kind":"ElementSelect","type":typ,"value":n,
                "selector":{"kind":"IntegerLiteral","type":"int","value":str(i),"constant":str(i)}}
    lhs=sel(named("dst","logic[3:0][1:0]",1),"logic[1:0]",k)
    src=sel(named("src","logic[31:0]",2),"logic",b)
    literal={"kind":"IntegerLiteral","type":"bit[0:0]","value":f"1'b{v}"}
    rhs={"kind":"Concatenation","type":"logic[1:0]","operands":[src,literal]}
    node={"kind":"Assignment","type":"logic[1:0]","isNonBlocking":False,"left":lhs,"right":rhs}
    raw={"dut.dst":"logic[3:0][1:0]","dut.src":"logic[31:0]"}
    return [node,"AlwaysComb",lambda e:{"1 dst":"dut.dst","2 src":"dut.src"}.get(e.get("symbol")),raw,
            {n:layout(t) for n,t in raw.items()}]


@pytest.mark.parametrize("k",range(4))
@pytest.mark.parametrize("v",[0,1])
def test_positive(k,v):
    a=setup(k,v=v); old=copy.deepcopy(a[0]); r=expand(*a)
    assert r["model"]==lane_model(k,v)
    assert r["pairs"]==[{"source":"dut.src","source_packed_indices":[],"source_bit":16,
                         "target":"dut.dst","target_packed_indices":[k],"target_bit":1}]
    assert r["local_values"]==[{"target":"dut.dst","target_packed_indices":[k],"target_bit":0,"value":v}]
    assert r["potential_pairs"]==1 and r["permanent_constant"]=="not_inferred"
    assert old==a[0]


@pytest.mark.parametrize("k,v",[(-1,0),(4,1),(True,1),(0,2),(0,True)])
def test_model_bounds(k,v):
    with pytest.raises(Unsupported): lane_model(k,v)


@pytest.mark.parametrize("bad",["context","nba","compound","timing","lane_layout","lane_oob","lane_dynamic",
    "lane_tag","lane_type","rhs_type","order","arity","source_layout","source_oob","source_dynamic",
    "source_tag","source_identity","target_identity","raw_disagreement","declared_disagreement",
    "literal_width","literal_type","literal_x","literal_z","literal_tag","rhs_tag","source_base_tag"])
def test_refusal(bad):
    a=setup(); n=a[0]; lhs=n["left"]; rhs=n["right"]; src,lit=rhs["operands"]
    if bad=="context": a[1]="AlwaysFF"
    elif bad=="nba": n["isNonBlocking"]=True
    elif bad=="compound": n["op"]="Add"
    elif bad=="timing": n["timingControl"]={}
    elif bad=="lane_layout": lhs["value"]["type"]="logic[0:3][1:0]"
    elif bad=="lane_oob": lhs["selector"].update(value="4",constant="4")
    elif bad=="lane_dynamic": lhs["selector"]["kind"]="NamedValue"
    elif bad=="lane_tag": lhs["selector"]["constant"]="2"
    elif bad=="lane_type": lhs["type"]="logic"
    elif bad=="rhs_type": rhs["type"]="bit[1:0]"
    elif bad=="order": rhs["operands"].reverse()
    elif bad=="arity": rhs["operands"].append(lit)
    elif bad=="source_layout": src["value"]["type"]="logic[3:0]"
    elif bad=="source_oob": src["selector"].update(value="32",constant="32")
    elif bad=="source_dynamic": src["selector"]["kind"]="NamedValue"
    elif bad=="source_tag": src["constant"]="1'b0"
    elif bad=="source_identity": src["value"]["symbol"]="9 src"
    elif bad=="target_identity": lhs["value"]["symbol"]="9 dst"
    elif bad=="raw_disagreement": a[3]["dut.dst"]="logic[7:0]"
    elif bad=="declared_disagreement": a[4]["dut.dst"]=layout("logic[7:0]")
    elif bad=="literal_width": lit["value"]="2'b01"
    elif bad=="literal_type": lit["type"]="logic"
    elif bad=="literal_x": lit["value"]="1'bx"
    elif bad=="literal_z": lit["value"]="1'bz"
    elif bad=="literal_tag": lit["constant"]="1'b0"
    elif bad=="rhs_tag": rhs["constant"]="2'b01"
    elif bad=="source_base_tag": src["value"]["constant"]="32'b0"
    with pytest.raises(Unsupported): expand(*a)


@pytest.mark.parametrize("refused",[False,True])
def test_report_contract(monkeypatch,refused):
    import rtlprep.packed_lane_concat_candidates as m
    a=setup(); n=a[0]
    if refused: n["right"]["operands"][1]["value"]="1'bx"
    ast={"node":n}
    occ={"ast_path":"/node","instance":"dut","context":"AlwaysComb","source":{},
         "historical_status":"captured","flat_assignment_id":0}
    access={"items":[{"target_selection":{"kind":"bit","index":3}}]}
    graph={"bit_accesses":access,"bit_dependency_graph":{"items":[{"target":"dut.dst"}]}}
    monkeypatch.setattr(m,"audit_capture",lambda *x:{"items":[occ],"counts":{"ast_occurrences":1,"historical_rows":1}})
    monkeypatch.setattr(m,"exact_links",lambda *x:(None,None,{0},None,None,None))
    def replay(*x,**kw):
        kw["captured_assignments"].append((0,access["items"][0],n,"dut",{},False))
        return access
    monkeypatch.setattr(m,"build_bit_access_index",replay)
    monkeypatch.setattr(m,"reconcile_capture",lambda *x:{0:(n,"dut",False)})
    monkeypatch.setattr(m,"SignalResolver",lambda *x:SimpleNamespace(resolve_exact=lambda owner,e:a[2](e)))
    monkeypatch.setattr(m,"raw_layouts",lambda *x:a[3])
    monkeypatch.setattr(m,"layouts",lambda *x:a[4])
    r=m.audit_packed_lane_concat(ast,{"top":"dut"},graph)
    assert len(r["items"])==r["counts"]["roots"]==1
    assert r["counts"]["partial"]==int(refused)
    assert r["counts"]["potential_pairs"]==int(not refused)
    assert r["counts"]["local_value_records"]==int(not refused)
    assert r["counts"]["stored_coordinates"]==2*int(not refused)
    assert ("candidate" in r["items"][0])!=refused

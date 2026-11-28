import copy
from types import SimpleNamespace
import pytest
from rtlprep.csr_composition_candidates import expand,csr_model,table,width_gate,Unsupported


def setup(k=7,upper=False):
    alias="10 p::csr_num_e"; token="11 p::csr_num_e"
    def named(name,typ,addr):
        return {"kind":"NamedValue","type":typ,"symbol":f"{addr} {name}"}
    def conv(operand,typ):
        return {"kind":"Conversion","type":typ,"operand":operand}
    def binop(op,left,right,typ="logic"):
        return {"kind":"BinaryOp","op":op,"type":typ,"left":left,"right":right}
    def lit(v,typ="int"):
        return {"kind":"IntegerLiteral","type":typ,"value":v}
    def sel(n,addr):
        return {"kind":"ElementSelect","type":"logic","value":named(n,"logic[31:0]",addr),
                "selector":copy.deepcopy(idx)}
    def member(name,addr,v):
        return {"kind":"EnumValue","addr":addr,"name":name,"value":f"12'd{v}",
                "initializer":conv(lit(f"12'd{v}","bit[11:0]"),"logic[11:0]")}
    idx={**named("gidx","integer",4),"constant":str(k)}
    address=conv(named("addr",alias,2),"logic[31:0]")
    name,base,addr=("CSR_MCYCLEH",2944,13) if upper else ("CSR_MCYCLE",2816,12)
    ec=conv({**named(name,token,addr),"constant":f"12'd{base}"},"logic[31:0]")
    ic=conv(copy.deepcopy(idx),"logic[31:0]")
    add=binop("Add",ec,ic,"logic[31:0]")
    eq=binop("Equality",address,add)
    en=named("en","logic",3)
    gate=binop("Equality",named("WIDTH","logic signed[31:0]",14),conv(lit("64"),"logic signed[31:0]"))
    neg={"kind":"UnaryOp","op":"LogicalNot","type":"logic","operand":sel("inhibit",5)}
    rhs=binop("LogicalAnd",binop("LogicalAnd",binop("LogicalAnd",neg,en),eq),gate) if upper else binop("LogicalAnd",en,eq)
    node={"kind":"Assignment","type":"logic","isNonBlocking":False,"left":sel("dst",1),"right":rhs}
    types=SimpleNamespace(types={alias:{"kind":"TypeAlias","target":token},
        token:{"kind":"EnumType","baseType":"logic[11:0]","members":[member("CSR_MCYCLE",12,2816),member("CSR_MCYCLEH",13,2944)]}},
        constants={"14":(("WIDTH",64),"logic signed[31:0]","p")})
    params={"14":("p",{"kind":"Parameter","name":"WIDTH","type":"logic signed[31:0]","isLocal":True,
                           "value":"64","initializer":conv(lit("64"),"logic signed[31:0]")})}
    resolve=lambda e:{"1 dst":"dut.dst","2 addr":"dut.addr","3 en":"dut.en","5 inhibit":"dut.inhibit"}.get(e.get("symbol"))
    return [node,"continuous",resolve,{"dut.dst":"logic[31:0]","dut.addr":alias,"dut.en":"logic","dut.inhibit":"logic[31:0]"},
            {"4":("gidx",k)},types,params]


@pytest.mark.parametrize("k",[0,7,31])
@pytest.mark.parametrize("upper",[False,True])
def test_positive(k,upper):
    a=setup(k,upper); before=copy.deepcopy(a[0]); x=expand(*a)
    assert x["model"]==csr_model(2944 if upper else 2816,k,upper)
    assert x["potential_pairs"]==13+upper and x["target_bit"]==k
    assert [(p["source"],p["source_bit"]) for p in x["pairs"]]==[
        *(("dut.addr",i) for i in range(12)),("dut.en",0),*([("dut.inhibit",k)] if upper else [])]
    assert a[0]==before


@pytest.mark.parametrize("base,k,upper",[(-1,0,False),(4095,1,False),(0,32,False),(0,-1,True),(True,0,False),(0,0,1)])
def test_model_bounds(base,k,upper):
    with pytest.raises(Unsupported): csr_model(base,k,upper)


@pytest.mark.parametrize("bad",["context","nba","target_type","selector_tag","selector_missing","selector_identity",
    "address_tag","address_type","address_identity","alias","enum_base","enum_member","enum_tag","enum_initializer",
    "duplicate_enum","sum_type","sum_tag","sum_index","enable_type","compare_type","and_tag",
    "inhibit_index","inhibit_identity","inhibit_op","width_identity","width_value","width_initializer","width_tag",
    "width_compare","width_not_local","width_package","compound"])
def test_refusals(bad):
    upper=bad.startswith(("inhibit","width"))
    a=setup(7,upper); node=a[0]; rhs=node["right"]; lhs=node["left"]
    if upper:
        eq=rhs["left"]["right"]; en=rhs["left"]["left"]["right"]; neg=rhs["left"]["left"]["left"]; gate=rhs["right"]
    else:
        eq=rhs["right"]; en=rhs["left"]
    add=eq["right"]; addr=eq["left"]["operand"]; ec=add["left"]; ic=add["right"]
    enum=a[5].types["11 p::csr_num_e"]
    if bad=="context": a[1]="AlwaysComb"
    elif bad=="nba": node["isNonBlocking"]=True
    elif bad=="target_type": lhs["value"]["type"]="logic[15:0]"
    elif bad=="selector_tag": lhs["selector"]["constant"]="8"
    elif bad=="selector_missing": a[4].clear()
    elif bad=="selector_identity": lhs["selector"]["symbol"]="9 gidx"
    elif bad=="address_tag": addr["constant"]="12'd0"
    elif bad=="address_type": addr["type"]="logic[11:0]"
    elif bad=="address_identity": addr["symbol"]="9 addr"
    elif bad=="alias": a[5].types.pop("10 p::csr_num_e")
    elif bad=="enum_base": enum["baseType"]="logic[10:0]"
    elif bad=="enum_member": ec["operand"]["symbol"]="99 CSR_MCYCLE"
    elif bad=="enum_tag": ec["operand"]["constant"]="12'd1"
    elif bad=="enum_initializer": enum["members"][0]["initializer"]["operand"]["value"]="12'd0"
    elif bad=="duplicate_enum": enum["members"].append(copy.deepcopy(enum["members"][0]))
    elif bad=="sum_type": add["type"]="logic[11:0]"
    elif bad=="sum_tag": add["constant"]="32'd0"
    elif bad=="sum_index": ic["operand"]["symbol"]="9 gidx"
    elif bad=="enable_type": en["type"]="bit"
    elif bad=="compare_type": eq["left"]["type"]="logic signed[31:0]"
    elif bad=="and_tag": rhs["constant"]="1'b1"
    elif bad=="inhibit_index": neg["operand"]["selector"]["constant"]="8"
    elif bad=="inhibit_identity": neg["operand"]["value"]["symbol"]="99 inhibit"
    elif bad=="inhibit_op": neg["op"]="BitwiseNot"
    elif bad=="width_identity": gate["left"]["symbol"]="99 WIDTH"
    elif bad=="width_value": a[5].constants["14"]=(("WIDTH",32),"logic signed[31:0]","p")
    elif bad=="width_initializer": a[6]["14"][1]["initializer"]["operand"]["value"]="32"
    elif bad=="width_tag": gate["left"]["constant"]="32"
    elif bad=="width_compare": gate["right"]["operand"]["value"]="32"
    elif bad=="width_not_local": a[6]["14"][1]["isLocal"]=False
    elif bad=="width_package": a[6]["14"]=("q",a[6]["14"][1])
    elif bad=="compound": node["op"]="Add"
    with pytest.raises(Unsupported): expand(*a)


@pytest.mark.parametrize("refused",[False,True])
def test_report_contract(monkeypatch,refused):
    import rtlprep.csr_composition_candidates as m
    a=setup(); n=a[0]
    if refused: n["right"]["right"]["right"]["constant"]="32'd0"
    ast={"node":n}
    occ={"ast_path":"/node","instance":"dut","context":"continuous","source":{},
         "historical_status":"captured","flat_assignment_id":0}
    access={"items":[{"target_selection":{"kind":"bit","index":7}}]}
    graph={"bit_accesses":access,"bit_dependency_graph":{"items":[{"target":"dut.dst"}]}}
    monkeypatch.setattr(m,"audit_capture",lambda *x:{"items":[occ],"counts":{"ast_occurrences":1,"historical_rows":1}})
    monkeypatch.setattr(m,"exact_links",lambda *x:(None,None,{0},None,None,None))
    def replay(*x,**kw):
        kw["captured_assignments"].append((0,access["items"][0],n,"dut",a[4],False))
        return access
    monkeypatch.setattr(m,"build_bit_access_index",replay)
    monkeypatch.setattr(m,"reconcile_capture",lambda *x:{0:(n,"dut",False)})
    monkeypatch.setattr(m,"SignalResolver",lambda *x:SimpleNamespace(resolve_exact=lambda owner,e:a[2](e)))
    monkeypatch.setattr(m,"raw_layouts",lambda *x:a[3])
    a[5].truncated=False
    monkeypatch.setattr(m,"Types",lambda *x:a[5])
    monkeypatch.setattr(m,"parameter_inventory",lambda *x:a[6])
    r=m.audit_csr_composition(ast,{"top":"dut"},graph)
    assert len(r["items"])==r["counts"]["roots"]==1
    assert r["counts"]["partial"]==int(refused)
    assert r["counts"]["potential_pairs"]==(0 if refused else 13)
    assert ("candidate" in r["items"][0])!=refused

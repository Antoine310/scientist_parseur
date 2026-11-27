from types import SimpleNamespace
import pytest
from rtlprep.state_conversion_candidates import (literal_bits,state_map,expand,Unsupported)


@pytest.mark.parametrize("raw,n,domain,expected",[
    ("4'b1",4,"bit","1000"),("4'bx",4,"logic","xxxx"),("4'bz",4,"logic","zzzz"),
    ("4'b1x0z",4,"logic","z0x1"),("32'd4",32,"bit","001"+"0"*29),
    ("4'bx1",4,"logic","1xxx"),("4'B10",4,"bit","0100")])
def test_literal(raw,n,domain,expected):
    assert "".join(literal_bits(raw,n,domain))==expected


@pytest.mark.parametrize("raw,n,domain",[
    ("4'bx",4,"bit"),("4'bz",4,"bit"),("4'b2",4,"logic"),("4'b11111",4,"logic"),
    ("3'b1",4,"logic"),("4'd16",4,"bit"),("4'dx",4,"logic"),("4'sb1",4,"bit"),
    ("4'b?",4,"logic"),("4'hf",4,"logic"),("0'b0",0,"bit"),("65'b0",65,"bit")])
def test_bad_literal(raw,n,domain):
    with pytest.raises(Unsupported): literal_bits(raw,n,domain)


@pytest.mark.parametrize("source,dest,expected",[
    ("logic","bit",{"0":"0","1":"1","x":"0","z":"0"}),
    ("bit","logic",{"0":"0","1":"1"})])
def test_map(source,dest,expected):
    assert state_map(source,dest)==expected


def args(dynamic=False,down=True):
    s,d=("logic","bit") if down else ("bit","logic")
    src,dst=s+"[3:0]",d+"[3:0]"
    lhs={"kind":"NamedValue","type":dst,"symbol":"2 y"}
    leaf={"kind":"NamedValue","type":src,"symbol":"1 x"} if dynamic else {
        "kind":"IntegerLiteral","type":src,"value":"4'b1x0z" if down else "4'b1010"}
    node={"kind":"Assignment","isNonBlocking":False,"type":dst,"left":lhs,
          "right":{"kind":"Conversion","type":dst,"operand":leaf}}
    return [node,"AlwaysComb",lambda e:{"1 x":"x","2 y":"y"}.get(e.get("symbol")),{"x":src,"y":dst}]


@pytest.mark.parametrize("down",[True,False])
def test_literal_expression(down):
    a=args(down=down); r=expand(*a)
    assert r["family"]=="literal_expression"
    assert r["result_values_lsb_first"]==list("0001" if down else "0101")
    assert r["coordinate_space"]=="expression_relative" and r["potential_pairs"]==0
    assert "target" not in r
    a[1]="AlwaysFF"; a[0]["isNonBlocking"]=True
    assert expand(*a)==r


@pytest.mark.parametrize("down",[True,False])
def test_dynamic(down):
    r=expand(*args(True,down))
    assert r["family"]=="dynamic_statement" and r["potential_pairs"]==4
    assert r["pairs"]==[{"source_bit":i,"target_bit":i} for i in range(4)]


@pytest.mark.parametrize("bad",["width","sign","nested","unknown_type","tag","source_tag","target","nba","context","bad_identity","rhs_tag"])
def test_refusals(bad):
    a=args(dynamic=bad in {"source_tag","target","nba","context","bad_identity","rhs_tag"})
    n=a[0]; rhs=n["right"]; leaf=rhs["operand"]
    if bad=="width": rhs["type"]="bit[4:0]"
    elif bad=="sign": rhs["type"]="bit signed[3:0]"
    elif bad=="nested": leaf["kind"]="Conversion"
    elif bad=="unknown_type": rhs["type"]="bit[1:0][1:0]"
    elif bad=="tag": rhs["constant"]="4'b1111"
    elif bad=="source_tag": leaf["constant"]="4'b0"
    elif bad=="target": n["left"]["type"]="bit[2:0]"
    elif bad=="nba": n["isNonBlocking"]=True
    elif bad=="context": a[1]="AlwaysFF"
    elif bad=="bad_identity": a[3]["x"]="logic[4:0]"
    elif bad=="rhs_tag": rhs["constant"]="4'b0"
    with pytest.raises(Unsupported): expand(*a)


@pytest.mark.parametrize("refused",[False,True])
def test_report_contract(monkeypatch,refused):
    import rtlprep.state_conversion_candidates as m
    a=args()
    if refused: a[0]["right"]["operand"]["value"]="4'b2"
    ast={"node":a[0]}
    occ={"ast_path":"/node","instance":"fixture","context":"AlwaysComb","source":{},
         "historical_status":"selection_gate_negative","flat_assignment_id":None}
    monkeypatch.setattr(m,"audit_capture",lambda *a:{"items":[occ],"counts":{"ast_occurrences":1,"historical_rows":0}})
    monkeypatch.setattr(m,"exact_links",lambda *a:(None,None,set(),None,None,None))
    monkeypatch.setattr(m,"SignalResolver",lambda *x:SimpleNamespace(resolve_exact=lambda owner,e:a[2](e)))
    monkeypatch.setattr(m,"raw_layouts",lambda *x:a[3])
    r=m.audit_state_conversions(ast,{},{}); row=r["items"][0]
    assert len(r["items"])==r["counts"]["roots"]==1
    assert r["counts"]["partial"]==int(refused)
    assert ("candidate" in row)!=refused
    assert r["counts"]["expression_value_positions"]==(0 if refused else 4)

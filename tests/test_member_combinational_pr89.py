import copy
import pytest
from rtlprep.array_dependencies import Unsupported
from rtlprep import member_combinational as m


def row():
    return {"conditional_operands":[{"target_bits":[2,3],"coverage":"configuration_constant",
        "proof":{"guard_value":0,"selected_branch":"right",
                 "parameters":[{"instance":"top","name":"FPU","value":0}]}}]}


def test_configuration_proof_exact_and_independent_copy():
    r=row()
    p=m.configuration_proof(r,3)
    assert p==r["conditional_operands"][0]["proof"]
    p["parameters"][0]["value"]=1
    assert r==row()


@pytest.mark.parametrize("mode",["missing_operands","wrong_bit","duplicate_operand","partial",
    "missing_proof","unknown_guard","wrong_branch","missing_parameters","unknown_parameter",
    "duplicate_parameter","boolean_parameter"])
def test_bad_configuration_proof(mode):
    r=row()
    o=r["conditional_operands"][0]
    p=o["proof"]
    if mode=="missing_operands": r.pop("conditional_operands")
    elif mode=="wrong_bit": o["target_bits"]=[9]
    elif mode=="duplicate_operand": r["conditional_operands"].append(copy.deepcopy(o))
    elif mode=="partial": o["coverage"]="partial"
    elif mode=="missing_proof": o.pop("proof")
    elif mode=="unknown_guard": p["guard_value"]="x"
    elif mode=="wrong_branch": p["selected_branch"]="left"
    elif mode=="missing_parameters": p["parameters"]=[]
    elif mode=="unknown_parameter": p["parameters"][0]["value"]="x"
    elif mode=="duplicate_parameter": p["parameters"].append(copy.deepcopy(p["parameters"][0]))
    else: p["parameters"][0]["value"]=False
    with pytest.raises(Unsupported):
        m.configuration_proof(r,2)


def test_constant_field_coordinate_units():
    assert m.constant_field({"field":"a","field_coordinates":[1,2]})==("a",[1,2])
    assert m.constant_field({"field":"b","field_bit":0})==("b",[0])
    assert m.constant_field({})==(None,None)


@pytest.mark.parametrize("p",[{"field":"a","field_coordinates":[0,1],"field_bit":0},
    {"field":"a","field_coordinates":[0,True]},{"field":"a","field_coordinates":[]}])
def test_bad_constant_field(p):
    with pytest.raises(Unsupported):
        m.constant_field(p)


@pytest.mark.parametrize("positions",[False,True])
def test_shared_collection_only_once(monkeypatch,positions):
    calls=[]
    evidence,linked=object(),object()
    def collect(ast,index):
        calls.append("collect")
        return evidence,{},linked
    def channel(name):
        def build(ast,index,graph,e,l):
            assert e is evidence and l is linked
            calls.append(name)
            return name
        return build
    monkeypatch.setattr(m,"collect_linked",collect)
    monkeypatch.setattr(m,"_build_combinational",channel("combinational"))
    monkeypatch.setattr(m,"_build_member_positions",channel("positions"))
    result=m.build_member_channels({}, {}, {},positions=positions)
    assert calls==["collect","combinational"]+(["positions"] if positions else [])
    assert result["member_combinational_candidates"]=="combinational"
    assert ("member_position_candidates" in result)==positions

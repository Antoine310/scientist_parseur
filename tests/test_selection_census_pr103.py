import copy
import pytest
from rtlprep.bitaccess import _contains_selection, _contains_selection_v2
from rtlprep.selection_census_v2 import compare_versions


def sel():
    return {"kind":"ElementSelect","value":{"kind":"NamedValue"},"selector":{"kind":"IntegerLiteral"}}


@pytest.mark.parametrize("node",[
    {"kind":"Call","arguments":[sel()]},
    {"kind":"ConditionalOp","conditions":[{"expr":sel()}]},
    {"kind":"StructuredAssignmentPattern","memberSetters":[{"expr":sel()}]},
    {"kind":"Conversion","operand":{"kind":"Call","arguments":[sel()]}},
    {"kind":"FutureExpression","nested":{"other":[sel()]}},
])
def test_hidden_selection(node):
    assert not _contains_selection(node,[0])
    assert _contains_selection_v2(node)


@pytest.mark.parametrize("node",[{},None,{"kind":"NamedValue"},{"kind":"Call","arguments":[{"kind":"NamedValue"}]},
                                 {"kind":"NamedValue","type":sel(),"definition":sel(),"symbol":sel()}])
def test_negative(node):
    assert not _contains_selection_v2(node)


@pytest.mark.parametrize("limits",[{"max_nodes":1},{"max_depth":1},{"max_nodes":0},{"max_depth":65},{"max_nodes":True}])
def test_budget(limits):
    with pytest.raises(ValueError):
        _contains_selection_v2({"kind":"Call","arguments":[sel()]},**limits)


def inputs():
    old={"items":[{"instance":"top","ast_path":"/a","classification":"captured","flat_assignment_id":0},
                  {"instance":"top","ast_path":"/b","classification":"selection_gate_missed_syntax","flat_assignment_id":None,
                   "source":None,"lhs_kind":"NamedValue","rhs_kind":"Call","selections":[],"call_argument_selection":True}]}
    new=copy.deepcopy(old["items"])
    new[0]["flat_assignment_id"]=1
    new[1].update(classification="captured",flat_assignment_id=0)
    a={"coverage":"precise","target":"top.a"}
    b={"coverage":"partial","bit_graph_eligible":False,"source_segments":[],
       "reason":"selection_census_v2_semantics_not_validated"}
    ag={"assignment_id":0,"coverage":"assignment_local_position_candidates","edge_count":1,"constant_target_bits":[]}
    bg={"assignment_id":0,"coverage":"partial","edge_count":0,"constant_target_bits":[]}
    oa={"items":[a],"counts":{"truncated":False}}
    na={"items":[b,copy.deepcopy(a)],"counts":{"truncated":False}}
    og={"items":[ag],"edges":[{"assignment_id":0,"source":"top.x"}],"counts":{"truncated":False}}
    ng={"items":[bg,{**ag,"assignment_id":1}],"edges":[{"assignment_id":1,"source":"top.x"}],"counts":{"truncated":False}}
    return old,new,oa,na,og,ng


def test_exact_projection():
    result=compare_versions(*inputs())
    assert result["old_to_new"]==[{"old_flat_assignment_id":0,"new_flat_assignment_id":1}]
    assert result["added"][0]["new_flat_assignment_id"]==0


@pytest.mark.parametrize("bad",["lost","unrecovered","duplicate","access_changed","row_changed","edge_changed","new_supported","new_edge","truncated"])
def test_projection_refusals(bad):
    args=inputs()
    old,new,oa,na,og,ng=args
    if bad=="lost": new[0]["classification"]="selection_gate_missed_syntax"
    elif bad=="unrecovered": new[1]["classification"]="selection_gate_missed_syntax"
    elif bad=="duplicate": new[1]["ast_path"]="/a"
    elif bad=="access_changed": na["items"][1]["target"]="top.z"
    elif bad=="row_changed": ng["items"][1]["edge_count"]=2
    elif bad=="edge_changed": ng["edges"][0]["source"]="top.y"
    elif bad=="new_supported": na["items"][0]["coverage"]="precise"
    elif bad=="new_edge": ng["edges"].append({"assignment_id":0,"source":"top.y"})
    else: ng["counts"]["truncated"]=True
    with pytest.raises(ValueError):
        compare_versions(*args)

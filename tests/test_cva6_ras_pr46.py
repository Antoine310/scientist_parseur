import pytest
from rtlprep.cva6_ras_reference import Entry, transition
from scripts.run_cva6_ras import summarize, TOP, TARGET

A,B,C = Entry(True,1),Entry(True,2),Entry(True,3)
@pytest.mark.parametrize("push,pop,flush,want",[
    (0,0,0,(A,B)),(1,0,0,(C,A)),(0,1,0,(B,Entry())),
    (1,1,0,(C,B)),(0,0,1,(Entry(),Entry())),
    (1,0,1,(Entry(),Entry())),(0,1,1,(Entry(),Entry())),
    (1,1,1,(Entry(),Entry())),
])
def test_transition(push,pop,flush,want):
    assert transition((A,B),push=push,pop=pop,flush=flush,address=3)==want

def test_reset():
    assert transition((A,B),reset=True,push=True,address=3)==(Entry(),Entry())

def test_unknown_preserved():
    row={"target":TARGET,"coverage":"partial","reason":"unknown"}
    graph={"top":TOP,"schema_version":1,
           "register_flow":{"items":[row],"counts":{"truncated":False}},
           "sequential_candidates":{"items":[row],"counts":{"partial_targets":1}}}
    report=summarize(graph)
    assert report["flow_records"]==[row]
    assert report["formal_proof"]=="not_performed"
    assert report["next_state_combinational_semantics"]=="not_proven"
    graph["register_flow"]["items"]=[]
    assert summarize(graph)["status"]=="not_observed"

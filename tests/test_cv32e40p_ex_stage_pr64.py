import pytest
from scripts.cv32e40p_pr64 import TOP, INSTANCES, LABELS, PATHS, SOURCES, EX_PINS, find_path
from scripts.cv32e40p_pr63 import materialize, COMMIT
from scripts.rtl_fixtures import FixtureError

def edge(s,t,kind="data",seq=False):
    return {"source":s,"target":t,"kind":kind,"sequential":seq}

def graph(*edges):
    return {"nodes":["a","b","c","d"],"edges":list(edges)}

def test_source_inventory():
    assert len(SOURCES)==8 and len(set(SOURCES))==8
    assert len(INSTANCES)==6 and TOP in INSTANCES
    assert set(EX_PINS)<=set(SOURCES)

def test_labels_unique():
    keys={(r["source"],r["target"],r["kind"],r["sequential"]) for r in LABELS}
    assert len(keys)==len(LABELS)==44
    assert sum(r["label"]=="positive" for r in LABELS)==36
    assert all(r["line"]>0 and r["note"] for r in LABELS)
    assert len(PATHS)==5

def test_cross_port_path():
    g=graph(edge("a","b","port_input"),edge("b","c"),edge("c","d","port_output"))
    r=find_path(g,"a","d")
    assert r["status"]=="observed" and len(r["edges"])==3

def test_cycle():
    g=graph(edge("a","b"),edge("b","a"),edge("b","c"))
    assert find_path(g,"a","c")["status"]=="observed"

@pytest.mark.parametrize("kind,seq",[("event",False),("data",True),("control",True)])
def test_sequential_or_event_boundary(kind,seq):
    assert find_path(graph(edge("a","b",kind,seq)),"a","b")["status"]=="not_observed"

def test_depth_budget():
    assert find_path(graph(edge("a","b"),edge("b","c")),"a","c",max_hops=1)["status"]=="budget_exhausted"

def test_visit_budget():
    assert find_path(graph(edge("a","b")),"a","b",max_visits=1)["status"]=="budget_exhausted"

def test_unknown_endpoint():
    with pytest.raises(ValueError,match="unknown endpoint"):
        find_path(graph(),"a","missing")

@pytest.mark.parametrize("bounds",[{"max_hops":0},{"max_visits":False},{"max_hops":33}])
def test_invalid_bounds(bounds):
    with pytest.raises(ValueError,match="bounds"):
        find_path(graph(),"a","b",**bounds)

@pytest.mark.parametrize("pin",["../escape.sv","/abs.sv","rtl/../escape.sv"])
def test_unsafe_additional_pin(tmp_path,pin):
    entry={"repository":"openhwfoundation/cv32e40p","commit":COMMIT,"blobs":{}}
    with pytest.raises(FixtureError,match="unsafe additional pin"):
        materialize(tmp_path,tmp_path/"out",entry,additional_pins={pin:"0"*40})
    assert not (tmp_path/"out").exists()

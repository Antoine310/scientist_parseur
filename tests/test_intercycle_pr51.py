import pytest
from rtlprep.intercycle import build_intercycle_dependencies, trace_event_candidates

def sig(path):
    return {"kind":"signal","path":path}

def row(target,src,clk="u.clk",guards=(),kind="last_nba_rhs_syntax"):
    return {"target":target,"process":"p","events":[{"edge":"PosEdge","signal":clk}],
            "coverage":"syntactic_candidates_supported","multiple_processes_same_target":False,
            "paths":[{"path_index":0,"guards":list(guards),
                      "transition_candidate":{"kind":kind,"rhs":sig(src),"write_order":1}}]}

def report(*rows,truncated=False):
    return build_intercycle_dependencies({"schema_version":1,"items":list(rows),
                                          "counts":{"truncated":truncated}})

def test_pipeline():
    r=report(row("u.q1","u.d"),row("u.q2","u.q1"),row("u.q3","u.q2"))
    p=trace_event_candidates(r,"u.q3")["paths"][0]
    assert [e["source"] for e in p["chain"]]==["u.q2","u.q1","u.d"]
    assert p["reason"]=="unresolved_or_partial"

def test_event_boundary():
    r=report(row("u.q1","u.d"),row("u.q2","u.q1","u.other"))
    p=trace_event_candidates(r,"u.q2")["paths"][0]
    assert len(p["chain"])==1 and p["reason"]=="event_boundary"

def test_hold_is_local_feedback():
    r=report(row("u.q","ignored",kind="unwritten_in_this_process"))
    p=trace_event_candidates(r,"u.q",max_steps=3)["paths"][0]
    assert len(p["chain"])==3
    assert all(e["relation"]=="local_hold_candidate" for e in p["chain"])
    assert p["reason"]=="step_limit"

def test_control_not_data():
    r=report(row("u.q","u.d",guards=[{"kind":"if","branch":"then","condition":sig("u.en")}]))
    p=r["items"][0]["paths"][0]
    assert p["control_sources"]==["u.en"] and p["data_sources"]==["u.d"]
    assert p["guaranteed_cycles"] is None

def test_multiple_events_not_clock():
    x=row("u.q","u.d")
    x["events"].append({"edge":"NegEdge","signal":"u.rst"})
    r=report(x)
    assert r["items"][0]["event_scope"]=="multiple_events_no_clock_inference"
    assert trace_event_candidates(r,"u.q")["paths"][0]["reason"]=="event_boundary"

@pytest.mark.parametrize("mode",["unknown","partial","duplicate","truncated"])
def test_fail_closed(mode):
    x=row("u.q","u.d")
    if mode=="unknown":
        x["paths"][0]["transition_candidate"]["rhs"]={"kind":"unknown"}
    if mode=="partial":
        x["coverage"]="partial"
    r=report(*([x,x] if mode=="duplicate" else [x]),truncated=mode=="truncated")
    assert all(p["coverage"]=="partial" and p["paths"]==[] for p in r["items"])

def test_bounds():
    x=row("u.q","u.d")
    x["paths"]*=4
    r=report(x)
    assert trace_event_candidates(r,"u.q",max_paths=1)["truncated"]
    with pytest.raises(ValueError):
        trace_event_candidates(r,"u.q",max_steps=0)

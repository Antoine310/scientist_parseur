import pytest
from rtlprep.hierarchy import trace_hierarchical

def edge(s,t,k="data",seq=False):
    return {"source":s,"target":t,"kind":k,"sequential":seq,"location":None}

def row(t,s,clk):
    return {"target":t,"coverage":"syntactic_event_candidates_supported",
            "event_scope":"single_edge_event","events":[{"signal":clk,"edge":"PosEdge"}],
            "paths":[{"data_sources":[s],"relation":"last_nba_rhs_references",
                      "guards":[],"path_index":0,"write_source":None}]}

def graph(edges,rows=(),bindings=()):
    nodes={e[k] for e in edges for k in ("source","target")}
    for r in rows:
        nodes.add(r["target"])
        nodes.update(e["signal"] for e in r["events"])
        for p in r["paths"]:
            nodes.update(p["data_sources"])
    return {"schema_version":1,"nodes":sorted(nodes),"edges":edges,"warnings":[],
            "intercycle_dependencies":{"schema_version":1,"items":list(rows),"counts":{"truncated":False}},
            "hierarchical_event_bindings":{"schema_version":1,"items":list(bindings)}}

def pipeline():
    ports=[edge("t.clk","t.a.clk","port_input"),edge("t.clk","t.b.clk","port_input"),
           edge("t.d","t.a.d","port_input"),edge("t.a.q","t.mid","port_output"),
           edge("t.mid","t.b.d","port_input"),edge("t.b.q","t.out","port_output")]
    return graph(ports,[row("t.a.q","t.a.d","t.a.clk"),row("t.b.q","t.b.d","t.b.clk")],
                 ports[:2])

def test_sibling_event_chain():
    r=trace_hierarchical(pipeline(),"t.out")["paths"][0]
    assert r["boundary"]=="t.d" and r["event_steps"]==2
    events=[e for e in r["chain"] if "local_event" in e]
    assert len(events)==2
    assert all(e["event_identity_candidate"]["signal"]=="t.clk" and e["event_bindings"] for e in events)

def test_different_event_boundary():
    g=pipeline()
    g["nodes"].append("t.other")
    g["edges"][1]["source"]="t.other"
    g["hierarchical_event_bindings"]["items"][1]["source"]="t.other"
    r=trace_hierarchical(g,"t.out")["paths"][0]
    assert r["reason"]=="event_boundary" and r["boundary"]=="t.a.q"

def test_general_input_is_not_event_alias():
    g=pipeline()
    g["hierarchical_event_bindings"]["items"]=[]
    r=trace_hierarchical(g,"t.out")["paths"][0]
    assert r["reason"]=="event_boundary"

def test_ambiguous_binding():
    g=pipeline()
    g["hierarchical_event_bindings"]["items"].append(g["hierarchical_event_bindings"]["items"][1])
    assert trace_hierarchical(g,"t.out")["paths"][0]["reason"]=="event_boundary"

def test_partial_sequential_boundary():
    g=pipeline()
    g["intercycle_dependencies"]["items"][1]["coverage"]="partial"
    assert trace_hierarchical(g,"t.out")["paths"][0]["reason"]=="partial_sequential_boundary"

def test_sequential_graph_edge_not_combinational():
    g=graph([edge("u.d","u.q",seq=True)])
    assert trace_hierarchical(g,"u.q")["paths"][0]["reason"]=="unresolved_sequential_boundary"

def test_control_and_event_edges_not_data():
    g=graph([edge("u.en","u.q","control"),edge("u.clk","u.q","event")])
    assert trace_hierarchical(g,"u.q")["paths"][0]["chain"]==[]

def test_combinational_cycle():
    g=graph([edge("u.a","u.b"),edge("u.b","u.a")])
    assert trace_hierarchical(g,"u.a")["paths"][0]["reason"]=="combinational_cycle_boundary"

def test_bounds_and_legacy():
    g=pipeline()
    assert trace_hierarchical(g,"t.out",max_hops=1)["paths"][0]["reason"]=="hop_limit"
    with pytest.raises(ValueError):
        trace_hierarchical(g,"t.out",max_paths=True)
    del g["hierarchical_event_bindings"]
    with pytest.raises(ValueError):
        trace_hierarchical(g,"t.out")

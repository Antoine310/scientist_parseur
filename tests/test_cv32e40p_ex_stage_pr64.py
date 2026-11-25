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


from rtlprep.dependencies import _sign_cast_operand, build_dependency_graph

def call(name="$signed", source_type="logic[31:0]", result_type="logic signed[31:0]"):
    return {"kind":"Call","subroutine":name,"type":result_type,
            "arguments":[{"kind":"NamedValue","symbol":"10 a","type":source_type}]}

@pytest.mark.parametrize("name,src,dst",[
    ("$signed","logic[31:0]","logic signed[31:0]"),
    ("$unsigned","logic signed[31:0]","logic[31:0]"),
    ("$signed","int unsigned","bit signed[31:0]"),
    ("$unsigned","integer","logic[31:0]"),
])
def test_builtin_sign_cast(name,src,dst):
    expr=call(name,src,dst)
    assert _sign_cast_operand(expr) is expr["arguments"][0]

@pytest.mark.parametrize("mode",["user","unknown","width","state","signedness","alias",
                                  "missing","multiple","iterator","malformed"])
def test_sign_cast_reject(mode):
    expr=call()
    if mode=="user":
        expr["subroutine"]="123 signed"
    elif mode=="unknown":
        expr["subroutine"]="$clog2"
    elif mode=="width":
        expr["type"]="logic signed[15:0]"
    elif mode=="state":
        expr["type"]="bit signed[31:0]"
    elif mode=="signedness":
        expr["type"]="logic[31:0]"
    elif mode=="alias":
        expr["arguments"][0]["type"]="word_t"
    elif mode=="missing":
        del expr["arguments"]
    elif mode=="multiple":
        expr["arguments"].append(expr["arguments"][0].copy())
    elif mode=="iterator":
        expr["iterVar"]="i"
    else:
        expr["arguments"]=[None]
    assert _sign_cast_operand(expr) is None

@pytest.mark.parametrize("valid",[True,False])
def test_signal_graph_signed_call_inside_binary(valid):
    expr=call()
    if not valid:
        expr["subroutine"]="123 signed"
    members=[
        {"kind":"Port","name":"a","direction":"In","type":"logic[31:0]"},
        {"kind":"Net","name":"a","addr":10,"type":"logic[31:0]"},
        {"kind":"Port","name":"y","direction":"Out","type":"logic[31:0]"},
        {"kind":"Variable","name":"y","addr":20,"type":"logic[31:0]"},
        {"kind":"ContinuousAssign","assignment":{"kind":"Assignment","isNonBlocking":False,
            "left":{"kind":"NamedValue","symbol":"20 y","type":"logic[31:0]"},
            "right":{"kind":"BinaryOp","op":"Add","type":"logic[31:0]","left":expr,
                     "right":{"kind":"IntegerLiteral","value":"32'd1","type":"logic[31:0]"}}}},
    ]
    ast={"design":{"kind":"Root","members":[{"kind":"Instance","name":"top",
        "body":{"kind":"InstanceBody","name":"top","members":members}}]}}
    g=build_dependency_graph(ast,expected_top="top")
    assert any(e["source"]=="top.a" and e["target"]=="top.y" and e["kind"]=="data"
               for e in g["edges"]) is valid
    assert any("Expression non prise en charge : Call" in w["reason"]
               for w in g["warnings"]) is (not valid)
    # Arithmetic stays outside positional bit inference.
    assert not g["bit_dependency_graph"]["edges"]

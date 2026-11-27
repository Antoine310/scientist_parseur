import pytest
from rtlprep.capture_audit import Budget, AuditLimit, inventory, reconcile, selections, pointer


def selection():
    return {"kind":"ElementSelect","value":{"kind":"NamedValue"},"selector":{"kind":"IntegerLiteral"}}


def assignment(rhs=None,lhs=None):
    return {"kind":"Assignment","left":lhs or {"kind":"NamedValue"},"right":rhs or {"kind":"NamedValue"}}


def call():
    return {"kind":"Call","arguments":[{"kind":"Concatenation","operands":[selection()]}]}


def ast_of(*nodes):
    return {"design":{"members":[{"kind":"Instance","name":"top","body":{"members":[
        {"kind":"ContinuousAssign","assignment":n} for n in nodes]}}]}}


def test_exact_same_line_identity_and_partition():
    a,b,c,d,e=assignment(call()),assignment(lhs=selection()),assignment(),assignment(selection()),assignment(call())
    for n in (a,b,c,d,e):
        n["source_line"]=1
    budget=Budget()
    sites=inventory(ast_of(a,b,c,d,e),{"top"},budget)
    rows=reconcile(sites,[("top",a,"selection_gate_negative"),("top",b,"captured"),
                          ("top",c,"selection_gate_negative"),("top",d,"unsupported_target")],
                   {0:(b,"top",False)},budget)
    assert [r["classification"] for r in rows]==["selection_gate_missed_syntax","captured","no_selection_syntax_in_operands","unsupported_target","not_visited_by_historical_walker"]
    assert rows[0]["call_argument_selection"] and rows[1]["flat_assignment_id"]==0
    assert len({r["ast_path"] for r in rows})==5


def test_nested_selection_path():
    s=selections(assignment(call()),Budget())
    assert [x["path"] for x in s]==["/right/arguments/0","/right/arguments/0/operands/0"]
    assert all(x["inside_call_arguments"] for x in s)


def test_non_call_hidden_field():
    s=selections(assignment({"kind":"ConditionalOp","branches":[selection()]}),Budget())
    assert s==[{"path":"/right/branches/0","kind":"ElementSelect","inside_call_arguments":False}]


def test_inactive_and_declarations_excluded():
    a=ast_of(assignment())
    members=a["design"]["members"][0]["body"]["members"]
    members.extend([{"kind":"GenerateBlock","isUninstantiated":True,"members":members[:]},
                    {"kind":"Variable","initializer":assignment(call())}])
    assert len(inventory(a,{"top"},Budget()))==1


def test_nested_expression_assignment_counted():
    a=assignment({"kind":"Call","arguments":[assignment()]})
    assert len(inventory(ast_of(a),{"top"},Budget()))==2


def test_json_pointer():
    assert pointer("/x","a~/b")=="/x/a~0~1b"


@pytest.mark.parametrize("kind",["foreign_trace","duplicate_trace","missing_capture","foreign_capture","duplicate_capture","duplicate_object","unknown_status"])
def test_reconcile_refuses(kind):
    a,b=assignment(),assignment()
    sites=inventory(ast_of(a,b),{"top"},Budget())
    trace=[("top",a,"captured")]
    capture={0:(a,"top",False)}
    if kind=="foreign_trace": trace.append(("top",assignment(),"selection_gate_negative"))
    elif kind=="duplicate_trace": trace.append(trace[0])
    elif kind=="missing_capture": capture={}
    elif kind=="foreign_capture": capture={0:(b,"top",False)}
    elif kind=="duplicate_capture": capture[1]=capture[0]
    elif kind=="duplicate_object": sites.append(sites[0])
    else: trace=[("top",a,"row_budget")]
    with pytest.raises(ValueError):
        reconcile(sites,trace,capture,Budget())


@pytest.mark.parametrize("limits",[{"max_visits":1},{"max_sites":1},{"max_depth":1}])
def test_inventory_budget(limits):
    with pytest.raises(AuditLimit):
        inventory(ast_of(assignment(),assignment()),{"top"},Budget(**limits))


def test_selection_budget():
    with pytest.raises(AuditLimit):
        selections(assignment(call()),Budget(max_selections=1))


@pytest.mark.parametrize("value",[0,-1,True,2000001])
def test_invalid_budget(value):
    with pytest.raises(ValueError):
        Budget(max_visits=value)

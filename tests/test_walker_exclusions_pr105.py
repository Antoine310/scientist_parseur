import pytest
from rtlprep.walker_exclusion_audit import ancestors, event_index, explain


def site(kind="Initial"):
    a={"kind":"Assignment","left":{"kind":"NamedValue"},"right":{"kind":"ElementSelect"}}
    p={"kind":"ProceduralBlock","procedureKind":kind,"body":{"kind":"ExpressionStatement","expr":a}}
    ast={"design":{"members":[p]}}
    row={"instance":"top","ast_path":"/design/members/0/body/expr",
         "source":{"file":"top.sv","line":1},"context":kind,"lhs_kind":"NamedValue","rhs_kind":"ElementSelect",
         "selections":[{"path":"/right","kind":"ElementSelect"}],"classification":"not_visited_by_historical_walker"}
    return ast,p,a,row


def test_initial_actual_boundary():
    ast,p,a,row=site()
    r=explain(ast,[row],[("top",p,"excluded_procedure_kind")])
    assert r["reason_counts"]=={"excluded_procedure_kind":1}
    assert r["procedure_kind_counts"]=={"Initial":1}
    assert r["nonvisited_with_selection"]==1
    assert r["nonvisited"][0]["boundary"]["ast_path"]=="/design/members/0"
    assert r["matched_exclusion_boundaries"]==1 and r["unexplained"]==0


def test_no_event_not_inferred_from_context():
    ast,p,a,row=site()
    r=explain(ast,[row],[])
    assert r["unexplained"]==1 and r["nonvisited"][0]["boundary"] is None


def test_wrong_owner_not_matched():
    ast,p,a,row=site()
    assert explain(ast,[row],[("other",p,"excluded_procedure_kind")])["unexplained"]==1


def test_assignment_boundary_not_self():
    ast,p,a,row=site("Always")
    assert explain(ast,[row],[("top",a,"assignment_expression_boundary")])["unexplained"]==1


def test_opaque_statement():
    ast,p,a,row=site("Always")
    loop={"kind":"RepeatLoop","body":p["body"]}
    p["body"]=loop
    row["ast_path"]="/design/members/0/body/body/expr"
    r=explain(ast,[row],[("top",loop,"unsupported_statement_kind")])
    assert r["reason_counts"]=={"unsupported_statement_kind":1}
    assert r["nonvisited"][0]["boundary"]["kind"]=="RepeatLoop"


def test_concatenation_target_separate():
    ast,p,a,row=site("Always")
    a["left"]["kind"]=row["lhs_kind"]="Concatenation"
    row["classification"]="unsupported_target"
    r=explain(ast,[row],[])
    assert r["nonvisited"]==[] and r["unsupported_targets"][0]["reason"]=="concatenation_target_outside_historical_target_gate"


@pytest.mark.parametrize("path",["bad","/design/members/01/body/expr","/design/members/9","/design/members/0/body",
                                  "/design/members/0/~2","/design/members/"+"a/"*129])
def test_bad_pointer(path):
    ast,*_=site()
    with pytest.raises(ValueError):
        ancestors(ast,path)


@pytest.mark.parametrize("bad",["duplicate","context","lhs","ambiguous","wrong_kind","unknown_reason","duplicate_row"])
def test_fail_closed(bad):
    ast,p,a,row=site()
    events=[("top",p,"excluded_procedure_kind")]
    rows=[row]
    if bad=="duplicate": events+=events
    elif bad=="context": row["context"]="Final"
    elif bad=="lhs": row["lhs_kind"]="RangeSelect"
    elif bad=="ambiguous": events.append(("top",p["body"],"unsupported_statement_kind"))
    elif bad=="wrong_kind": events=[("top",a,"excluded_procedure_kind")]
    elif bad=="unknown_reason": events=[("top",p,"unknown")]
    else: rows.append(row)
    with pytest.raises(ValueError):
        explain(ast,rows,events)

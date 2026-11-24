import pytest
from rtlprep.complex_constructs import (
    call_record, selection_record, loop_record, literal_index, reference_summary,
    build_complex_construct_index,
)

def ref(name):
    return {"kind":"NamedValue","symbol":"123 "+name}

def resolve(node):
    return "u."+node["symbol"].split()[1] if node["symbol"].split()[1] in ("a","b","idx","arr") else None

def lit(value):
    return {"kind":"IntegerLiteral","value":value}

def test_call_argument_references_not_return_dependencies():
    row=call_record({"kind":"Call","subroutine":"987 mix","arguments":[ref("a"),ref("b")]},resolve)
    assert row["callee"]=="mix" and row["coverage"]=="partial"
    assert [a["signal_references"] for a in row["arguments"]]==[["u.a"],["u.b"]]

def test_call_bad_args():
    row=call_record({"kind":"Call","subroutine":"987 mix","arguments":[ref("a")]*33},resolve)
    assert row["arguments"]==[] and row["coverage"]=="partial"

def test_static_selector():
    row=selection_record({"kind":"ElementSelect","value":ref("arr"),"selector":lit("32'd2")},resolve)
    assert row["selectors"][0]["literal_index"]==2
    assert row["base_references"]["signal_references"]==["u.arr"]
    assert row["bit_mapping"] is None

def test_runtime_selector():
    node=ref("idx")
    node["constant"]="2"
    row=selection_record({"kind":"ElementSelect","value":ref("arr"),"selector":node},resolve)
    assert row["selectors"][0]["classification"]=="runtime_reference_candidate"
    assert row["selectors"][0]["literal_index"] is None

@pytest.mark.parametrize("value",["8'sd255","8'shff","4'b1x00","-1"])
def test_reject_ambiguous_literal(value):
    assert literal_index(lit(value)) is None

def test_repeat_header():
    row=loop_record({"kind":"RepeatLoop","count":lit("3")},resolve)
    assert row["literal_repeat_count"]==3 and row["unrolled"] is False
    assert row["coverage"]=="partial"

def test_repeat_bound():
    row=loop_record({"kind":"RepeatLoop","count":lit("65")},resolve)
    assert row["literal_repeat_count"] is None and row["reason"]=="repeat_count_exceeds_bound"

def test_for_header_not_execution_count():
    row=loop_record({"kind":"ForLoop","initializers":[],"steps":[],
                     "stopExpr":{"kind":"BinaryOp","op":"LessThan","left":ref("i"),"right":lit("4")}},resolve)
    assert row["comparison_literal"]==4 and row["unrolled"] is False
    assert row["reason"]=="for_header_observed_no_trip_count"

def test_unknown_reference():
    result=reference_summary(ref("local"),resolve)
    assert result["unresolved_references"]==1 and not result["complete"]

def test_inventory_ignores_uncalled_function_body():
    index={"instances":[{"path":"u","ports":[{"name":"a"}]}],"signals":[]}
    call={"kind":"Call","subroutine":"987 mix","arguments":[ref("a")]}
    ast={"design":{"members":[{"kind":"Instance","name":"u","body":{"members":[
        {"kind":"Subroutine","name":"mix","body":call},
        {"kind":"ContinuousAssign","assignment":{"kind":"Assignment","right":call}}
    ]}}]}}
    result=build_complex_construct_index(ast,index=index)
    assert result["counts"]["calls"]==1 and not result["counts"]["truncated"]

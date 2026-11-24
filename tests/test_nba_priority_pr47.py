import copy
import pytest
from rtlprep.sequential import build_sequential_candidates

def flow(orders):
    writes=[{"order":n,"rhs":{"kind":"literal","value":str(i)},"source":None}
            for i,n in enumerate(orders)]
    return {"schema_version":1,"counts":{"truncated":False},"items":[
        {"target":"unit.q","process":"p","coverage":"syntactic_paths_supported",
         "paths":[{"writes_in_execution_order":writes,"write_count":len(writes),"guards":[]}]}]}

@pytest.mark.parametrize("orders",[[2,1],[1,1],[0],[-1,2],[True,2]])
def test_invalid_order(orders):
    row=build_sequential_candidates(flow(orders))["items"][0]
    assert row["coverage"]=="partial"
    assert row["paths"]==[]

def test_order_gaps_allowed():
    row=build_sequential_candidates(flow([1,4,9]))["items"][0]
    assert row["paths"][0]["local_overwritten_orders"]==[1,4]
    assert row["paths"][0]["transition_candidate"]["write_order"]==9

def test_hold():
    assert build_sequential_candidates(flow([]))["items"][0]["paths"][0]["transition_candidate"]["kind"]=="unwritten_in_this_process"

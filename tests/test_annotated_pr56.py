import pytest
from rtlprep.annotated_evaluation import evaluate_channel, evaluate_case, key_for

TOP="u"
NODES={"u.a","u.b","u.q","u.c","u.d","u.e"}

def label(source,kind):
    return {"source":source,"target":"q","kind":"data","sequential":False,
            "label":kind,"line":1,"note":"fixture"}

def prediction(source):
    return {"source":"u."+source,"target":"u.q","kind":"data","sequential":False}

def score(labels,preds):
    return evaluate_channel(labels,preds,"signal",TOP,NODES)

def test_confusion_and_metrics():
    r=score([label("a","positive"),label("b","positive"),label("c","negative"),label("d","negative")],
            [prediction("a"),prediction("c")])
    assert (r["tp"],r["fp"],r["fn"],r["tn"])==(1,1,1,1)
    assert (r["precision"],r["recall"],r["f1"])==(.5,.5,.5)

def test_unknown_and_unlabelled_not_negative():
    r=score([label("a","positive"),label("b","unknown"),label("c","unknown")],
            [prediction("a"),prediction("b"),prediction("d")])
    assert r["fp"]==0 and r["precision"]==1
    assert r["unknown_predicted"]==1 and r["unknown_not_predicted"]==1
    assert r["unlabelled_predictions"]==1

def test_no_predictions():
    r=score([label("a","positive")],[])
    assert r["precision"] is None and r["recall"]==0 and r["f1"]==0

def test_no_positive_labels():
    r=score([label("b","negative")],[])
    assert r["precision"] is None and r["recall"] is None and r["f1"] is None

def test_duplicate_prediction_count_not_double_tp():
    r=score([label("a","positive")],[prediction("a"),prediction("a")])
    assert r["tp"]==1 and r["duplicate_prediction_records"]==1

@pytest.mark.parametrize("mode",["duplicate","conflict","bad_label","missing_node","bad_line","empty"])
def test_bad_labels(mode):
    labels=[label("a","positive")]
    if mode=="duplicate":
        labels.append(label("a","positive"))
    elif mode=="conflict":
        labels.append(label("a","negative"))
    elif mode=="bad_label":
        labels[0]["label"]="maybe"
    elif mode=="missing_node":
        labels[0]["source"]="missing"
    elif mode=="bad_line":
        labels[0]["line"]=0
    else:
        labels=[]
    with pytest.raises(ValueError):
        score(labels,[])

def test_edge_roles_separate():
    p=prediction("a")
    p["kind"]="control"
    r=score([label("a","positive")],[p])
    assert r["fn"]==1 and r["unlabelled_predictions"]==1

def test_bit_index_strict():
    with pytest.raises(ValueError):
        key_for({"source":"a","target":"q","source_bit":True,"target_bit":0},"bit")

def test_bit_positions_not_signal_edges():
    a={"source":"a","target":"q","source_bit":1,"target_bit":0,
       "label":"positive","line":2,"note":"slice"}
    p={"source":"u.a","target":"u.q","source_bit":0,"target_bit":0}
    r=evaluate_channel([a],[p],"bit",TOP,NODES)
    assert r["fn"]==1 and r["unlabelled_predictions"]==1

def test_wrong_top_rejected():
    with pytest.raises(ValueError):
        evaluate_case({"top":"u"},{"schema_version":1,"top":"v"})

"""Evaluate a frozen, explicitly labelled candidate universe.

Unlabelled predictions and unknown labels are not treated as negatives.
Metrics concern direct syntactic edges/positions only, not functional influence.
"""
from collections import Counter
from pathlib import Path
import json

SIGNAL_FIELDS=("source","target","kind","sequential")
BIT_FIELDS=("source","source_bit","target","target_bit")
FIELDS={"signal":SIGNAL_FIELDS,"bit":BIT_FIELDS}
LABELS={"positive","negative","unknown"}
KINDS={"data","control","event","port_input","port_output"}


def key_for(row,channel,top=None):
    if channel not in FIELDS or not isinstance(row,dict):
        raise ValueError("unknown channel or malformed row")
    try:
        key=tuple(row[k] for k in FIELDS[channel])
    except KeyError as exc:
        raise ValueError("missing candidate field") from exc
    for name in ("source","target"):
        if not isinstance(row[name],str) or not row[name]:
            raise ValueError("invalid signal name")
    if channel=="signal":
        if row["kind"] not in KINDS or type(row["sequential"]) is not bool:
            raise ValueError("invalid signal edge classification")
    elif any(type(row[f]) is not int or not 0<=row[f]<=65535 for f in ("source_bit","target_bit")):
        raise ValueError("invalid bit index")
    if top is not None:
        key=tuple(top+"."+v if field in ("source","target") else v
                  for field,v in zip(FIELDS[channel],key))
    return key


def ratio(n,d):
    return n/d if d else None


def evaluate_channel(labels,predictions,channel,top,known_nodes):
    """Score one frozen labelled universe; never infer negatives from absence."""
    if not isinstance(labels,list) or not labels:
        raise ValueError("empty label universe")
    observed=[key_for(row,channel) for row in predictions]
    predicted=set(observed)
    by_key={}
    for row in labels:
        key=key_for(row,channel,top)
        label=row.get("label")
        if label not in LABELS or type(row.get("line")) is not int or row["line"]<1 or not isinstance(row.get("note"),str) or not row["note"]:
            raise ValueError("invalid label provenance")
        if key in by_key:
            raise ValueError("duplicate or conflicting label")
        for field in ("source","target"):
            if top+"."+row[field] not in known_nodes:
                raise ValueError("label signal absent from elaborated graph: "+row[field])
        by_key[key]=row
    counts=Counter()
    findings=[]
    for key,row in by_key.items():
        present=key in predicted
        label=row["label"]
        status=("tp" if present else "fn") if label=="positive" else (
               ("fp" if present else "tn") if label=="negative" else
               ("unknown_predicted" if present else "unknown_not_predicted"))
        counts[status]+=1
        findings.append({**row,"predicted":present,"classification":status})
    tp,fp,fn,tn=(counts[x] for x in ("tp","fp","fn","tn"))
    return {"labelled_candidates":len(by_key),
            "positive_labels":tp+fn,"negative_labels":fp+tn,
            "unknown_labels":counts["unknown_predicted"]+counts["unknown_not_predicted"],
            "tp":tp,"fp":fp,"fn":fn,"tn":tn,
            "unknown_predicted":counts["unknown_predicted"],
            "unknown_not_predicted":counts["unknown_not_predicted"],
            "unique_predictions_total":len(predicted),
            "duplicate_prediction_records":len(observed)-len(predicted),
            "unlabelled_predictions":len(predicted-set(by_key)),
            "precision":ratio(tp,tp+fp),"recall":ratio(tp,tp+fn),
            "f1":ratio(2*tp,2*tp+fp+fn),
            "scope":"labelled_candidates_only",
            "findings":findings}


def load_annotations(path):
    data=json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version")!=1 or not isinstance(data.get("cases"),list):
        raise ValueError("annotations v1 required")
    names=[c.get("name") for c in data["cases"]]
    if len(names)!=len(set(names)) or set(names)!={"fixture","cv32e40p_alu"}:
        raise ValueError("unexpected annotation cases")
    return data


def evaluate_case(case,graph):
    if graph.get("schema_version")!=1 or graph.get("top")!=case["top"]:
        raise ValueError("graph does not match annotation case")
    nodes=set(graph["nodes"])
    bitgraph=graph["bit_dependency_graph"]
    return {"signal":evaluate_channel(case["signal"],graph["edges"],"signal",case["top"],nodes),
            "bit":evaluate_channel(case["bit"],bitgraph["edges"],"bit",case["top"],nodes),
            "graph_warnings":len(graph["warnings"]),
            "bit_graph_counts":bitgraph["counts"],
            "design_coverage":"not_measured",
            "functional_influence":"not_proven"}

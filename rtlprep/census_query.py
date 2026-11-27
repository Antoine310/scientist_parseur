"""Public, versioned, bounded syntax census snapshot. No semantic promotion."""
from collections import Counter
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from .analysis_budgets import DEFAULT_BUDGET, measure_tree, read_ast
from .selection_census_v2 import audit_selection_v2

MAX_REPORT_BYTES=16*1024*1024
MAX_INDEX_BYTES=12*1024*1024
MAX_GRAPH_BYTES=64*1024*1024
MAX_PAGE=100
MAX_RESPONSE_BYTES=256*1024
MAX_ROWS=20000
INPUTS=("elaborated_ast.json","rtl_index.json","rtl_dependencies.json")
CLASSES={"captured","no_selection_syntax_in_operands","selection_gate_missed_syntax",
         "unsupported_target","not_visited_by_historical_walker"}
SCOPE="active_process_continuous_selection_census"
ROW_KEYS={"instance","ast_path","context","source","lhs_kind","rhs_kind","selection_count",
          "call_argument_selection","v1","v2"}
VERSION_KEYS={"classification","assignment_id","position_coverage"}
COVERAGE={"partial","assignment_local_position_candidates"}


def _require(condition,reason):
    if not condition:
        raise ValueError("selection_census: "+reason)


def _nat(x):
    return type(x) is int and x>=0


def _string(x,limit=4096):
    return isinstance(x,str) and 0<len(x)<=limit


def _sha(x):
    return isinstance(x,str) and re.fullmatch(r"[0-9a-f]{64}",x) is not None


def file_sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest() if hasattr(hashlib,"file_digest") else _stream_sha(stream)


def _stream_sha(stream):
    h=hashlib.sha256()
    for chunk in iter(lambda:stream.read(65536),b""):
        h.update(chunk)
    return h.hexdigest()


def _load(path,cap):
    path=Path(path)
    _require(path.is_file() and path.stat().st_size<=cap,"file absent or byte budget")
    with path.open("rb") as stream:
        raw=stream.read(cap+1)
    _require(len(raw)<=cap,"file byte budget")
    try:
        value=json.loads(raw.decode("utf-8"))
    except RecursionError as exc:
        raise ValueError("selection_census: JSON depth budget") from exc
    _require(isinstance(value,dict),"JSON object required")
    measure_tree(value,stage="selection_census_read",max_values=DEFAULT_BUDGET.max_graph_values,
                 max_depth=DEFAULT_BUDGET.max_graph_depth)
    return value,hashlib.sha256(raw).hexdigest()


def _compact_bytes(obj):
    return json.dumps(obj,ensure_ascii=True,allow_nan=False,separators=(",",":")).encode("utf-8")


def _version_counts(rows,key):
    c=Counter(r[key]["classification"] for r in rows)
    supported=sum(r[key]["position_coverage"]=="assignment_local_position_candidates" for r in rows)
    return {"ast_occurrences":len(rows),"captured":c.get("captured",0),
            "position_supported":supported,"position_partial":c.get("captured",0)-supported,
            "classification":dict(sorted(c.items()))}


def validate(report):
    _require(isinstance(report,dict) and type(report.get("schema_version")) is int and report["schema_version"]==1
             and report.get("scope")==SCOPE,"unsupported public schema")
    _require(_string(report.get("top"),1024) and _string(report.get("source_fingerprint"),1024),"missing provenance")
    hashes=report.get("input_sha256")
    _require(isinstance(hashes,dict) and set(hashes)==set(INPUTS) and all(_sha(v) for v in hashes.values()),"invalid input hashes")
    _require(report.get("historical_projection_exact") is True and report.get("historical_replay_exact") is True
             and report.get("design_coverage")=="not_measured" and report.get("functional_influence")=="not_proven",
             "invalid scientific claims")
    rows=report.get("items")
    _require(isinstance(rows,list) and len(rows)<=MAX_ROWS,"row budget")
    ids={"v1":set(),"v2":set()}
    keys=set()
    added=0
    for row in rows:
        _require(isinstance(row,dict) and set(row)==ROW_KEYS,"invalid row fields")
        _require(_string(row["instance"],1024) and _string(row["ast_path"]) and row["ast_path"].startswith("/design/members/")
                 and _string(row["context"],128),"invalid occurrence identity")
        key=(row["instance"],row["ast_path"])
        _require(key not in keys,"duplicate occurrence")
        keys.add(key)
        src=row["source"]
        _require(isinstance(src,dict) and set(src)=={"file","line"}
                 and (src["file"] is None or _string(src["file"]))
                 and (src["line"] is None or _nat(src["line"])),"invalid source location")
        _require(all(row[k] is None or _string(row[k],128) for k in ("lhs_kind","rhs_kind"))
                 and _nat(row["selection_count"]) and type(row["call_argument_selection"]) is bool
                 and (not row["call_argument_selection"] or row["selection_count"]>0),"invalid syntax metadata")
        for version in ("v1","v2"):
            item=row[version]
            _require(isinstance(item,dict) and set(item)==VERSION_KEYS and isinstance(item["classification"],str)
                     and item["classification"] in CLASSES,"invalid version row")
            i=item["assignment_id"]
            if item["classification"]=="captured":
                _require(_nat(i) and i not in ids[version] and isinstance(item["position_coverage"],str)
                         and item["position_coverage"] in COVERAGE,"invalid or duplicate assignment ID")
                ids[version].add(i)
            else:
                _require(i is None and item["position_coverage"] is None,"noncaptured row has position ID")
        a,b=row["v1"],row["v2"]
        if a["classification"]=="selection_gate_missed_syntax":
            _require(b["classification"]=="captured" and b["position_coverage"]=="partial"
                     and row["selection_count"]>0,"omission not recovered conservatively")
            added+=1
        else:
            _require(a["classification"]==b["classification"] and a["position_coverage"]==b["position_coverage"],
                     "historical classification changed")
    for v in ids:
        _require(ids[v]==set(range(len(ids[v]))),"noncontiguous assignment IDs")
    _require(report.get("counts")=={v:_version_counts(rows,v) for v in ids},"version counts disagree")
    _require(type(report.get("new_partial_rows")) is int and report["new_partial_rows"]==added
             and type(report.get("new_edges")) is int and report["new_edges"]==0
             and type(report.get("new_supported_rows")) is int and report["new_supported_rows"]==0,"invalid promotion claims")
    return report


def build_report(ast,index,graph,hashes):
    _require(index.get("top")==graph.get("top") and index.get("schema_version")==graph.get("schema_version")==1,
             "index/graph mismatch")
    fp=index.get("source_fingerprint")
    _require(_string(fp,1024) and fp==graph.get("source_fingerprint"),"source fingerprint mismatch")
    audit=audit_selection_v2(ast,index,graph)
    old_by_new={r["new_flat_assignment_id"]:r["old_flat_assignment_id"] for r in audit["id_mapping"]}
    added={r["new_flat_assignment_id"] for r in audit["added"]}
    old_flat=graph["bit_dependency_graph"]["items"]
    new_flat=audit["v2_bit_dependency_graph"]["items"]
    rows=[]
    for row in audit["v2_items"]:
        new=row["flat_assignment_id"]
        old=old_by_new.get(new)
        cls=row["classification"]
        prior="selection_gate_missed_syntax" if new in added else cls
        rows.append({k:copy.deepcopy(row[k]) for k in ("instance","ast_path","context","source","lhs_kind","rhs_kind","call_argument_selection")}|{
            "selection_count":len(row["selections"]),
            "v1":{"classification":prior,"assignment_id":old,"position_coverage":old_flat[old]["coverage"] if old is not None else None},
            "v2":{"classification":cls,"assignment_id":new,"position_coverage":new_flat[new]["coverage"] if new is not None else None}})
    result={"schema_version":1,"scope":SCOPE,"top":index["top"],"source_fingerprint":fp,
            "input_sha256":dict(hashes),"historical_projection_exact":True,"historical_replay_exact":True,
            "counts":{v:_version_counts(rows,v) for v in ("v1","v2")},
            "new_partial_rows":len(added),"new_edges":0,"new_supported_rows":0,
            "design_coverage":"not_measured","functional_influence":"not_proven","items":rows}
    return validate(result)


def export_report(folder,out):
    """Read only operator-selected artifact directory; never overwrite a file."""
    folder=Path(folder)
    out=Path(out)
    _require(not out.exists() and not out.is_symlink(),"output already exists")
    ast_path=folder/INPUTS[0]
    _require(ast_path.is_file() and ast_path.stat().st_size<=DEFAULT_BUDGET.max_ast_bytes,"AST byte budget")
    before=file_sha(ast_path)
    ast=read_ast(ast_path)
    idx,ih=_load(folder/INPUTS[1],MAX_INDEX_BYTES)
    graph,gh=_load(folder/INPUTS[2],MAX_GRAPH_BYTES)
    hashes=dict(zip(INPUTS,(before,ih,gh)))
    report=build_report(ast,idx,graph,hashes)
    _require(all(file_sha(folder/k)==v for k,v in hashes.items()),"input changed during publication")
    raw=_compact_bytes(report)
    _require(len(raw)<=MAX_REPORT_BYTES,"report byte budget")
    out.parent.mkdir(parents=True,exist_ok=True)
    tmp=None
    try:
        with tempfile.NamedTemporaryFile(dir=out.parent,delete=False) as stream:
            tmp=Path(stream.name)
            stream.write(raw)
        os.link(tmp,out)  # exclusive atomic publication on the same filesystem
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
    return {"status":"passed","report":str(out),"counts":report["counts"],"input_sha256":hashes}


def load_report(path):
    report,_=_load(path,MAX_REPORT_BYTES)
    return validate(report)


def query_census(report,*,version,classification=None,instance=None,limit=20,offset=0):
    _require(type(version) is int and version in (1,2),"explicit version 1 or 2 required")
    _require(type(limit) is int and 1<=limit<=MAX_PAGE and _nat(offset),"invalid pagination")
    _require(classification is None or isinstance(classification,str) and classification in CLASSES,"unknown classification")
    _require(instance is None or _string(instance,1024),"invalid instance")
    key="v"+str(version)
    rows=[r for r in report["items"] if (classification is None or r[key]["classification"]==classification)
          and (instance is None or r["instance"]==instance)]
    result={"schema_version":1,"census_version":version,"scope":SCOPE,"top":report["top"],
            "source_fingerprint":report["source_fingerprint"],"input_sha256":copy.deepcopy(report["input_sha256"]),
            "counts":copy.deepcopy(report["counts"][key]),"new_partial_rows":report["new_partial_rows"],
            "new_edges":0,"new_supported_rows":0,"total":len(rows),"offset":offset,
            "next_offset":offset+limit if offset+limit<len(rows) else None,
            "items":copy.deepcopy(rows[offset:offset+limit]),
            "origin":"stored_syntax_census_not_reexecuted","design_coverage":"not_measured",
            "functional_influence":"not_proven","historical_projection_exact":True}
    _require(len(_compact_bytes(result))<=MAX_RESPONSE_BYTES,"response byte budget; reduce limit")
    return result

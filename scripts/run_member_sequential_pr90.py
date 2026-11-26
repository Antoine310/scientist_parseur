"""Validate all three member channels and statement-local NBA partitions."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
from time import perf_counter

from rtlprep.analysis_budgets import read_ast
from rtlprep.dependencies import build_dependency_graph
from scripts.run_member_combinational_pr89 import check_channel as check_pr89
from rtlprep.member_evidence import collect
from rtlprep.member_occurrences import collect_linked
from scripts.run_member_evidence_pr86 import check_core as check_pr86, check_lossless
from scripts.run_conditional_member_concat_pr85 import check_core as check_pr85
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.rtl_fixtures import load_lock

ROOT=Path(__file__).resolve().parents[1]
TOP="member_occ_pr87"
FIXTURE=ROOT/"tests/fixtures/member_occ_pr87.sv"

def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()

def check_channel(channel,positions,combinational,name):
    c=channel["collections"]
    records=c["nba_sampled"]+c["nba_constant"]
    expected={"member_pattern_pr84":(2,3,1,7),"alu":(0,0,0,0),"core":(2,5,1,1474)}
    samples,constants,sites,other=expected[name]
    assert channel["counts"]=={"nba_sampled":samples,"nba_constant":constants,
        "records":samples+constants,"occurrences":sites,"complete_statement_partitions":sites,
        "other_candidate_records_not_promoted":other},channel["counts"]
    assert not channel["truncated"]
    ids={r["record_id"] for r in records}
    other_records=positions["items"]+[r for v in combinational["collections"].values() for r in v]
    other_ids={r["record_id"] for r in other_records}
    assert len(ids)==len(records) and len(other_ids)==len(other_records) and not ids&other_ids
    assert len(other_ids)==other
    for r in records:
        assert r["update_semantics"]=="deferred_nonblocking_when_executed"
        assert r["guard_feasibility"]==r["writer_priority"]=="not_proven"
        assert r["event_binding"]=="not_performed"
    assert all("source" not in r and r["semantics"]=="constant_rhs_when_statement_executes" for r in c["nba_constant"])
    assert all("value" not in r and r["semantics"]=="rhs_sampled_when_statement_executes" for r in c["nba_sampled"])
    if name=="core":
        check_pr89(combinational,positions,"core")
        p="cv32e40p_core.cs_registers_i."
        src,dst=p+"mstatus_n",p+"mstatus_q"
        vals={(0,0),(1,1),(2,1),(4,0),(6,0)}
        bits=(3,5)
        fields={0:("mprv",0),1:("mpp",0),2:("mpp",1),3:("mpie",0),4:("upie",0),5:("mie",0),6:("uie",0)}
        assert {r["source_location"]["line"] for r in records}=={1223}
    elif name=="member_pattern_pr84":
        p=name+"."
        src,dst=p+"d",p+"q"
        vals={(0,0),(1,0),(2,1)}
        bits=(3,4)
        fields={0:("c",0),1:("mode",0),2:("mode",1),3:("b",0),4:("a",0)}
    else:
        check_pr89(combinational,positions,"alu")
        return
    assert {(r["source"]["signal"],r["source"]["position"],r["target"]["signal"],r["target"]["position"])
            for r in c["nba_sampled"]}=={(src,b,dst,b) for b in bits}
    assert {(r["target"]["signal"],r["target"]["position"],r["value"]) for r in c["nba_constant"]}=={
        (dst,b,v) for b,v in vals}
    for r in records:
        t=r["target"]
        assert t["coordinate_kind"]=="packed_struct_offset"
        assert (t["field"],t["field_coordinates"][0])==fields[t["position"]]
    assert len(channel["partitions"])==1
    part=channel["partitions"][0]
    assert part["target"]==dst and part["width"]==len(fields) and set(part["record_ids"])==ids
    assert part["scope"]=="complete_statement_target_positions_only"


def execute(out,reference=None):
    out=out.resolve()
    for e in load_lock():
        root=(ROOT/e["destination"]).resolve()
        if out==root or out.is_relative_to(root):
            raise ValueError("output cannot be inside official RTL")
    out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out))
    path,summary=run/"member_sequential.result.json",run/"summary.json"
    report={"status":"incomplete","cases":[],"design_coverage":"not_measured",
            "functional_influence":"not_proven","formal_proof":"not_performed"}
    def save():
        path.write_text(json.dumps(report,indent=2),encoding="utf-8")
        summary.write_text(json.dumps({**report,"cases":[{k:v for k,v in c.items()
            if k not in ("collections","partitions","position_channel","combinational_channel")} for c in report["cases"]]},indent=2),encoding="utf-8")
    def case(name,folder,idx,legacy_graph):
        ast_path=folder/"elaborated_ast.json"
        ast=read_ast(ast_path)
        start=perf_counter()
        graph=build_dependency_graph(ast,expected_top=idx["top"],index=idx,enable_member_positions=True,enable_member_combinational=True,enable_member_sequential=True)
        graph_seconds=perf_counter()-start
        graph=json.loads(json.dumps(graph))
        channel=graph["member_sequential_candidates"]
        combinational=graph["member_combinational_candidates"]
        positions=graph["member_position_candidates"]
        report["cases"].append({"name":name,"ast_sha256":sha256(ast_path),
            "index_sha256":sha256(folder/"rtl_index.json"),**channel,
            "position_channel_counts":positions["counts"],"position_channel":positions,
            "combinational_channel_counts":combinational["counts"],"combinational_channel":combinational,
            "historical_bit_counts":graph["bit_dependency_graph"]["counts"],
            "opt_in_graph_build_seconds":graph_seconds})
        save()
        check_channel(channel,positions,combinational,name)
        # Preserve the existing graph content; only publication metrics may grow.
        excluded={"analysis_limits","source_fingerprint","member_position_candidates","member_combinational_candidates","member_sequential_candidates"}
        assert {k:v for k,v in graph.items() if k not in excluded}=={
            k:v for k,v in legacy_graph.items() if k not in excluded}
        assert not graph["analysis_limits"]["truncated_analyzers"]
        report["cases"][-1]["historical_graph_unchanged"]=True
        report["cases"][-1]["graph_publication_metrics"]=graph["analysis_limits"]["graph_metrics_excluding_this_report"]
        save()
    save()
    try:
        for top in ("member_pattern_pr84",):
            legacy,idx=extract(run/top,top,[ROOT/"tests/fixtures"/(top+".sv")])
            case(top,run/top,idx,legacy)
        d=diagnostics(run/"reference") if reference is None else reference.resolve()
        ref=json.loads(d.read_text())
        assert ref["status"]=="passed"
        report["reference_report"]=str(d)
        for name,folder in (("alu",d.parent/"alu"),
                            ("core",Path(ref["core_reference_report"]).parent/"static")):
            idx=json.loads((folder/"rtl_index.json").read_text())
            graph=json.loads((folder/"rtl_dependencies.json").read_text())
            case(name,folder,idx,graph)
        report["status"]="passed"
    except Exception as exc:
        report.update(status="failed",error=f"{type(exc).__name__}: {exc}"[:1000])
        raise
    finally:
        save()
        print(f"Summary: {summary}",flush=True)
        print(summary.read_text(),flush=True)
    return path

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--reference",type=Path,help="Fresh diagnostics.result.json from same validated checkout")
    args=p.parse_args()
    execute(args.out,args.reference)

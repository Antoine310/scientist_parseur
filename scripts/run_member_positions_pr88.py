"""Validate opt-in typed member channel in the actual dependency graph builder."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
from time import perf_counter

from rtlprep.analysis_budgets import read_ast
from rtlprep.dependencies import build_dependency_graph
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

def check_channel(channel,name):
    counts=channel["counts"]
    expected={"fixture":(2,0,2,2,0),"alu":(0,0,0,0,0),"core":(660,640,13,10,821)}[name]
    n,m,occ,pairs,other=expected
    assert counts=={"positions":n,"multidimensional_targets":m,"position_occurrences":occ,
        "signal_pairs":pairs,"other_candidate_records_not_promoted":other,
        "signal_pair_present":n,"signal_pair_absent":0,"flat_coordinate_comparable":0,
        "flat_coordinate_incomparable":n,"flat_endpoint_tuple_present":0,
        "flat_endpoint_tuple_absent":0},counts
    assert len({r["record_id"] for r in channel["items"]})==n
    assert not channel["truncated"]
    if name=="core":
        p="cv32e40p_core.cs_registers_i."
        for target,width,offset,inner in (("pmp_addr_o",512,256,32),("pmp_cfg_o",128,0,8)):
            records=[r for r in channel["items"] if r["target"]["signal"]==p+target]
            assert {(r["source"]["position"],r["target"]["position"],tuple(r["target"]["coordinates"])) for r in records}=={
                (offset+b,b,(b//inner,b%inner)) for b in range(width)}
        assert all(r["source"]["coordinate_kind"]=="packed_struct_offset" for r in channel["items"]
                   if r["producer"]=="pr82")
        expected_small={(p+s,sb,p+t,tb) for s,sb,t,tb in [
            *[("debug_cause_i",i,"dcsr_n",6+i) for i in range(3)],
            ("mstatus_q",5,"mstatus_n",3),("mstatus_q",3,"mstatus_n",5),
            ("dcsr_q",0,"priv_lvl_n",0),("dcsr_q",1,"priv_lvl_n",1),
            ("dcsr_q",2,"debug_single_step_o",0),("dcsr_q",15,"debug_ebreakm_o",0),
            ("dcsr_q",12,"debug_ebreaku_o",0),
            *[("csr_wdata_int",i,"dcsr_n",i) for i in (15,11,2)],
            *[("mstatus_q",a,"csr_rdata_int",b) for a,b in ((6,0),(5,3),(4,4),(3,7),(1,11),(2,12),(0,17))]]}
        actual_small={(i["source"]["signal"],i["source"]["position"],i["target"]["signal"],i["target"]["position"])
                      for i in channel["items"] if i["producer"]!="pr82"}
        assert actual_small==expected_small and len(actual_small)==20
    if name=="fixture":
        assert {(r["source"]["position"],r["target"]["signal"]) for r in channel["items"]}=={
            (1,TOP+".a"),(0,TOP+".b")}


def execute(out,reference=None):
    out=out.resolve()
    for e in load_lock():
        root=(ROOT/e["destination"]).resolve()
        if out==root or out.is_relative_to(root):
            raise ValueError("output cannot be inside official RTL")
    out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out))
    path,summary=run/"member_positions.result.json",run/"summary.json"
    report={"status":"incomplete","cases":[],"design_coverage":"not_measured",
            "functional_influence":"not_proven","formal_proof":"not_performed"}
    def save():
        path.write_text(json.dumps(report,indent=2),encoding="utf-8")
        summary.write_text(json.dumps({**report,"cases":[{k:v for k,v in c.items()
            if k!="items"} for c in report["cases"]]},indent=2),encoding="utf-8")
    def case(name,folder,idx,legacy_graph):
        ast_path=folder/"elaborated_ast.json"
        ast=read_ast(ast_path)
        start=perf_counter()
        graph=build_dependency_graph(ast,expected_top=idx["top"],index=idx,enable_member_positions=True)
        graph_seconds=perf_counter()-start
        graph=json.loads(json.dumps(graph))
        channel=graph["member_position_candidates"]
        report["cases"].append({"name":name,"ast_sha256":sha256(ast_path),
            "index_sha256":sha256(folder/"rtl_index.json"),**channel,
            "historical_bit_counts":graph["bit_dependency_graph"]["counts"],
            "opt_in_graph_build_seconds":graph_seconds})
        save()
        check_channel(channel,name)
        # Preserve the existing graph content; only publication metrics may grow.
        excluded={"analysis_limits","source_fingerprint","member_position_candidates"}
        assert {k:v for k,v in graph.items() if k not in excluded}=={
            k:v for k,v in legacy_graph.items() if k not in excluded}
        assert not graph["analysis_limits"]["truncated_analyzers"]
        report["cases"][-1]["historical_graph_unchanged"]=True
        report["cases"][-1]["graph_publication_metrics"]=graph["analysis_limits"]["graph_metrics_excluding_this_report"]
        save()
    save()
    try:
        legacy,idx=extract(run/"fixture",TOP,[FIXTURE])
        case("fixture",run/"fixture",idx,legacy)
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

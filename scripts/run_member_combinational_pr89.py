"""Validate the two opt-in member channels, with independent constant/reference oracles."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
from time import perf_counter

from rtlprep.analysis_budgets import read_ast
from rtlprep.dependencies import build_dependency_graph
from scripts.run_member_positions_pr88 import check_channel as check_pr88
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

def constant_key(r):
    return (r["source_location"]["line"],r["target"]["signal"],r["target"]["position"],r["value"])

def logical_key(r):
    return (r["source"]["signal"],r["source"]["position"],r["target"]["signal"],r["target"]["position"])

def check_channel(channel,positions,name):
    c=channel["collections"]
    counts=channel["counts"]
    assert not channel["truncated"]
    all_records=[r for records in c.values() for r in records]
    assert len({r["record_id"] for r in all_records})==len(all_records)
    assert not {r["record_id"] for r in all_records}&{r["record_id"] for r in positions["items"]}
    assert all("source" not in r and r["semantics"]=="statement_local_when_executed" for r in c["local_constant"])
    assert all("source" not in r and r["semantics"]=="configuration_local_when_executed" for r in c["configuration_constant"])
    assert all(r["semantics"]=="structural_reference_only" and "value" not in r for r in c["logical_reference"])
    expected={"local_members_pr82":(12,0,0,12),"member_expr_pr83":(0,0,3,3),
              "member_cond_pr85":(0,2,0,4),"alu":(0,0,0,0),"core":(805,3,6,660)}
    a,b,d,pcount=expected[name]
    assert (counts["local_constant"],counts["configuration_constant"],counts["logical_reference"],counts["records"])==(a,b,d,a+b+d),counts
    assert positions["counts"]["positions"]==pcount
    if name=="local_members_pr82":
        p=name+"."
        expected={(p+"zero_bundle",offset+i,field,coord,0)
                  for field,offset,coords in (("upper",4,[(i//4,i%4) for i in range(8)]),
                    ("lower",0,[(1-i//2,i%2) for i in range(4)]))
                  for i,coord in enumerate(coords)}
        assert {(r["target"]["signal"],r["target"]["position"],r["target"]["field"],
                 tuple(r["target"]["field_coordinates"]),r["value"]) for r in c["local_constant"]}==expected
    if name=="member_expr_pr83":
        assert {logical_key(r) for r in c["logical_reference"]}=={
            (name+".bundle",i,name+".flag",0) for i in range(3)}
    if name=="member_cond_pr85":
        assert {(r["target"]["signal"],r["target"]["position"],r["value"]) for r in c["configuration_constant"]}=={
            (name+".disabled_o",i,0) for i in (2,3)}
    if name=="core":
        check_pr88(positions,"core")
        assert counts["occurrences"]==17 and counts["other_candidate_records_not_promoted"]==667
        p="cv32e40p_core.cs_registers_i."
        expected={(line,p+target,bit,v) for line,target,bit,v in [
            (1000,"dcsr_n",13,0),(1001,"dcsr_n",12,0),(1003,"dcsr_n",10,0),
            (1004,"dcsr_n",9,0),(1005,"dcsr_n",4,0),(1060,"mstatus_n",5,0),(1070,"mstatus_n",3,1),
            *[(line,"dcsr_n",bit,1) for line in (1007,1054) for bit in (0,1)],
            *[(line,"mstatus_n",bit,1) for line in (1061,1071) for bit in (1,2)],
            *[(467,"csr_rdata_int",bit,0) for bit in (1,2,5,6,8,9,10,15,16,*range(18,31))],
            *[(line,"pmp_reg_n",bit,0) for line,start,end in ((910,256,768),(911,128,256),(912,0,128)) for bit in range(start,end)]]}
        assert len(expected)==805 and {constant_key(r) for r in c["local_constant"]}==expected
        for r in c["local_constant"]:
            t=r["target"]
            if t["signal"]==p+"pmp_reg_n":
                line=r["source_location"]["line"]
                field,offset,width={910:("pmpaddr",256,32),911:("pmpcfg_packed",128,32),912:("pmpcfg",0,8)}[line]
                bit=t["position"]-offset
                assert t["field"]==field and t["field_coordinates"]==[bit//width,bit%width]
        assert {constant_key(r) for r in c["configuration_constant"]}=={
            (467,p+"csr_rdata_int",bit,0) for bit in (13,14,31)}
        for r in c["configuration_constant"]:
            proof=r["configuration_proof"]
            assert proof["guard_value"]==0 and proof["selected_branch"]=="right"
            assert {(x["instance"],x["name"],x["value"]) for x in proof["parameters"]}=={
                (owner,n,0) for owner in ("cv32e40p_core",p[:-1]) for n in ("FPU","ZFINX")}
        assert {logical_key(r) for r in c["logical_reference"]}=={
            (p+src,bit,p+target,0) for target,m in (("m_irq_enable_o",5),("u_irq_enable_o",6))
            for src,bit in (("mstatus_q",m),("dcsr_q",2),("dcsr_q",11))}
        assert len({r["occurrence_ordinal"] for r in c["logical_reference"]})==2
        # CSR concat: 7 position copies plus 22 literal and 3 configuration lanes.
        groups=[{r["target"]["position"] for r in records if r["target"]["signal"]==p+"csr_rdata_int"}
                for records in (positions["items"],c["local_constant"],c["configuration_constant"])]
        assert list(map(len,groups))==[7,22,3] and set.union(*groups)==set(range(32))


def execute(out,reference=None):
    out=out.resolve()
    for e in load_lock():
        root=(ROOT/e["destination"]).resolve()
        if out==root or out.is_relative_to(root):
            raise ValueError("output cannot be inside official RTL")
    out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out))
    path,summary=run/"member_combinational.result.json",run/"summary.json"
    report={"status":"incomplete","cases":[],"design_coverage":"not_measured",
            "functional_influence":"not_proven","formal_proof":"not_performed"}
    def save():
        path.write_text(json.dumps(report,indent=2),encoding="utf-8")
        summary.write_text(json.dumps({**report,"cases":[{k:v for k,v in c.items()
            if k not in ("collections","position_channel")} for c in report["cases"]]},indent=2),encoding="utf-8")
    def case(name,folder,idx,legacy_graph):
        ast_path=folder/"elaborated_ast.json"
        ast=read_ast(ast_path)
        start=perf_counter()
        graph=build_dependency_graph(ast,expected_top=idx["top"],index=idx,enable_member_positions=True,enable_member_combinational=True)
        graph_seconds=perf_counter()-start
        graph=json.loads(json.dumps(graph))
        channel=graph["member_combinational_candidates"]
        positions=graph["member_position_candidates"]
        report["cases"].append({"name":name,"ast_sha256":sha256(ast_path),
            "index_sha256":sha256(folder/"rtl_index.json"),**channel,
            "position_channel_counts":positions["counts"],"position_channel":positions,
            "historical_bit_counts":graph["bit_dependency_graph"]["counts"],
            "opt_in_graph_build_seconds":graph_seconds})
        save()
        check_channel(channel,positions,name)
        # Preserve the existing graph content; only publication metrics may grow.
        excluded={"analysis_limits","source_fingerprint","member_position_candidates","member_combinational_candidates"}
        assert {k:v for k,v in graph.items() if k not in excluded}=={
            k:v for k,v in legacy_graph.items() if k not in excluded}
        assert not graph["analysis_limits"]["truncated_analyzers"]
        report["cases"][-1]["historical_graph_unchanged"]=True
        report["cases"][-1]["graph_publication_metrics"]=graph["analysis_limits"]["graph_metrics_excluding_this_report"]
        save()
    save()
    try:
        for top in ("local_members_pr82","member_expr_pr83","member_cond_pr85"):
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

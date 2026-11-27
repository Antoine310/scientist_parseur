"""Independent statement-coordinate oracle, real slang and controlled simulation."""
import argparse
import json
from pathlib import Path
import tempfile
from time import perf_counter
from rtlprep.analysis_budgets import read_ast
from rtlprep.census_query import file_sha,INPUTS
from rtlprep.vector_concat_nba import audit_vector_concat
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.rtl_fixtures import load_lock,verify_checkout
from scripts.run_priority_pr47 import simulate

ROOT=Path(__file__).resolve().parents[1]
TOP="vector_concat_nba_pr109"
FIXTURE=ROOT/"tests/fixtures/vector_concat_nba_pr109.sv"


def extract_fixture(folder):
    return extract(folder,FIXTURE.stem,[FIXTURE])


def check(name,result):
    c=result["counts"]
    expected={"fixture":(2,2,2,0,0,0,9,0),"alu":(0,0,0,0,0,0,0,0),
              "core":(5,0,0,0,0,0,0,5),"axis_register":(0,0,0,0,0,0,0,0),
              "priority_encoder":(0,0,0,0,0,0,0,0),"rxuart":(2,2,0,0,2,6,0,0)}
    assert tuple(c[k] for k in ("historical_unsupported_targets","concat_sites","new_sites","partial",
          "existing_pr106_sites","existing_pr106_records","new_records","other_unsupported_targets"))==expected[name],c
    assert result["historical_replay_exact"] and not result["historical_graph_promoted"]
    assert result["new_historical_edges"]==0
    if name=="rxuart":
        assert {r["source_location"]["line"] for r in result["items"]}=={179,181}
        assert all(r["coverage"]=="existing_pr106" and r["existing_record_count"]==3 and not r["records"] for r in result["items"])
    if name!="fixture":
        return
    expected_rows={
      ((0,"flag_q",0),(1,"word_q",2),(5,"word_q",3),(6,"word_q",4),(7,"word_q",5)),
      ((5,"split_q",0),(6,"split_q",1),(7,"split_q",2),(4,"split_q",3))}
    observed=set()
    for row in result["items"]:
        assert row["instance"]==TOP and row["historical_flat_assignment_id"] is None
        assert row["coverage"]=="new_vector_candidates"
        assert [r["concat_lsb_position"] for r in row["records"]]==list(range(len(row["records"])))
        assert all(r["source"]["signal"]==TOP+".data" and r["target"]["signal"].startswith(TOP+".") for r in row["records"])
        observed.add(tuple((r["source"]["bit"],r["target"]["signal"].removeprefix(TOP+"."),r["target"]["bit"]) for r in row["records"]))
    assert observed==expected_rows,(observed,expected_rows)


def execute(out,reference=None):
    out=out.resolve()
    lock=load_lock()
    for e in lock:
        root=(ROOT/e["destination"]).resolve()
        if out==root or out.is_relative_to(root):
            raise ValueError("output cannot be inside official RTL")
    out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out))
    path=run/"summary.json"
    report={"status":"incomplete","cases":[],"design_coverage":"not_measured",
            "functional_influence":"not_proven","rtl_equivalence":"not_performed"}
    def save(): path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    def case(name,folder,upstream=None):
        before={k:file_sha(folder/k) for k in INPUTS}
        ast=read_ast(folder/INPUTS[0])
        idx=json.loads((folder/INPUTS[1]).read_text())
        g=json.loads((folder/INPUTS[2]).read_text())
        start=perf_counter()
        result=audit_vector_concat(ast,idx,g)
        elapsed=perf_counter()-start
        detail=run/(name+".vector-concat.json")
        detail.write_text(json.dumps(result,indent=2),encoding="utf-8")
        check(name,result)
        assert before=={k:file_sha(folder/k) for k in INPUTS}
        report["cases"].append({"name":name,"input_sha256":before,"detail_file":detail.name,
             "detail_sha256":file_sha(detail),"audit_seconds":elapsed,"upstream":upstream,
             "historical_unchanged":True,**{k:v for k,v in result.items() if k not in ("items","other_targets")}})
        save()
    try:
        extract_fixture(run/"fixture")
        case("fixture",run/"fixture")
        counts,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.vector_concat_nba_pr109",run/"simulation")
        assert (counts["tests"],counts["passed"],counts["failed"],counts["skipped"])==(1,1,0,0)
        report["fixture_simulation"]={"status":"passed","binary_input_vectors":256,"output_checks_per_vector":3,
            "total_checks":768,"source_sha256":file_sha(FIXTURE)}
        save()
        ref=diagnostics(run/"reference") if reference is None else reference.resolve()
        d=json.loads(ref.read_text())
        assert d["status"]=="passed"
        case("alu",ref.parent/"alu")
        case("core",Path(d["core_reference_report"]).parent/"static")
        for e in lock:
            if e["repository"] not in ("alexforencich/verilog-axis","ZipCPU/wbuart32"): continue
            root=ROOT/e["destination"]
            verify_checkout(root,e)
            for src in e["blobs"]:
                name=Path(src).stem
                folder=run/name
                extract(folder,name,[root/src])
                case(name,folder,{"repository":e["repository"],"commit":e["commit"],"blob":e["blobs"][src]})
            verify_checkout(root,e)
        assert len(report["cases"])==6
        report["status"]="passed"
    except Exception as exc:
        report.update(status="failed",error=f"{type(exc).__name__}: {exc}"[:3000])
        raise
    finally:
        save()
        print(path.read_text(),flush=True)
        print(f"Summary: {path}",flush=True)
    return path


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--reference",type=Path)
    a=p.parse_args()
    execute(a.out,a.reference)

"""Reproduce historical stop decisions on fixture and pinned RTL."""
import argparse
import json
from pathlib import Path
import tempfile
from time import perf_counter
from rtlprep.analysis_budgets import read_ast
from rtlprep.census_query import file_sha, INPUTS
from rtlprep.walker_exclusion_audit import audit_walker
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.rtl_fixtures import load_lock,verify_checkout
from scripts.cv32e40p_pr67 import ast_inventory

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/"tests/fixtures/walker_exclusions_pr105.sv"
RX_LINES={174,175,176,197,216,236,250,262,298,408,438,461,462,487,522}


def check(name,result):
    counts=result["counts"]
    classes=counts["classification"]
    expected={"fixture":(5,1,3,0),"alu":(612,479,0,0),"core":(3811,1199,0,5),
              "axis_register":(44,4,0,0),"priority_encoder":(9,8,0,0),"rxuart":(87,16,15,2)}
    assert (counts["ast_occurrences"],counts["historical_rows"],len(result["nonvisited"]),
            len(result["unsupported_targets"]))==expected[name],counts
    assert result["unexplained"]==0 and result["historical_replay_exact"]
    assert result["new_edges"]==result["new_supported_rows"]==0
    assert sum(result["reason_counts"].values())==len(result["nonvisited"])
    if name=="fixture":
        assert result["reason_counts"]=={"excluded_procedure_kind":2,"unsupported_statement_kind":1}
        assert result["procedure_kind_counts"]=={"Initial":2}
        assert result["nonvisited_with_selection"]==2
        assert result["matched_exclusion_boundaries"]==2
        assert {r["boundary"]["kind"] for r in result["nonvisited"]}=={"ProceduralBlock","RepeatLoop"}
    if name=="rxuart":
        assert result["reason_counts"]=={"excluded_procedure_kind":15}
        assert result["procedure_kind_counts"]=={"Initial":15}
        assert result["matched_exclusion_boundaries"]==15
        assert result["nonvisited_with_selection"]==1
        assert {r["source"]["line"] for r in result["nonvisited"]}==RX_LINES
        assert all(r["boundary"]["kind"]=="ProceduralBlock" and r["boundary"]["procedure_kind"]=="Initial" for r in result["nonvisited"])
        assert {r["source"]["line"] for r in result["unsupported_targets"]}=={179,181}
        assert all(r["reason"]=="concatenation_target_outside_historical_target_gate" for r in result["unsupported_targets"])


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
            "functional_influence":"not_proven","formal_proof":"not_applicable_to_syntax_audit"}
    def save(): path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    def case(name,folder,upstream=None):
        before={k:file_sha(folder/k) for k in INPUTS}
        ast=read_ast(folder/INPUTS[0])
        idx=json.loads((folder/INPUTS[1]).read_text())
        graph=json.loads((folder/INPUTS[2]).read_text())
        start=perf_counter()
        result=audit_walker(ast,idx,graph)
        elapsed=perf_counter()-start
        detail=run/(name+".walker-exclusions.json")
        detail.write_text(json.dumps(result,indent=2),encoding="utf-8")
        check(name,result)
        prior=ast_inventory(ast,{r["path"]:r["module"] for r in idx["instances"]})
        assert prior["assignment_count"]==result["counts"]["ast_occurrences"]
        assert before=={k:file_sha(folder/k) for k in INPUTS}
        report["cases"].append({"name":name,"status":"passed","input_sha256":before,
             "detail_file":detail.name,"detail_sha256":file_sha(detail),"audit_seconds":elapsed,
             "upstream":upstream,"historical_unchanged":True,"pr67_census_reconciled":True,
             **{k:v for k,v in result.items() if k not in ("nonvisited","unsupported_targets")}})
        save()
    try:
        extract(run/"fixture","walker_exclusions_pr105",[FIXTURE])
        case("fixture",run/"fixture")
        ref=diagnostics(run/"reference") if reference is None else reference.resolve()
        d=json.loads(ref.read_text())
        assert d["status"]=="passed"
        case("alu",ref.parent/"alu")
        case("core",Path(d["core_reference_report"]).parent/"static")
        for e in lock:
            if e["repository"] not in ("alexforencich/verilog-axis","ZipCPU/wbuart32"):
                continue
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
    args=p.parse_args()
    execute(args.out,args.reference)

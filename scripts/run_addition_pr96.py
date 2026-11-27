"""Real slang/cocotb fixture and pinned residual addition census."""
import argparse
import json
from pathlib import Path
import tempfile
from time import perf_counter
from rtlprep.analysis_budgets import read_ast
from rtlprep.addition_candidates import audit_additions
from scripts.run_analysis_budgets_pr62 import extract
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.run_member_benchmark_pr91 import file_hash,digest
from scripts.run_priority_pr47 import simulate
from scripts.rtl_fixtures import load_lock

ROOT=Path(__file__).resolve().parents[1]
TOP="addition_pr96"
FIXTURE=ROOT/"tests/fixtures/addition_pr96.sv"


def check_fixture(result):
    assert result["counts"]=={"residual_ids":2,"roots":2,"supported":2,"partial":0,
                              "potential_pairs":1076,"stored_coordinates":108,"truncated":False},result
    rows={r["target"]:r["candidate"] for r in result["items"]}
    for suffix,n,operands in (("sum4",4,("a","b")),("sum32",32,("x","y"))):
        c=rows[TOP+"."+suffix]
        assert c["width"]==n and c["prefix_lengths"]==list(range(1,n+1))
        assert c["target"]["bits_lsb_first"]==list(range(n))
        assert [(e["signal"],e["outer_packed_indices"],e["bits_lsb_first"]) for e in c["operands"]]==[
            (TOP+"."+s,[],list(range(n))) for s in operands]
        assert c["potential_pairs"]==n*(n+1)


def execute(out,reference=None):
    out=out.resolve()
    for e in load_lock():
        root=(ROOT/e["destination"]).resolve()
        if out==root or out.is_relative_to(root):
            raise ValueError("output cannot be inside official RTL")
    out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out))
    path=run/"summary.json"
    report={"status":"incomplete","cases":[],"design_coverage":"not_measured",
            "functional_influence":"not_proven","formal_proof":"not_performed_in_this_runner"}
    def save(): path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    def case(name,folder,expected):
        files=("elaborated_ast.json","rtl_index.json","rtl_dependencies.json")
        hashes={f:file_hash(folder/f) for f in files}
        ast=read_ast(folder/files[0])
        idx=json.loads((folder/files[1]).read_text())
        g=json.loads((folder/files[2]).read_text())
        before=digest(g)
        start=perf_counter()
        result=audit_additions(ast,idx,g)
        elapsed=perf_counter()-start
        assert (result["counts"]["residual_ids"],result["counts"]["roots"])==expected
        assert result["counts"]["supported"]+result["counts"]["partial"]==expected[1]
        assert not result["counts"]["truncated"]
        assert digest(g)==before and hashes=={f:file_hash(folder/f) for f in files}
        if name=="fixture":
            check_fixture(result)
        detail=run/(name+".additions.json")
        detail.write_text(json.dumps(result,indent=2),encoding="utf-8")
        report["cases"].append({"name":name,"input_sha256":hashes,"audit_seconds":elapsed,
            "historical_unchanged":True,"detail_file":detail.name,
            **{k:v for k,v in result.items() if k!="items"}})
        save()
    try:
        extract(run/"fixture",TOP,[FIXTURE])
        case("fixture",run/"fixture",(2,2))
        counts,_=simulate([FIXTURE],TOP,"rtlprep.sim_tests.addition_pr96",run/"simulation")
        assert (counts["tests"],counts["passed"],counts["failed"],counts["skipped"])==(1,1,0,0)
        report["fixture_simulation"]={"status":"passed","vectors4":256,"vectors32":8,"checks":264}
        save()
        ref=diagnostics(run/"reference") if reference is None else reference.resolve()
        d=json.loads(ref.read_text())
        assert d["status"]=="passed"
        case("alu",ref.parent/"alu",(98,31))
        case("core",Path(d["core_reference_report"]).parent/"static",(384,64))
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

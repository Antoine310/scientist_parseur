"""PR97 frozen popcnt coordinate oracle and real RTL simulation."""
import argparse
import json
from pathlib import Path
import tempfile
from time import perf_counter
from rtlprep.analysis_budgets import read_ast
from rtlprep.addition_candidates import audit_additions
from rtlprep.zero_extended_additions import audit_zero_extended_additions
from scripts.run_cv32e40p_diagnostics_pr67 import execute as diagnostics
from scripts.run_member_benchmark_pr91 import file_hash,digest
from scripts.run_priority_pr47 import simulate
from scripts.rtl_fixtures import load_lock

ROOT=Path(__file__).resolve().parents[1]


def oracle(prefix):
    rows={}
    for level in range(1,6):
        count=32>>level
        for i in range(count):
            dst=prefix+("result_o" if level==5 else f"cnt_l{level}")
            src=prefix+("in_i" if level==1 else f"cnt_l{level-1}")
            outer=() if level==5 else (i,)
            endpoints=tuple((src,() if level==1 else (2*i+j,),
                             (2*i+j,) if level==1 else tuple(range(level)))
                            for j in range(2))
            rows[(dst,outer)]=(tuple(range(level+1)),endpoints)
    return rows


def check(result,name):
    prefix=("cv32e40p_alu.popcnt_i." if name=="alu" else
            "cv32e40p_core.ex_stage_i.alu_i.popcnt_i.")
    expected=oracle(prefix)
    actual={}
    good=[r for r in result["items"] if r["coverage"]=="addition_candidates"]
    for r in good:
        c=r["candidate"]
        dst=c["target"]
        k=(dst["signal"],tuple(dst["outer_packed_indices"]))
        assert k not in actual
        actual[k]=(tuple(dst["bits_lsb_first"]),tuple(
            (e["signal"],tuple(e["outer_packed_indices"]),tuple(e["bits_lsb_first"])) for e in c["operands"]))
        n=c["width"]
        assert c["prefix_lengths"]==list(range(1,n))+[n-1]
        assert c["potential_pairs"]==(n-1)*(n+2)
        assert all(e["extension"]["width"]==1 for e in c["operands"])
        assert all(e["selector_proofs"] for e in c["operands"])
    assert actual==expected,(actual.keys()-expected.keys(),expected.keys()-actual.keys())
    counts=result["counts"]
    assert counts["supported"]==31 and counts["potential_pairs"]==312
    assert counts["stored_coordinates"]==202 and not counts["truncated"]
    assert counts["partial"]==(0 if name=="alu" else 33)


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
    try:
        ref=diagnostics(run/"reference") if reference is None else reference.resolve()
        d=json.loads(ref.read_text())
        assert d["status"]=="passed"
        core=Path(d["core_reference_report"]).parent
        for name,folder,n,roots in (("alu",ref.parent/"alu",98,31),("core",core/"static",384,64)):
            files=("elaborated_ast.json","rtl_index.json","rtl_dependencies.json")
            hashes={f:file_hash(folder/f) for f in files}
            ast=read_ast(folder/files[0])
            idx=json.loads((folder/files[1]).read_text())
            g=json.loads((folder/files[2]).read_text())
            before=digest(g)
            old=audit_additions(ast,idx,g)
            start=perf_counter()
            result=audit_zero_extended_additions(ast,idx,g)
            elapsed=perf_counter()-start
            assert (result["counts"]["residual_ids"],result["counts"]["roots"])==(n,roots)
            assert old["counts"]["supported"]==0
            assert [r["flat_assignment_id"] for r in old["items"]]==[r["flat_assignment_id"] for r in result["items"]]
            check(result,name)
            assert digest(g)==before and hashes=={f:file_hash(folder/f) for f in files}
            detail=run/(name+".zero-additions.json")
            detail.write_text(json.dumps(result,indent=2),encoding="utf-8")
            report["cases"].append({"name":name,"input_sha256":hashes,"audit_seconds":elapsed,
                "historical_unchanged":True,"detail_file":detail.name,"pr96_counts":old["counts"],
                **{k:v for k,v in result.items() if k!="items"}})
            save()
        source=core/"official_sources/rtl/cv32e40p_popcnt.sv"
        assert source.is_file()
        sha=file_hash(source)
        counts,_=simulate([source],"cv32e40p_popcnt","rtlprep.sim_tests.popcnt_pr97",run/"simulation")
        assert (counts["tests"],counts["passed"],counts["failed"],counts["skipped"])==(1,1,0,0)
        assert sha==file_hash(source)
        report["real_popcnt_simulation"]={"status":"passed","checks":196,"source_sha256":sha}
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

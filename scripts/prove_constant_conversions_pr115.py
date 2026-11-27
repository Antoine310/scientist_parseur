"""Exact defined-binary constant conversion models, no RTL equivalence."""
import argparse,json,subprocess,tempfile
from pathlib import Path


def execute(out):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out));path=run/"summary.json"
    report={"status":"incomplete","scope":"binary_constant_conversion_models",
            "rtl_equivalence":"not_performed","temporal_proof":"not_performed"}
    def save(): path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    try:
        report["z3_version"]=subprocess.check_output(["z3","--version"],text=True,timeout=10).strip()
        lines=["(set-logic QF_BV)","(set-option :timeout 10000)","(declare-fun j () (_ BitVec 32))"]
        queries=[("zero_extend_32_64","(distinct ((_ zero_extend 32) (_ bv0 32)) (_ bv0 64))","unsat"),
                 ("zero_state_binary_identity","(distinct (_ bv0 32) #x00000000)","unsat"),
                 ("zero_truncate_32_16","(distinct ((_ extract 15 0) (_ bv0 32)) (_ bv0 16))","unsat")]
        for i in range(32):
            queries.append((f"index_{i}",f"(distinct ((_ extract 4 0) (_ bv{i} 32)) (_ bv{i} 5))","unsat"))
        queries.extend([("mutant_drop_index_msb","(and (= j (_ bv16 32)) (distinct ((_ extract 4 0) j) ((_ zero_extend 1) ((_ extract 3 0) j))))","sat"),
                        ("mutant_off_by_one","(and (= j (_ bv31 32)) (distinct ((_ extract 4 0) j) (bvadd ((_ extract 4 0) j) (_ bv1 5))))","sat"),
                        ("mutant_nonzero_fill","(distinct ((_ zero_extend 32) (_ bv0 32)) (concat #xffffffff #x00000000))","sat")])
        assert len(queries)==38
        for name,expr,expected in queries:
            lines.extend(["(push 1)",f"(assert {expr})","(check-sat)","(pop 1)"])
        smt=run/"constant-conversions.smt2"
        smt.write_text("\n".join(lines+["(exit)"])+"\n",encoding="utf-8")
        p=subprocess.run(["z3","-smt2",str(smt)],capture_output=True,text=True,timeout=120)
        (run/"stdout.log").write_text(p.stdout,encoding="utf-8");(run/"stderr.log").write_text(p.stderr,encoding="utf-8")
        actual=p.stdout.splitlines()
        report["queries"]=[{"name":name,"expected":expected,"actual":actual[i] if i<len(actual) else None}
                           for i,(name,_,expected) in enumerate(queries)]
        assert p.returncode==0 and actual==[q[2] for q in queries],(p.stdout,p.stderr)
        report.update(status="passed",query_count=len(queries),unsat=35,sat=3)
    except Exception as exc:
        report.update(status="failed",error=f"{type(exc).__name__}: {exc}"[:1000]);raise
    finally:
        save();print(path.read_text(),flush=True);print(f"Summary: {path}",flush=True)
    return path


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--out",type=Path,required=True)
    execute(p.parse_args().out)

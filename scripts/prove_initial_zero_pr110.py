"""Zero conversion models and counterexamples to permanent zero."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile


def execute(out):
    out=out.resolve()
    out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out))
    path=run/"summary.json"
    report={"status":"incomplete","scope":"binary_zero_conversion_and_update_models",
            "rtl_equivalence":"not_performed","temporal_proof":"not_performed"}
    def save(): path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    try:
        report["z3_version"]=subprocess.check_output(["z3","--version"],text=True,timeout=10).strip()
        lines=["(set-logic QF_BV)","(set-option :timeout 10000)"]
        queries=[]
        for n in (1,4,8,28):
            lines.append(f"(declare-fun next{n} () (_ BitVec {n}))")
            lines.append(f"(define-fun init{n} () (_ BitVec {n}) ((_ extract {n-1} 0) (_ bv0 32)))")
            queries.extend([(f"zero_resize_{n}",f"(distinct init{n} (_ bv0 {n}))","unsat"),
                            (f"mutant_nonzero_{n}",f"(distinct init{n} (_ bv1 {n}))","sat"),
                            (f"not_permanent_zero_{n}",f"(distinct next{n} init{n})","sat")])
        for name,expr,expected in queries:
            lines.extend(["(push 1)",f"(assert {expr})","(check-sat)","(pop 1)"])
        smt=run/"initial-zero.smt2"
        smt.write_text("\n".join(lines+["(exit)"])+"\n",encoding="utf-8")
        p=subprocess.run(["z3","-smt2",str(smt)],capture_output=True,text=True,timeout=120)
        (run/"stdout.log").write_text(p.stdout,encoding="utf-8")
        (run/"stderr.log").write_text(p.stderr,encoding="utf-8")
        actual=p.stdout.splitlines()
        report["queries"]=[{"name":n,"expected":e,"actual":actual[i] if i<len(actual) else None} for i,(n,_,e) in enumerate(queries)]
        assert p.returncode==0 and actual==[e for _,_,e in queries],(p.stdout,p.stderr)
        report.update(status="passed",query_count=12,unsat=4,sat=8)
    except Exception as exc:
        report.update(status="failed",error=f"{type(exc).__name__}: {exc}"[:1000])
        raise
    finally:
        save()
        print(path.read_text(),flush=True)
        print(f"Summary: {path}",flush=True)
    return path


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    execute(p.parse_args().out)

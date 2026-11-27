"""Defined-binary fixed selection model; not RTL equivalence."""
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
    report={"status":"incomplete","scope":"binary_fixed_select_nba_statement_models",
            "rtl_equivalence":"not_performed","temporal_proof":"not_performed"}
    def save(): path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    try:
        report["z3_version"]=subprocess.check_output(["z3","--version"],text=True,timeout=10).strip()
        lines=["(set-logic QF_BV)","(set-option :timeout 10000)",
               "(declare-fun x () (_ BitVec 32))"]
        queries=[]
        for n,lo in ((1,2),(4,4),(32,0)):
            expr=f"((_ extract {lo+n-1} {lo}) x)"
            oracle=f"((_ extract {n-1} 0) (bvlshr x (_ bv{lo} 32)))"
            lines.append(f"(define-fun f{n} () (_ BitVec {n}) {expr})")
            queries.append((f"equivalence_{n}",f"(distinct f{n} {oracle})","unsat"))
            for i in range(n):
                changed=f"((_ extract {lo+n-1} {lo}) (bvxor x (_ bv{1<<(lo+i)} 32)))"
                queries.append((f"witness_{n}_{i}",f"(distinct f{n} {changed})","sat"))
            queries.append((f"mutant_{n}",f"(distinct f{n} (bvxor f{n} (_ bv1 {n})))","sat"))
        for name,expr,expected in queries:
            lines.extend(["(push 1)",f"(assert {expr})","(check-sat)","(pop 1)"])
        smt=run/"generate-nba.smt2"
        smt.write_text("\n".join(lines+["(exit)"])+"\n",encoding="utf-8")
        p=subprocess.run(["z3","-smt2",str(smt)],capture_output=True,text=True,timeout=120)
        (run/"stdout.log").write_text(p.stdout,encoding="utf-8")
        (run/"stderr.log").write_text(p.stderr,encoding="utf-8")
        actual=p.stdout.splitlines()
        report["queries"]=[{"name":n,"expected":e,"actual":actual[i] if i<len(actual) else None}
                           for i,(n,_,e) in enumerate(queries)]
        assert p.returncode==0 and actual==[e for _,_,e in queries],(p.stdout,p.stderr)
        report.update(status="passed",query_count=43,unsat=3,sat=40)
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

"""Defined-binary statement models, not an RTL or temporal proof."""
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
    report={"status":"incomplete","scope":"binary_scalar_concat_statement_model",
            "rtl_equivalence":"not_performed","temporal_proof":"not_performed"}
    def save(): path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    try:
        report["z3_version"]=subprocess.check_output(["z3","--version"],text=True,timeout=10).strip()
        lines=["(set-logic QF_BV)","(set-option :timeout 10000)",
               "(declare-fun old () (_ BitVec 3))","(declare-fun inp () (_ BitVec 1))",
               "(define-fun copied () (_ BitVec 3) (concat ((_ extract 1 1) old) (concat ((_ extract 0 0) old) inp)))",
               "(define-fun oracle () (_ BitVec 3) (bvor (bvshl old #b001) ((_ zero_extend 2) inp)))",
               "(define-fun zero () (_ BitVec 3) (concat #b0 (concat #b0 #b0)))"]
        queries=[("copy_equivalence","(distinct copied oracle)","unsat"),
                 ("zero_equivalence","(distinct zero #b000)","unsat"),
                 ("copy_q_sensitivity","(distinct copied (concat ((_ extract 1 1) old) (concat (bvnot ((_ extract 0 0) old)) inp)))","sat"),
                 ("copy_qq_sensitivity","(distinct copied (concat (bvnot ((_ extract 1 1) old)) (concat ((_ extract 0 0) old) inp)))","sat"),
                 ("copy_input_sensitivity","(distinct copied (concat ((_ extract 1 0) old) (bvnot inp)))","sat"),
                 ("mutant_swapped","(distinct copied (concat ((_ extract 0 0) old) (concat ((_ extract 1 1) old) inp)))","sat"),
                 ("mutant_hold","(distinct copied old)","sat"),
                 ("mutant_nonzero","(distinct zero #b001)","sat")]
        for name,expr,expected in queries:
            lines.extend(["(push 1)",f"(assert {expr})","(check-sat)","(pop 1)"])
        smt=run/"concat-nba.smt2"
        smt.write_text("\n".join(lines+["(exit)"])+"\n",encoding="utf-8")
        p=subprocess.run(["z3","-smt2",str(smt)],capture_output=True,text=True,timeout=120)
        (run/"stdout.log").write_text(p.stdout,encoding="utf-8")
        (run/"stderr.log").write_text(p.stderr,encoding="utf-8")
        actual=p.stdout.splitlines()
        report["queries"]=[{"name":n,"expected":e,"actual":actual[i] if i<len(actual) else None}
                           for i,(n,_,e) in enumerate(queries)]
        assert p.returncode==0 and actual==[e for _,_,e in queries],(p.stdout,p.stderr)
        report.update(status="passed",query_count=8,unsat=2,sat=6)
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

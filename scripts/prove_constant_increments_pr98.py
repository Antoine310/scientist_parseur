"""Z3 proof for abstract binary increments, not RTL equivalence."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

def execute(out):
    out=out.resolve()
    out.mkdir(parents=True,exist_ok=True)
    out=Path(tempfile.mkdtemp(prefix="run-",dir=out))
    path=out/"summary.json"
    report={"status":"incomplete","scope":"independent_binary_constant_increment_model",
            "rtl_equivalence":"not_performed","cases":[]}
    def save(): path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    try:
        report["z3_version"]=subprocess.check_output(["z3","--version"],text=True,timeout=10).strip()
        for n,shift in ((4,0),(64,0),(32,2)):
            m=n-shift
            lines=["(set-logic QF_BV)","(set-option :timeout 10000)",
                f"(declare-fun a () (_ BitVec {m}))",f"(declare-fun b () (_ BitVec {m}))"]
            expr=f"(bvadd x (_ bv1 {m}))"
            if shift:
                expr=f"(concat {expr} (_ bv0 {shift}))"
            lines.append(f"(define-fun inc ((x (_ BitVec {m}))) (_ BitVec {n}) {expr})")
            expected=[]
            def query(conditions,answer):
                lines.append("(push 1)")
                lines.extend(f"(assert {x})" for x in conditions)
                lines.extend(["(check-sat)","(pop 1)"])
                expected.append(answer)
            for i in range(n):
                p=max(0,i-shift+1)
                mask=(1<<p)-1
                query([f"(= (bvand a (_ bv{mask} {m})) (bvand b (_ bv{mask} {m})))",
                       f"(distinct ((_ extract {i} {i}) (inc a)) ((_ extract {i} {i}) (inc b)))"],"unsat")
                for j in range(p):
                    query([f"(distinct ((_ extract {i} {i}) (inc a)) "
                           f"((_ extract {i} {i}) (inc (bvxor a (_ bv{1<<j} {m})))))"],"sat")
            if shift:
                query([f"(distinct ((_ extract {shift-1} 0) (inc a)) (_ bv0 {shift}))"],"unsat")
            mutant=f"(bvxor a (_ bv1 {m}))"
            if shift:
                mutant=f"(concat {mutant} (_ bv0 {shift}))"
            query([f"(distinct (inc a) {mutant})"],"sat")
            lines.append("(exit)")
            file=out/f"increment-{n}.smt2"
            file.write_text("\n".join(lines)+"\n",encoding="utf-8")
            p=subprocess.run(["z3","-smt2",str(file)],capture_output=True,text=True,timeout=120)
            (out/f"increment-{n}.stdout.log").write_text(p.stdout,encoding="utf-8")
            (out/f"increment-{n}.stderr.log").write_text(p.stderr,encoding="utf-8")
            if p.returncode or p.stdout.splitlines()!=expected:
                raise AssertionError(f"SMT disagreement for width {n}")
            report["cases"].append({"width":n,"low_zero_bits":shift,"noninterference_unsat":n,
                "alignment_zero_unsat":int(bool(shift)),"included_pair_witness_sat":m*(m+1)//2,
                "carry_free_mutant_sat":1})
            save()
        report["status"]="passed"
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

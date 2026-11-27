"""Z3 proof of the independent widened binary addition model."""
import argparse
import json
from pathlib import Path
import subprocess

def execute(out):
    out=out.resolve()
    out.mkdir(parents=True,exist_ok=True)
    path=out/"summary.json"
    report={"status":"incomplete","scope":"independent_zero_extended_binary_addition_model",
            "rtl_equivalence":"not_performed","cases":[]}
    def save(): path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    try:
        report["z3_version"]=subprocess.check_output(["z3","--version"],text=True,timeout=10).strip()
        for m in range(1,6):
            n=m+1
            lines=["(set-logic QF_BV)","(set-option :timeout 10000)"]
            for v in ("a","b","aa","bb"):
                lines.append(f"(declare-fun {v} () (_ BitVec {m}))")
            lines.append(f"(define-fun sum ((x (_ BitVec {m})) (y (_ BitVec {m}))) (_ BitVec {n}) (bvadd ((_ zero_extend 1) x) ((_ zero_extend 1) y)))")
            expected=[]
            def query(conditions,answer):
                lines.append("(push 1)")
                lines.extend(f"(assert {x})" for x in conditions)
                lines.extend(["(check-sat)","(pop 1)"])
                expected.append(answer)
            for i in range(n):
                mask=(1<<min(i+1,m))-1
                query([f"(= (bvand a (_ bv{mask} {m})) (bvand aa (_ bv{mask} {m})))",
                       f"(= (bvand b (_ bv{mask} {m})) (bvand bb (_ bv{mask} {m})))",
                       f"(distinct ((_ extract {i} {i}) (sum a b)) ((_ extract {i} {i}) (sum aa bb)))"],"unsat")
                for j in range(min(i+1,m)):
                    for side in ("a","b"):
                        other="b" if side=="a" else "a"
                        query([f"(distinct ((_ extract {i} {i}) (sum a b)) ((_ extract {i} {i}) (sum (bvxor {side} (_ bv{1<<j} {m})) {other})))"],"sat")
            query([f"(distinct (sum a b) ((_ zero_extend 1) (bvadd a b)))"],"sat")
            lines.append("(exit)")
            file=out/f"zero-add-{m}.smt2"
            file.write_text("\n".join(lines)+"\n",encoding="utf-8")
            p=subprocess.run(["z3","-smt2",str(file)],capture_output=True,text=True,timeout=120)
            (out/f"zero-add-{m}.stdout.log").write_text(p.stdout,encoding="utf-8")
            (out/f"zero-add-{m}.stderr.log").write_text(p.stderr,encoding="utf-8")
            if p.returncode or p.stdout.splitlines()!=expected:
                raise AssertionError(f"SMT disagreement for width {m}")
            report["cases"].append({"operand_width":m,"result_width":n,"noninterference_unsat":n,
                "included_pair_witness_sat":m*(m+3),"lost_carry_mutant_sat":1})
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

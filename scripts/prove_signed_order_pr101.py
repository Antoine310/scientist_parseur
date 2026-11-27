"""Independent QF_BV controlled signed order models; not RTL equivalence."""
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
    report={"status":"incomplete","scope":"defined_binary_controlled_signed_order_models",
            "rtl_equivalence":"not_performed","cases":[]}
    def save(): path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    def query(lines,expected,condition,answer):
        lines.extend(["(push 1)",f"(assert {condition})","(check-sat)","(pop 1)"])
        expected.append(answer)
    def solve(name,lines,expected):
        file=run/(name+".smt2")
        file.write_text("\n".join(lines+["(exit)"])+"\n",encoding="utf-8")
        p=subprocess.run(["z3","-smt2",str(file)],capture_output=True,text=True,timeout=120)
        (run/(name+".stdout.log")).write_text(p.stdout,encoding="utf-8")
        (run/(name+".stderr.log")).write_text(p.stderr,encoding="utf-8")
        assert p.returncode==0 and p.stdout.splitlines()==expected,(name,p.stdout,p.stderr)
        report["cases"].append({"name":name,"queries":len(expected),"sat":expected.count("sat"),"unsat":expected.count("unsat")})
        save()
    save()
    try:
        report["z3_version"]=subprocess.check_output(["z3","--version"],text=True,timeout=10).strip()
        for n in (2,4,8,32):
            lines=["(set-logic QF_BV)","(set-option :timeout 10000)",
                   f"(declare-fun a () (_ BitVec {n}))",
                   f"(declare-fun b () (_ BitVec {n}))",
                   "(declare-fun c () (_ BitVec 1))",
                   f"(define-fun ext ((x (_ BitVec {n})) (m (_ BitVec 1))) (_ BitVec {n+1}) (concat (bvand ((_ extract {n-1} {n-1}) x) m) x))",
                   f"(define-fun cmp ((x (_ BitVec {n})) (y (_ BitVec {n})) (m (_ BitVec 1))) Bool (bvsgt (ext x m) (ext y m)))"]
            expected=[]
            model="(cmp a b c)"
            oracle="(ite (= c #b1) (bvsgt a b) (bvugt a b))"
            query(lines,expected,f"(distinct {model} {oracle})","unsat")
            for j in range(n):
                for side in ("a","b"):
                    toggle=f"(bvxor {side} (_ bv{1<<j} {n}))"
                    other=f"(cmp {toggle} b c)" if side=="a" else f"(cmp a {toggle} c)"
                    query(lines,expected,f"(distinct {model} {other})","sat")
            query(lines,expected,f"(distinct {model} (cmp a b (bvxor c #b1)))","sat")
            for mutant in ("(cmp a b #b0)","(cmp a b #b1)","(bvugt (ext a c) (ext b c))"):
                query(lines,expected,f"(distinct {model} {mutant})","sat")
            solve(f"controlled-signed-{n}",lines,expected)
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

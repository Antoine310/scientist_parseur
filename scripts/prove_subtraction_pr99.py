"""Independent QF_BV subtraction and shift-mask proofs, not RTL equivalence."""
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
    report={"status":"incomplete","scope":"independent_binary_subtraction_and_shift_mask_models",
            "rtl_equivalence":"not_performed","cases":[]}
    def save(): path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    def solve(name,lines,expected,counts):
        lines.append("(exit)")
        file=out/(name+".smt2")
        file.write_text("\n".join(lines)+"\n",encoding="utf-8")
        p=subprocess.run(["z3","-smt2",str(file)],capture_output=True,text=True,timeout=120)
        (out/(name+".stdout.log")).write_text(p.stdout,encoding="utf-8")
        (out/(name+".stderr.log")).write_text(p.stderr,encoding="utf-8")
        if p.returncode or p.stdout.splitlines()!=expected:
            raise AssertionError(f"SMT disagreement for {name}")
        report["cases"].append({"name":name,"queries":len(expected),**counts})
        save()
    def query(lines,expected,conditions,answer):
        lines.append("(push 1)")
        lines.extend(f"(assert {x})" for x in conditions)
        lines.extend(["(check-sat)","(pop 1)"])
        expected.append(answer)
    save()
    try:
        report["z3_version"]=subprocess.check_output(["z3","--version"],text=True,timeout=10).strip()
        for n in (2,4,32):
            lines=["(set-logic QF_BV)","(set-option :timeout 10000)"]
            for v in ("a","b","aa","bb"):
                lines.append(f"(declare-fun {v} () (_ BitVec {n}))")
            expected=[]
            for i in range(n):
                mask=(1<<(i+1))-1
                query(lines,expected,[f"(= (bvand a (_ bv{mask} {n})) (bvand aa (_ bv{mask} {n})))",
                    f"(= (bvand b (_ bv{mask} {n})) (bvand bb (_ bv{mask} {n})))",
                    f"(distinct ((_ extract {i} {i}) (bvsub a b)) ((_ extract {i} {i}) (bvsub aa bb)))"],"unsat")
                for j in range(i+1):
                    for side in ("a","b"):
                        toggle=f"(bvxor {side} (_ bv{1<<j} {n}))"
                        expr=f"(bvsub {toggle} b)" if side=="a" else f"(bvsub a {toggle})"
                        query(lines,expected,[f"(distinct ((_ extract {i} {i}) (bvsub a b)) ((_ extract {i} {i}) {expr}))"],"sat")
            query(lines,expected,["(distinct (bvsub a b) (bvxor a b))"],"sat")
            solve(f"subtract-{n}",lines,expected,{"width":n,"noninterference_unsat":n,
                  "included_pair_witness_sat":n*(n+1),"borrow_free_mutant_sat":1})
        lines=["(set-logic QF_BV)","(set-option :timeout 10000)",
               "(declare-fun k () (_ BitVec 5))","(declare-fun kk () (_ BitVec 5))",
               "(define-fun mask ((x (_ BitVec 5))) (_ BitVec 32) (bvsub (bvshl (_ bv1 32) ((_ zero_extend 27) x)) (_ bv1 32)))"]
        expected=[]
        # Derive expected support by exhaustive integer toggles, independently
        # of the analyzer's threshold suffix formula.
        pairs={(j,i) for x in range(32) for j in range(5) for i in range(32)
               if (((1<<x)-1)^((1<<(x^(1<<j)))-1))&(1<<i)}
        for i in range(32):
            bits=sum(1<<j for j in range(5) if (j,i) in pairs)
            query(lines,expected,[f"(= (bvand k (_ bv{bits} 5)) (bvand kk (_ bv{bits} 5)))",
                f"(distinct ((_ extract {i} {i}) (mask k)) ((_ extract {i} {i}) (mask kk)))"],"unsat")
            for j in range(5):
                if (j,i) in pairs:
                    query(lines,expected,[f"(distinct ((_ extract {i} {i}) (mask k)) ((_ extract {i} {i}) (mask (bvxor k (_ bv{1<<j} 5)))))"],"sat")
        # Independent closed-form truth table, all 32 possible k.
        table="(_ bv2147483647 32)"
        for k in reversed(range(31)):
            table=f"(ite (= k (_ bv{k} 5)) (_ bv{(1<<k)-1} 32) {table})"
        query(lines,expected,[f"(distinct (mask k) {table})"],"unsat")
        query(lines,expected,["(distinct ((_ extract 31 31) (mask k)) #b0)"],"unsat")
        query(lines,expected,["(distinct (mask k) (bvshl (_ bv1 32) ((_ zero_extend 27) k)))"],"sat")
        solve("shift-mask",lines,expected,{"shift_width":5,"width":32,"noninterference_unsat":32,
              "included_pair_witness_sat":len(pairs),"truth_table_unsat":1,"constant_high_bit_unsat":1,"mutant_sat":1})
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

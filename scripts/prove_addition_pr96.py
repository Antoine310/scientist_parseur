"""Independent SMT-LIB proof for the modular addition model, not RTL equivalence."""
import argparse
import json
from pathlib import Path
import subprocess


def execute(out):
    out=out.resolve()
    out.mkdir(parents=True,exist_ok=True)
    report={"status":"incomplete","scope":"independent_binary_modular_addition_model_only",
            "rtl_equivalence":"not_performed","design_coverage":"not_measured","cases":[]}
    summary=out/"summary.json"
    def save(): summary.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    try:
        report["z3_version"]=subprocess.check_output(["z3","--version"],text=True,timeout=10).strip()
        for n in (4,32):
            lines=["(set-logic QF_BV)", "(set-option :timeout 10000)"]
            for v in ("a","b","aa","bb"):
                lines.append(f"(declare-fun {v} () (_ BitVec {n}))")
            expected=[]
            for i in range(n):
                # Arbitrary independent upper bits, equal lower prefixes.
                mask=(1<<(i+1))-1
                lines.extend(["(push 1)",
                    f"(assert (= (bvand a (_ bv{mask} {n})) (bvand aa (_ bv{mask} {n}))))",
                    f"(assert (= (bvand b (_ bv{mask} {n})) (bvand bb (_ bv{mask} {n}))))",
                    f"(assert (distinct ((_ extract {i} {i}) (bvadd a b)) ((_ extract {i} {i}) (bvadd aa bb))))",
                    "(check-sat)","(pop 1)"])
                expected.append("unsat")
            # Each included bit has a witness in the independent-input model.
            # Toggle exactly one operand bit, preserve the other operand.
            for i in range(n):
                for j in range(i+1):
                    for side in ("a","b"):
                        other="b" if side=="a" else "a"
                        toggle=f"(bvxor {side} (_ bv{1<<j} {n}))"
                        lines.extend(["(push 1)",
                            f"(assert (distinct ((_ extract {i} {i}) (bvadd a b)) "
                            f"((_ extract {i} {i}) (bvadd {toggle} {other}))))",
                            "(check-sat)","(pop 1)"])
                        expected.append("sat")
            # A carry-free XOR mutant is distinguishable from addition.
            lines.extend(["(push 1)","(assert (distinct (bvadd a b) (bvxor a b)))",
                          "(check-sat)","(pop 1)","(exit)"])
            expected.append("sat")
            file=out/f"addition-{n}.smt2"
            file.write_text("\n".join(lines)+"\n",encoding="utf-8")
            p=subprocess.run(["z3","-smt2",str(file)],capture_output=True,text=True,timeout=120)
            (out/f"addition-{n}.stdout.log").write_text(p.stdout,encoding="utf-8")
            (out/f"addition-{n}.stderr.log").write_text(p.stderr,encoding="utf-8")
            actual=p.stdout.splitlines()
            if p.returncode or actual!=expected:
                raise AssertionError(f"SMT result disagreement width {n}: {p.returncode}, {actual[:10]}")
            report["cases"].append({"width":n,"noninterference_unsat":n,
                "included_pair_witness_sat":n*(n+1),"xor_mutant_distinguishable_sat":1})
            save()
        report["status"]="passed"
    except Exception as exc:
        report.update(status="failed",error=f"{type(exc).__name__}: {exc}"[:1000])
        raise
    finally:
        save()
        print(summary.read_text(),flush=True)
        print(f"Summary: {summary}",flush=True)
    return summary


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    execute(p.parse_args().out)

"""Independent QF_BV equality models; not RTL equivalence."""
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
    report={"status":"incomplete","scope":"defined_binary_comparison_models",
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
        for n in (2,8,32):
            for op in ("=","distinct"):
                lines=["(set-logic QF_BV)","(set-option :timeout 10000)",
                       f"(declare-fun a () (_ BitVec {n}))",f"(declare-fun b () (_ BitVec {n}))"]
                expected=[]
                model=f"({op} a b)"
                bitwise="(and "+" ".join(f"(= ((_ extract {j} {j}) a) ((_ extract {j} {j}) b))" for j in range(n))+")"
                oracle=bitwise if op=="=" else f"(not {bitwise})"
                query(lines,expected,f"(distinct {model} {oracle})","unsat")
                for j in range(n):
                    for side in ("a","b"):
                        toggle=f"(bvxor {side} (_ bv{1<<j} {n}))"
                        other=f"({op} {toggle} b)" if side=="a" else f"({op} a {toggle})"
                        query(lines,expected,f"(distinct {model} {other})","sat")
                mutant=f"({op} ((_ extract 0 0) a) ((_ extract 0 0) b))"
                query(lines,expected,f"(distinct {model} {mutant})","sat")
                solve(f"direct-{n}-{'eq' if op=='=' else 'ne'}",lines,expected)
        for op,value in (("=",2),("distinct",3)):
            lines=["(set-logic QF_BV)","(set-option :timeout 10000)","(declare-fun a () (_ BitVec 2))"]
            expected=[]
            model=f"({op} a (_ bv{value} 2))"
            # Independent truth table for all defined inputs.
            cases=[f"(= a (_ bv{i} 2))" for i in range(4) if (i==value)==(op=="=")]
            oracle=cases[0] if len(cases)==1 else "(or "+" ".join(cases)+")"
            query(lines,expected,f"(distinct {model} {oracle})","unsat")
            for j in range(2):
                query(lines,expected,f"(distinct {model} ({op} (bvxor a (_ bv{1<<j} 2)) (_ bv{value} 2)))","sat")
            query(lines,expected,f"(distinct {model} ({op} a (_ bv{value^1} 2)))","sat")
            solve(f"constant-{value}",lines,expected)
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

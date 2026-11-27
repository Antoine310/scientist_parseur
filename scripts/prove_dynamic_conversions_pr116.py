"""Compare explicit positional models to SMT built-ins; not RTL equivalence."""
import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from rtlprep.dynamic_conversion_candidates import position_map


def execute(out):
    out=out.resolve(); out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out))
    path=run/"summary.json"
    report={"status":"incomplete","scope":"binary_dynamic_conversion_models",
            "rtl_equivalence":"not_performed","temporal_proof":"not_performed"}
    def save(): path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    try:
        report["z3_version"]=subprocess.check_output(["z3","--version"],text=True,timeout=10).strip()
        lines=["(set-logic QF_BV)","(set-option :timeout 10000)"]
        queries=[]
        for a,b,signed in [(4,8,False),(4,8,True),(8,4,False),(16,32,False),(4,4,True)]:
            key=f"x{len(queries)}"
            lines.append(f"(declare-fun {key} () (_ BitVec {a}))")
            _,positions=position_map((a-1,0,signed,True),(b-1,0,signed,True))
            bits=["#b0" if p is None else f"((_ extract {p} {p}) {key})" for p in reversed(positions)]
            actual=bits[0]
            for bit in bits[1:]: actual=f"(concat {actual} {bit})"
            if b>a:
                op="sign_extend" if signed else "zero_extend"
                expected=f"((_ {op} {b-a}) {key})"
            elif b<a: expected=f"((_ extract {b-1} 0) {key})"
            else: expected=key
            queries.append((f"{a}_{b}_{signed}",f"(distinct {actual} {expected})","unsat"))
        queries.extend([
            ("wrong_sign_fill","(distinct ((_ sign_extend 4) x1) ((_ zero_extend 4) x1))","sat"),
            ("wrong_truncation","(distinct ((_ extract 3 0) x2) ((_ extract 7 4) x2))","sat"),
            ("wrong_zero_fill","(distinct ((_ zero_extend 4) x0) (concat #b1111 x0))","sat")])
        for _,expr,_ in queries:
            lines.extend(["(push 1)",f"(assert {expr})","(check-sat)","(pop 1)"])
        smt=run/"models.smt2"; smt.write_text("\n".join(lines+["(exit)"])+"\n")
        p=subprocess.run(["z3","-smt2",str(smt)],capture_output=True,text=True,timeout=120)
        (run/"stdout.log").write_text(p.stdout); (run/"stderr.log").write_text(p.stderr)
        actual=p.stdout.splitlines()
        report["queries"]=[{"name":q[0],"expected":q[2],"actual":actual[i] if i<len(actual) else None} for i,q in enumerate(queries)]
        assert p.returncode==0 and actual==[q[2] for q in queries],(p.stdout,p.stderr)
        report.update(status="passed",query_count=8,unsat=5,sat=3)
    except Exception as exc:
        report.update(status="failed",error=f"{type(exc).__name__}: {exc}"[:1000]); raise
    finally:
        save(); print(path.read_text()); print(f"Summary: {path}")
    return path


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--out",type=Path,required=True)
    execute(p.parse_args().out)

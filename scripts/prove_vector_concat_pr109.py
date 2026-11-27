"""Independent binary models for mixed-width vector concat; not RTL equivalence."""
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
    report={"status":"incomplete","scope":"binary_vector_concat_statement_models",
            "rtl_equivalence":"not_performed","temporal_proof":"not_performed"}
    def save(): path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    try:
        report["z3_version"]=subprocess.check_output(["z3","--version"],text=True,timeout=10).strip()
        lines=["(set-logic QF_BV)","(set-option :timeout 10000)","(declare-fun x () (_ BitVec 8))",
               "(define-fun a ((v (_ BitVec 8))) (_ BitVec 5) (concat ((_ extract 7 5) v) ((_ extract 1 0) v)))",
               "(define-fun b ((v (_ BitVec 8))) (_ BitVec 4) (concat ((_ extract 4 4) v) ((_ extract 7 5) v)))",
               "(define-fun oa () (_ BitVec 5) (bvor (bvshl ((_ zero_extend 2) ((_ extract 7 5) x)) #b00010) ((_ zero_extend 3) ((_ extract 1 0) x))))",
               "(define-fun ob () (_ BitVec 4) (bvor (bvshl ((_ zero_extend 3) ((_ extract 4 4) x)) #b0011) ((_ zero_extend 1) ((_ extract 7 5) x))))"]
        queries=[("equivalence_a","(distinct (a x) oa)","unsat"),("equivalence_b","(distinct (b x) ob)","unsat")]
        for name,positions in (("a",[0,1,5,6,7]),("b",[4,5,6,7])):
            for i in range(8):
                queries.append((f"{name}_bit_{i}",f"(distinct ({name} x) ({name} (bvxor x (_ bv{1<<i} 8))))",
                                "sat" if i in positions else "unsat"))
        queries.extend([("mutant_a_reorder","(distinct (a x) (concat ((_ extract 1 0) x) ((_ extract 7 5) x)))","sat"),
                        ("mutant_b_reorder","(distinct (b x) (concat ((_ extract 7 5) x) ((_ extract 4 4) x)))","sat")])
        for name,expr,expected in queries:
            lines.extend(["(push 1)",f"(assert {expr})","(check-sat)","(pop 1)"])
        smt=run/"vector-concat.smt2"
        smt.write_text("\n".join(lines+["(exit)"])+"\n",encoding="utf-8")
        p=subprocess.run(["z3","-smt2",str(smt)],capture_output=True,text=True,timeout=120)
        (run/"stdout.log").write_text(p.stdout,encoding="utf-8")
        (run/"stderr.log").write_text(p.stderr,encoding="utf-8")
        actual=p.stdout.splitlines()
        report["queries"]=[{"name":n,"expected":e,"actual":actual[i] if i<len(actual) else None} for i,(n,_,e) in enumerate(queries)]
        assert p.returncode==0 and actual==[e for _,_,e in queries],(p.stdout,p.stderr)
        report.update(status="passed",query_count=20,unsat=9,sat=11)
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

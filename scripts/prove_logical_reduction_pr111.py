"""Binary logical fixture models vs independently enumerated truth tables."""
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
    report={"status":"incomplete","scope":"binary_read_once_logic_fixture_models",
            "rtl_equivalence":"not_performed","temporal_proof":"not_performed"}
    def save(): path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    try:
        report["z3_version"]=subprocess.check_output(["z3","--version"],text=True,timeout=10).strip()
        lines=["(set-logic QF_BV)","(set-option :timeout 10000)","(declare-fun x () (_ BitVec 8))"]
        exprs=["(and a (not b))","(and (not a) (not b) (not c))","(and (not a) (not b) (not c) d)",
               "(and v d)","(or v b)","(not v)"]
        binding=" ".join(f"({name} (= ((_ extract {i} {i}) w) #b1))" for i,name in enumerate("abcd"))
        binding+=" (v (distinct ((_ extract 7 4) w) #b0000))"
        supports=[{0,1},{0,1,2},{0,1,2,3},{3,4,5,6,7},{1,4,5,6,7},{4,5,6,7}]
        def oracle(x):
            return [x&3==1,x&7==0,x&15==8,x>=16 and bool(x&8),x>=16 or bool(x&2),x<16]
        queries=[]
        for i,expr in enumerate(exprs):
            lines.append(f"(define-fun f{i} ((w (_ BitVec 8))) Bool (let ({binding}) {expr}))")
            table=" ".join(f"(= x (_ bv{x} 8))" for x in range(256) if oracle(x)[i])
            queries.append((f"truth_table_{i}",f"(distinct (f{i} x) (or {table}))","unsat"))
            for j in range(8):
                queries.append((f"sensitivity_{i}_{j}",f"(distinct (f{i} x) (f{i} (bvxor x (_ bv{1<<j} 8))))",
                                "sat" if j in supports[i] else "unsat"))
            mask=255^(1<<min(supports[i]))
            queries.append((f"mutant_drop_bit_{i}",f"(distinct (f{i} x) (f{i} (bvand x (_ bv{mask} 8))))","sat"))
        for name,expr,expected in queries:
            lines.extend(["(push 1)",f"(assert {expr})","(check-sat)","(pop 1)"])
        smt=run/"logical-reduction.smt2"
        smt.write_text("\n".join(lines+["(exit)"])+"\n",encoding="utf-8")
        p=subprocess.run(["z3","-smt2",str(smt)],capture_output=True,text=True,timeout=120)
        (run/"stdout.log").write_text(p.stdout,encoding="utf-8")
        (run/"stderr.log").write_text(p.stderr,encoding="utf-8")
        actual=p.stdout.splitlines()
        report["queries"]=[{"name":n,"expected":e,"actual":actual[i] if i<len(actual) else None} for i,(n,_,e) in enumerate(queries)]
        assert p.returncode==0 and actual==[e for _,_,e in queries],(p.stdout,p.stderr)
        report.update(status="passed",query_count=len(queries),unsat=actual.count("unsat"),sat=actual.count("sat"))
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

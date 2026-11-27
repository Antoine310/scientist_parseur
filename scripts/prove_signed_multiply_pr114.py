"""Signed full product: binary encoding checks, prefix bounds, concrete witnesses."""
import argparse,json,subprocess,tempfile
from pathlib import Path


def execute(out):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out));path=run/"summary.json"
    report={"status":"incomplete","scope":"binary_signed_full_product_models",
            "rtl_equivalence":"not_performed","temporal_proof":"not_performed"}
    def save(): path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    try:
        report["z3_version"]=subprocess.check_output(["z3","--version"],text=True,timeout=10).strip()
        lines=["(set-logic QF_BV)","(set-option :timeout 10000)"]
        queries=[]
        for n in (4,9,17):
            a,b,fn=f"a{n}",f"b{n}",f"p{n}"
            for name in (a,b): lines.append(f"(declare-fun {name} () (_ BitVec {n}))")
            lines.append(f"(define-fun {fn} ((x (_ BitVec {n})) (y (_ BitVec {n}))) (_ BitVec {2*n}) (bvmul ((_ sign_extend {n}) x) ((_ sign_extend {n}) y)))")
            native=f"({fn} {a} {b})"
            def ext(x): return f"(concat ((_ repeat {n}) ((_ extract {n-1} {n-1}) {x})) {x})"
            oracle=f"(bvmul {ext(a)} {ext(b)})"
            queries.append((f"encoding_equivalence_{n}",f"(distinct {native} {oracle})","unsat"))
            for side in (0,1):
                for j in range(1,n):
                    args=[a,b];args[side]=f"(bvxor {args[side]} (_ bv{1<<j} {n}))"
                    changed=f"({fn} {' '.join(args)})"
                    queries.append((f"low_prefix_noninterference_{n}_{side}_{j}",
                                    f"(distinct ((_ extract {j-1} 0) {native}) ((_ extract {j-1} 0) {changed}))","unsat"))
                for j in range(n):
                    # Toggle one original bit from zero; multiply by -1
                    # except for the negative-weight sign bit (multiply by +1).
                    other=(1<<n)-1 if j<n-1 else 1
                    args=[f"(_ bv{other} {n})"]*2;args[side]=f"(_ bv{1<<j} {n})"
                    base=args.copy();base[side]=f"(_ bv0 {n})"
                    changed=f"({fn} {' '.join(args)})";initial=f"({fn} {' '.join(base)})"
                    expected=(1<<(2*n))-(1<<j)
                    queries.append((f"simultaneous_upper_lane_witness_{n}_{side}_{j}",
                                    f"(= (bvxor {initial} {changed}) (_ bv{expected} {2*n}))","sat"))
            zero=f"(bvmul ((_ zero_extend {n}) {a}) ((_ zero_extend {n}) {b}))"
            truncated=f"((_ sign_extend {n}) (bvmul {a} {b}))"
            # Concrete witnesses avoid unconstrained nonlinear search for mutants.
            queries.extend([(f"mutant_unsigned_{n}",f"(and (= {a} (_ bv{1<<(n-1)} {n})) (= {b} (_ bv1 {n})) (distinct {native} {zero}))","sat"),
                            (f"mutant_truncated_{n}",f"(and (= {a} (_ bv{1<<(n-1)} {n})) (= {b} (_ bv{1<<(n-1)} {n})) (distinct {native} {truncated}))","sat")])
        assert len(queries)==123
        for name,expr,expected in queries:
            lines.extend(["(push 1)",f"(assert {expr})","(check-sat)","(pop 1)"])
        smt=run/"signed-products.smt2";smt.write_text("\n".join(lines+["(exit)"])+"\n",encoding="utf-8")
        p=subprocess.run(["z3","-smt2",str(smt)],capture_output=True,text=True,timeout=120)
        (run/"stdout.log").write_text(p.stdout,encoding="utf-8");(run/"stderr.log").write_text(p.stderr,encoding="utf-8")
        actual=p.stdout.splitlines()
        report["queries"]=[{"name":name,"expected":expected,"actual":actual[i] if i<len(actual) else None}
                           for i,(name,_,expected) in enumerate(queries)]
        assert p.returncode==0 and actual==[q[2] for q in queries],(p.stdout,p.stderr)
        assert actual.count("unsat")==57 and actual.count("sat")==66
        report.update(status="passed",query_count=len(queries),unsat=57,sat=66)
    except Exception as exc:
        report.update(status="failed",error=f"{type(exc).__name__}: {exc}"[:1000]);raise
    finally:
        save();print(path.read_text(),flush=True);print(f"Summary: {path}",flush=True)
    return path


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--out",type=Path,required=True)
    execute(p.parse_args().out)

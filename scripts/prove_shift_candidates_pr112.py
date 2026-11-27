"""Independent shift bit-vector vs per-amount lane models, not RTL proof."""
import argparse,json,subprocess,tempfile
from pathlib import Path


def execute(out):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out));path=run/"summary.json"
    report={"status":"incomplete","scope":"binary_shift_models","rtl_equivalence":"not_performed","temporal_proof":"not_performed"}
    def save(): path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    try:
        report["z3_version"]=subprocess.check_output(["z3","--version"],text=True,timeout=10).strip()
        lines=["(set-logic QF_BV)","(set-option :timeout 10000)"]
        queries=[]
        for label,w,n,m,left,fixed,mask in (("fixed",8,8,0,True,2,None),("left",8,8,3,True,None,None),
               ("right",8,4,3,False,None,None),("mask",32,32,5,True,None,0xfffffffe),
               ("real_right",64,32,5,False,None,None)):
            x="x_"+label;k="k_"+label
            if mask is None: lines.append(f"(declare-fun {x} () (_ BitVec {w}))")
            else: x=f"(_ bv{mask} {w})"
            if fixed is None:
                lines.append(f"(declare-fun {k} () (_ BitVec {m}))")
                amount=f"((_ zero_extend {w-m}) {k})"
            else: amount=f"(_ bv{fixed} {w})"
            def low(e): return e if n==w else f"((_ extract {n-1} 0) {e})"
            native=low(f"({'bvshl' if left else 'bvlshr'} {x} {amount})")
            def lanes(a):
                bits=[]
                for i in reversed(range(n)):
                    j=i-a if left else i+a
                    bits.append("#b0" if not 0<=j<w else f"((_ extract {j} {j}) {x})")
                expr=bits[0]
                for bit in bits[1:]: expr=f"(concat {expr} {bit})"
                return expr
            if fixed is not None: oracle=lanes(fixed)
            else:
                oracle=lanes((1<<m)-1)
                for a in reversed(range((1<<m)-1)):
                    oracle=f"(ite (= {k} (_ bv{a} {m})) {lanes(a)} {oracle})"
            queries.append((label+"_equivalence",f"(distinct {native} {oracle})","unsat"))
            mutant=low(f"({'bvlshr' if left else 'bvshl'} {x} {amount})")
            queries.append((label+"_direction_mutant",f"(distinct {native} {mutant})","sat"))
        for name,expr,expected in queries:
            lines.extend(["(push 1)",f"(assert {expr})","(check-sat)","(pop 1)"])
        smt=run/"shift-models.smt2";smt.write_text("\n".join(lines+["(exit)"])+"\n",encoding="utf-8")
        p=subprocess.run(["z3","-smt2",str(smt)],capture_output=True,text=True,timeout=120)
        (run/"stdout.log").write_text(p.stdout,encoding="utf-8");(run/"stderr.log").write_text(p.stderr,encoding="utf-8")
        actual=p.stdout.splitlines()
        report["queries"]=[{"name":name,"expected":expected,"actual":actual[i] if i<len(actual) else None}
                           for i,(name,_,expected) in enumerate(queries)]
        assert p.returncode==0 and actual==[q[2] for q in queries],(p.stdout,p.stderr)
        report.update(status="passed",query_count=len(queries),unsat=actual.count("unsat"),sat=actual.count("sat"))
    except Exception as exc:
        report.update(status="failed",error=f"{type(exc).__name__}: {exc}"[:1000]);raise
    finally:
        save();print(path.read_text(),flush=True);print(f"Summary: {path}",flush=True)
    return path


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--out",type=Path,required=True)
    execute(p.parse_args().out)

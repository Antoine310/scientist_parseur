"""Independent binary arithmetic shift model vs logical shift + gated fill."""
import argparse
import json
import subprocess
import tempfile
from pathlib import Path


def execute(out):
    out=out.resolve()
    out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out))
    path=run/"summary.json"
    report={"status":"incomplete","scope":"binary_controlled_signed_shift_models",
            "rtl_equivalence":"not_performed","temporal_proof":"not_performed"}
    def save():
        path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    try:
        report["z3_version"]=subprocess.check_output(["z3","--version"],text=True,timeout=10).strip()
        lines=["(set-logic QF_BV)","(set-option :timeout 10000)"]
        queries=[]
        for n,m in ((4,2),(8,3),(16,4)):
            d,k,c=f"d{n}",f"k{n}",f"c{n}"
            fn=f"f{n}"
            args=f"((d (_ BitVec {n})) (k (_ BitVec {m})) (c (_ BitVec 1)))"
            for name,width in ((d,n),(k,m),(c,1)):
                lines.append(f"(declare-fun {name} () (_ BitVec {width}))")
            sign=f"(bvand ((_ extract {n-1} {n-1}) d) c)"
            extended=f"(concat {sign} d)"
            wide_k=f"((_ zero_extend {n+1-m}) k)"
            shift=f"((_ extract {n-1} 0) (bvashr {extended} {wide_k}))"
            lines.append(f"(define-fun {fn} {args} (_ BitVec {n}) {shift})")
            amount=f"((_ zero_extend {n-m}) {k})"
            ones=f"(_ bv{2**n-1} {n})"
            fill=f"(bvxor {ones} (bvlshr {ones} {amount}))"
            oracle=f"(bvor (bvlshr {d} {amount}) (ite (and (= {c} #b1) (= ((_ extract {n-1} {n-1}) {d}) #b1)) {fill} (_ bv0 {n})))"
            native=f"({fn} {d} {k} {c})"
            queries.append((f"equivalence_{n}",f"(distinct {native} {oracle})","unsat"))
            logical=f"((_ extract {n-1} 0) (bvlshr (concat (bvand ((_ extract {n-1} {n-1}) {d}) {c}) {d}) ((_ zero_extend {n+1-m}) {k})))"
            queries.extend([(f"mutant_zero_fill_{n}",f"(distinct {native} {logical})","sat"),
                            (f"mutant_ignore_mode_{n}",f"(distinct {native} ({fn} {d} {k} #b0))","sat")])
            for i in range(n):
                for role,width in (("data",n),("amount",m),("mode",1)):
                    for j in range(width):
                        src=[d,k,c];pos={"data":0,"amount":1,"mode":2}[role]
                        src[pos]=f"(bvxor {src[pos]} (_ bv{1<<j} {width}))"
                        mutated=f"({fn} {' '.join(src)})"
                        expected="sat" if (role=="data" and j>=i) or role=="amount" or (role=="mode" and i>0) else "unsat"
                        queries.append((f"sensitivity_{n}_{i}_{role}_{j}",
                                        f"(distinct ((_ extract {i} {i}) {native}) ((_ extract {i} {i}) {mutated}))",expected))
        assert len(queries)==469
        for name,expr,expected in queries:
            lines.extend(["(push 1)",f"(assert {expr})","(check-sat)","(pop 1)"])
        smt=run/"signed-shifts.smt2"
        smt.write_text("\n".join(lines+["(exit)"])+"\n",encoding="utf-8")
        p=subprocess.run(["z3","-smt2",str(smt)],capture_output=True,text=True,timeout=120)
        (run/"stdout.log").write_text(p.stdout,encoding="utf-8")
        (run/"stderr.log").write_text(p.stderr,encoding="utf-8")
        actual=p.stdout.splitlines()
        report["queries"]=[{"name":name,"expected":expected,"actual":actual[i] if i<len(actual) else None}
                           for i,(name,_,expected) in enumerate(queries)]
        assert p.returncode==0 and actual==[q[2] for q in queries],(p.stdout,p.stderr)
        assert actual.count("unsat")==160 and actual.count("sat")==309
        report.update(status="passed",query_count=len(queries),unsat=160,sat=309)
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

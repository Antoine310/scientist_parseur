"""Binary range and arithmetic bound models, not whole RTL equivalence."""
import argparse,json,subprocess,tempfile
from pathlib import Path
from rtlprep.arithmetic_range_candidates import range_model


def expr(m,word="a"):
    return f"((_ extract {m['msb']} {m['lsb']}) {word})"


def execute(out):
    out=out.resolve(); out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out)); path=run/"summary.json"
    report={"status":"incomplete","scope":"binary_arithmetic_range_models",
            "rtl_equivalence":"not_performed","temporal_proof":"not_performed","global_influence":"not_proven"}
    def save(): path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    try:
        report["z3_version"]=subprocess.check_output(["z3","--version"],text=True,timeout=10).strip()
        queries=[]
        ranges=[(4,0,"(bvsub (_ bv5 32) (_ bv1 32))","(_ bv0 32)"),
                (2,0,"(bvsub (_ bv3 32) (_ bv1 32))","(_ bv0 32)"),
                (7,5,"(bvsub (bvadd (_ bv3 32) (_ bv5 32)) (_ bv1 32))","(_ bv5 32)")]
        for hi,lo,upper,lower in ranges:
            m=range_model(hi,lo); n=m["width"]; x=expr(m)
            tag=f"range{hi}_{lo}"
            queries.append((tag+"_bounds",f"(or (distinct {upper} (_ bv{hi} 32)) (distinct {lower} (_ bv{lo} 32)))","unsat"))
            spec=f"((_ extract {n-1} 0) (bvand (bvlshr a (_ bv{lo} 32)) (_ bv{(1<<n)-1} 32)))"
            queries.append((tag+"_equivalence",f"(distinct {x} {spec})","unsat"))
            for bit in range(32):
                y=expr(m,f"(bvxor a (_ bv{1<<bit} 32))")
                queries.append((tag+f"_bit{bit}",f"(distinct {x} {y})","sat" if lo<=bit<=hi else "unsat"))
        x=expr(range_model(7,5))
        queries.extend([
            ("mutant_offset",f"(distinct {x} {expr(range_model(6,4))})","sat"),
            ("mutant_low_range",f"(distinct {x} {expr(range_model(2,0))})","sat"),
            ("mutant_order",f"(distinct {x} (concat ((_ extract 5 5) a) (concat ((_ extract 6 6) a) ((_ extract 7 7) a))))","sat"),
            ("mutant_operator","(distinct (bvsub (bvadd (_ bv3 32) (_ bv5 32)) (_ bv1 32)) (bvadd (bvadd (_ bv3 32) (_ bv5 32)) (_ bv1 32)))","sat")])
        lines=["(set-logic QF_BV)","(set-option :timeout 10000)","(declare-fun a () (_ BitVec 32))"]
        for _,q,_ in queries: lines.extend(["(push 1)",f"(assert {q})","(check-sat)","(pop 1)"])
        smt=run/"models.smt2"; smt.write_text("\n".join(lines+["(exit)"])+"\n")
        p=subprocess.run(["z3","-smt2",str(smt)],capture_output=True,text=True,timeout=120)
        (run/"stdout.log").write_text(p.stdout); (run/"stderr.log").write_text(p.stderr)
        actual=p.stdout.splitlines()
        report["queries"]=[{"name":q[0],"expected":q[2],"actual":actual[i] if i<len(actual) else None} for i,q in enumerate(queries)]
        assert p.returncode==0 and actual==[q[2] for q in queries],(p.stdout[-1000:],p.stderr)
        report.update(status="passed",query_count=len(queries),unsat=actual.count("unsat"),sat=actual.count("sat"),
                      bound_queries=3,equivalence_queries=3,selected_sensitivity_queries=11,
                      unselected_sensitivity_queries=85,mutants=4)
        assert (len(queries),report["unsat"],report["sat"])==(106,91,15)
    except Exception as exc:
        report.update(status="failed",error=f"{type(exc).__name__}: {exc}"[:2000]); raise
    finally:
        save(); print(json.dumps({k:v for k,v in report.items() if k!="queries"},indent=2),flush=True)
        print(f"Summary: {path}",flush=True)
    return path


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--out",type=Path,required=True)
    execute(p.parse_args().out)

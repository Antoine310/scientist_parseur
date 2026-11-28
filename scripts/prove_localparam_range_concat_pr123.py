"""Binary positional models, not full RTL equivalence or guard proofs."""
import argparse,json,subprocess,tempfile
from pathlib import Path
from rtlprep.localparam_range_concat_candidates import range_model


def expr(m,word="a",flag="f"):
    return f"(concat {flag} ((_ extract {m['msb']} {m['lsb']}) {word}))"


def execute(out):
    out=out.resolve(); out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out)); path=run/"summary.json"
    report={"status":"incomplete","scope":"binary_localparam_range_concat_models",
            "rtl_equivalence":"not_performed","temporal_proof":"not_performed","global_influence":"not_proven"}
    def save(): path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    try:
        report["z3_version"]=subprocess.check_output(["z3","--version"],text=True,timeout=10).strip()
        queries=[]
        for lo in (7,15,20,27):
            m=range_model(lo+4,lo); x=expr(m)
            spec=f"(bvor (bvshl ((_ zero_extend 5) f) (_ bv5 6)) ((_ extract 5 0) (bvand (bvlshr a (_ bv{lo} 32)) (_ bv31 32))))"
            queries.append((f"lo{lo}_equivalence",f"(distinct {x} {spec})","unsat"))
            for b in range(32):
                y=expr(m,f"(bvxor a (_ bv{1<<b} 32))")
                queries.append((f"lo{lo}_source{b}",f"(distinct {x} {y})","sat" if lo<=b<=lo+4 else "unsat"))
            queries.append((f"lo{lo}_flag",f"(distinct {x} {expr(m,flag='(bvnot f)')})","sat"))
        x=expr(range_model(19,15))
        queries.extend([
            ("mutant_range",f"(distinct {x} {expr(range_model(20,16))})","sat"),
            ("mutant_order",f"(distinct {x} (concat ((_ extract 19 15) a) f))","sat"),
            ("mutant_flag",f"(distinct {x} {expr(range_model(19,15),flag='#b0')})","sat")])
        lines=["(set-logic QF_BV)","(set-option :timeout 10000)",
               "(declare-fun a () (_ BitVec 32))","(declare-fun f () (_ BitVec 1))"]
        for _,q,_ in queries: lines.extend(["(push 1)",f"(assert {q})","(check-sat)","(pop 1)"])
        smt=run/"models.smt2"; smt.write_text("\n".join(lines+["(exit)"])+"\n")
        p=subprocess.run(["z3","-smt2",str(smt)],capture_output=True,text=True,timeout=120)
        (run/"stdout.log").write_text(p.stdout); (run/"stderr.log").write_text(p.stderr)
        actual=p.stdout.splitlines()
        report["queries"]=[{"name":q[0],"expected":q[2],"actual":actual[i] if i<len(actual) else None} for i,q in enumerate(queries)]
        assert p.returncode==0 and actual==[q[2] for q in queries],(p.stdout[-1000:],p.stderr)
        report.update(status="passed",query_count=len(queries),unsat=actual.count("unsat"),sat=actual.count("sat"),
                      selected_sensitivity_queries=24,unselected_sensitivity_queries=108,mutants=3)
        assert (len(queries),report["unsat"],report["sat"])==(139,112,27)
    except Exception as exc:
        report.update(status="failed",error=f"{type(exc).__name__}: {exc}"[:2000]); raise
    finally:
        save(); print(json.dumps({k:v for k,v in report.items() if k!="queries"},indent=2),flush=True)
        print(f"Summary: {path}",flush=True)
    return path


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--out",type=Path,required=True)
    execute(p.parse_args().out)

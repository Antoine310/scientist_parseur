"""Configuration-specific binary models, not RTL equivalence."""
import argparse,json,subprocess,tempfile
from pathlib import Path
from rtlprep.parameter_mux_candidates import mux_model


def expr(m,word="(concat b a)"):
    lane=m["lane"]; lo=32*lane; hi=lo+31
    return f"(ite (= (_ bv{m['parameter_value']} 32) (_ bv0 32)) (_ bv0 32) ((_ extract {hi} {lo}) {word}))"


def execute(out):
    out=out.resolve(); out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out)); path=run/"summary.json"
    report={"status":"incomplete","scope":"binary_parameter_mux_models","rtl_equivalence":"not_performed",
            "temporal_proof":"not_performed","global_influence":"not_proven"}
    def save(): path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    try:
        report["z3_version"]=subprocess.check_output(["z3","--version"],text=True,timeout=10).strip()
        queries=[]
        for v in (0,1):
            for lane in (0,1):
                m=mux_model(v,lane); x=expr(m)
                spec=("a" if lane==0 else "b") if v else "(_ bv0 32)"
                queries.append((f"cfg{v}_lane{lane}_composition",f"(distinct {x} {spec})","unsat"))
                for bit in range(32):
                    changed=f"(bvxor (concat b a) (_ bv{1<<(32*lane+bit)} 64))"
                    queries.append((f"cfg{v}_lane{lane}_bit{bit}",f"(distinct {x} {expr(m,changed)})","sat" if v else "unsat"))
        x=expr(mux_model(1,0))
        queries.extend([
            ("mutant_config",f"(distinct {x} {expr(mux_model(0,0))})","sat"),
            ("mutant_lane",f"(distinct {x} {expr(mux_model(1,1))})","sat"),
            ("mutant_zero_literal",f"(distinct {expr(mux_model(0,0))} (_ bv1 32))","sat")])
        lines=["(set-logic QF_BV)","(set-option :timeout 10000)",
               "(declare-fun a () (_ BitVec 32))","(declare-fun b () (_ BitVec 32))"]
        for _,q,_ in queries: lines.extend(["(push 1)",f"(assert {q})","(check-sat)","(pop 1)"])
        smt=run/"models.smt2"; smt.write_text("\n".join(lines+["(exit)"])+"\n")
        p=subprocess.run(["z3","-smt2",str(smt)],capture_output=True,text=True,timeout=120)
        (run/"stdout.log").write_text(p.stdout); (run/"stderr.log").write_text(p.stderr)
        actual=p.stdout.splitlines()
        report["queries"]=[{"name":q[0],"expected":q[2],"actual":actual[i] if i<len(actual) else None} for i,q in enumerate(queries)]
        assert p.returncode==0 and actual==[q[2] for q in queries],(p.stdout,p.stderr)
        report.update(status="passed",query_count=len(queries),unsat=actual.count("unsat"),sat=actual.count("sat"),
                      selected_sensitivity_queries=64,inactive_sensitivity_queries=64,mutants=3)
        assert (len(queries),report["unsat"],report["sat"])==(135,68,67)
    except Exception as exc:
        report.update(status="failed",error=f"{type(exc).__name__}: {exc}"[:2000]); raise
    finally:
        save(); print(json.dumps({k:v for k,v in report.items() if k!="queries"},indent=2),flush=True)
        print(f"Summary: {path}",flush=True)
    return path


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--out",type=Path,required=True)
    execute(p.parse_args().out)

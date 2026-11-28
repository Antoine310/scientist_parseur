"""Binary local configuration models, not RTL or temporal equivalence."""
import argparse,json,subprocess,tempfile
from pathlib import Path
from rtlprep.parameter_concat_mux_candidates import concat_mux_model


def expr(m,frm="r",flags="f"):
    parts=[f"(_ bv0 {m['zero_prefix_width']})"]+[frm if w==3 else flags for w in m["operand_widths_msb_first"]]
    c=parts[0]
    for p in parts[1:]: c=f"(concat {c} {p})"
    return f"(ite (= (_ bv{m['parameter_value']} 32) (_ bv1 32)) {c} (_ bv0 32))"


def execute(out):
    out=out.resolve(); out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out)); path=run/"summary.json"
    report={"status":"incomplete","scope":"binary_parameter_concat_mux_models",
            "rtl_equivalence":"not_performed","temporal_proof":"not_performed","global_influence":"not_proven"}
    def save(): path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    try:
        report["z3_version"]=subprocess.check_output(["z3","--version"],text=True,timeout=10).strip()
        queries=[]
        specs=["((_ zero_extend 27) f)","((_ zero_extend 29) r)",
               "(bvadd (bvshl ((_ zero_extend 29) r) (_ bv5 32)) ((_ zero_extend 27) f))"]
        for v in (0,1):
            for j,widths in enumerate(((5,),(3,),(3,5))):
                m=concat_mux_model(v,widths); x=expr(m)
                spec=specs[j] if v else "(_ bv0 32)"
                queries.append((f"cfg{v}_site{j}_composition",f"(distinct {x} {spec})","unsat"))
                for w,var in ((3,"r"),(5,"f")):
                    for bit in range(w):
                        changed=f"(bvxor {var} (_ bv{1<<bit} {w}))"
                        y=expr(m,frm=changed if w==3 else "r",flags=changed if w==5 else "f")
                        queries.append((f"cfg{v}_site{j}_{var}{bit}",f"(distinct {x} {y})",
                                        "sat" if v and w in widths else "unsat"))
        x=expr(concat_mux_model(1,(3,5)))
        queries.extend([
            ("mutant_config",f"(distinct {x} {expr(concat_mux_model(0,(3,5)))})","sat"),
            ("mutant_order",f"(distinct {x} (concat (_ bv0 24) (concat f r)))","sat"),
            ("mutant_offset",f"(distinct {x} (bvadd (bvshl ((_ zero_extend 29) r) (_ bv4 32)) ((_ zero_extend 27) f)))","sat"),
            ("mutant_zero",f"(distinct {expr(concat_mux_model(0,(3,5)))} (_ bv1 32))","sat")])
        lines=["(set-logic QF_BV)","(set-option :timeout 10000)",
               "(declare-fun r () (_ BitVec 3))","(declare-fun f () (_ BitVec 5))"]
        for _,q,_ in queries: lines.extend(["(push 1)",f"(assert {q})","(check-sat)","(pop 1)"])
        smt=run/"models.smt2"; smt.write_text("\n".join(lines+["(exit)"])+"\n")
        p=subprocess.run(["z3","-smt2",str(smt)],capture_output=True,text=True,timeout=120)
        (run/"stdout.log").write_text(p.stdout); (run/"stderr.log").write_text(p.stderr)
        actual=p.stdout.splitlines()
        report["queries"]=[{"name":q[0],"expected":q[2],"actual":actual[i] if i<len(actual) else None} for i,q in enumerate(queries)]
        assert p.returncode==0 and actual==[q[2] for q in queries],(p.stdout,p.stderr)
        report.update(status="passed",query_count=len(queries),unsat=actual.count("unsat"),sat=actual.count("sat"),
                      selected_sensitivity_queries=16,inactive_or_unused_sensitivity_queries=32,mutants=4)
        assert (len(queries),report["unsat"],report["sat"])==(58,38,20)
    except Exception as exc:
        report.update(status="failed",error=f"{type(exc).__name__}: {exc}"[:2000]); raise
    finally:
        save(); print(json.dumps({k:v for k,v in report.items() if k!="queries"},indent=2),flush=True)
        print(f"Summary: {path}",flush=True)
    return path


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--out",type=Path,required=True)
    execute(p.parse_args().out)

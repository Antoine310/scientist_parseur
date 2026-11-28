"""Binary lane coordinate model checks, not whole RTL or branch proofs."""
import argparse,json,subprocess,tempfile
from pathlib import Path
from rtlprep.packed_lane_concat_candidates import lane_model


def expr(m,bit="d"):
    # Embed a single lane in an otherwise zero vector; not a hold claim.
    p=2*m["outer_index"]
    a=f"(bvshl ((_ zero_extend 7) {bit}) (_ bv{p+m['dynamic_inner_bit']} 8))"
    b=f"(_ bv{m['literal_value']<<(p+m['literal_inner_bit'])} 8)"
    return f"(bvor {a} {b})"


def execute(out):
    out=out.resolve(); out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out)); path=run/"summary.json"
    report={"status":"incomplete","scope":"binary_packed_lane_coordinate_models",
            "rtl_equivalence":"not_performed","temporal_proof":"not_performed","global_influence":"not_proven"}
    def save(): path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    try:
        report["z3_version"]=subprocess.check_output(["z3","--version"],text=True,timeout=10).strip()
        queries=[]
        for k in range(4):
            for v in (0,1):
                m=lane_model(k,v); x=expr(m)
                spec=f"(bvshl ((_ zero_extend 6) (concat d #b{v})) (_ bv{2*k} 8))"
                queries.append((f"lane_{k}_literal_{v}",f"(distinct {x} {spec})","unsat"))
                queries.append((f"lane_{k}_literal_{v}_sensitivity",f"(distinct {x} {expr(m,bit='(bvnot d)')})","sat"))
        m=lane_model(3,1); x=expr(m)
        queries.extend([
            ("mutant_swap_order",f"(distinct {x} {expr({**m,'dynamic_inner_bit':0,'literal_inner_bit':1})})","sat"),
            ("mutant_wrong_lane",f"(distinct {x} {expr(lane_model(2,1))})","sat"),
            ("mutant_wrong_literal",f"(distinct {x} {expr(lane_model(3,0))})","sat")])
        lines=["(set-logic QF_BV)","(set-option :timeout 10000)","(declare-fun d () (_ BitVec 1))"]
        for _,q,_ in queries: lines.extend(["(push 1)",f"(assert {q})","(check-sat)","(pop 1)"])
        smt=run/"models.smt2"; smt.write_text("\n".join(lines+["(exit)"])+"\n")
        p=subprocess.run(["z3","-smt2",str(smt)],capture_output=True,text=True,timeout=120)
        (run/"stdout.log").write_text(p.stdout); (run/"stderr.log").write_text(p.stderr)
        actual=p.stdout.splitlines()
        report["queries"]=[{"name":q[0],"expected":q[2],"actual":actual[i] if i<len(actual) else None} for i,q in enumerate(queries)]
        assert p.returncode==0 and actual==[q[2] for q in queries],(p.stdout,p.stderr)
        report.update(status="passed",query_count=len(queries),unsat=actual.count("unsat"),sat=actual.count("sat"),
                      local_sensitivity_queries=8,mutants=3)
        assert (len(queries),report["unsat"],report["sat"])==(19,8,11)
    except Exception as exc:
        report.update(status="failed",error=f"{type(exc).__name__}: {exc}"[:2000]); raise
    finally:
        save(); print(json.dumps({k:v for k,v in report.items() if k!="queries"},indent=2),flush=True)
        print(f"Summary: {path}",flush=True)
    return path


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--out",type=Path,required=True)
    execute(p.parse_args().out)

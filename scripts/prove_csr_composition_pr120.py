"""CSR binary composition models and local bit sensitivity (not RTL proof)."""
import argparse,json,subprocess,tempfile
from pathlib import Path
from rtlprep.csr_composition_candidates import csr_model


def expr(m,a="a",e="e",l="l",w="(_ bv64 32)"):
    compare=f'(= ((_ zero_extend {m["zero_fill_count"]}) {a}) (bvadd (_ bv{m["enum_base"]} 32) (_ bv{m["index"]} 32)))'
    clauses=[compare,f"(= {e} #b1)"]
    if m["upper"]: clauses += [f"(= {l} #b0)",f"(= {w} (_ bv64 32))"]
    return "(ite (and "+" ".join(clauses)+") #b1 #b0)"


def execute(out):
    out=out.resolve(); out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out)); path=run/"summary.json"
    report={"status":"incomplete","scope":"binary_csr_composition_models","rtl_equivalence":"not_performed",
            "temporal_proof":"not_performed","global_influence":"not_proven"}
    def save(): path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    try:
        report["z3_version"]=subprocess.check_output(["z3","--version"],text=True,timeout=10).strip()
        queries=[]
        for upper,base in [(False,2816),(True,2944)]:
            for k in range(32):
                m=csr_model(base,k,upper); x=expr(m)
                name=("upper" if upper else "lower")+f"_{k}"
                spec=f'(bvand e (ite (= a (_ bv{base+k} 12)) #b1 #b0))'
                if upper: spec=f"(bvand {spec} (bvnot l))"
                queries.append((name+"_composition",f"(distinct {x} {spec})","unsat"))
                for b in range(12):
                    queries.append((name+f"_address_{b}",f"(distinct {x} {expr(m,a=f'(bvxor a (_ bv{1<<b} 12))')})","sat"))
                queries.append((name+"_enable",f"(distinct {x} {expr(m,e='(bvnot e)')})","sat"))
                if upper: queries.append((name+"_inhibit",f"(distinct {x} {expr(m,l='(bvnot l)')})","sat"))
        m=csr_model(2944,7,True); x=expr(m)
        queries += [
            ("mutant_wrong_base",f"(distinct {x} {expr(csr_model(2816,7,True))})","sat"),
            ("mutant_wrong_index",f"(distinct {x} {expr(csr_model(2944,8,True))})","sat"),
            ("mutant_ignore_inhibit",f"(distinct {x} {expr(m,l='#b0')})","sat"),
            ("mutant_width32",f"(distinct {x} {expr(m,w='(_ bv32 32)')})","sat")]
        lines=["(set-logic QF_BV)","(set-option :timeout 10000)","(declare-fun a () (_ BitVec 12))",
               "(declare-fun e () (_ BitVec 1))","(declare-fun l () (_ BitVec 1))"]
        for _,q,_ in queries: lines.extend(["(push 1)",f"(assert {q})","(check-sat)","(pop 1)"])
        smt=run/"models.smt2"; smt.write_text("\n".join(lines+["(exit)"])+"\n")
        p=subprocess.run(["z3","-smt2",str(smt)],capture_output=True,text=True,timeout=120)
        (run/"stdout.log").write_text(p.stdout); (run/"stderr.log").write_text(p.stderr)
        actual=p.stdout.splitlines()
        report["queries"]=[{"name":q[0],"expected":q[2],"actual":actual[i] if i<len(actual) else None} for i,q in enumerate(queries)]
        assert p.returncode==0 and actual==[q[2] for q in queries],(p.stdout[-1000:],p.stderr)
        report.update(status="passed",query_count=len(queries),unsat=actual.count("unsat"),sat=actual.count("sat"),
                      local_sensitivity_queries=864,mutants=4)
        assert (len(queries),report["unsat"],report["sat"])==(932,64,868)
    except Exception as exc:
        report.update(status="failed",error=f"{type(exc).__name__}: {exc}"[:2000]); raise
    finally:
        save()
        print(json.dumps({k:v for k,v in report.items() if k!="queries"},indent=2),flush=True)
        print(f"Summary: {path}",flush=True)
    return path


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--out",type=Path,required=True)
    execute(p.parse_args().out)

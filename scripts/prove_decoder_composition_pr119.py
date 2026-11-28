"""Binary composition model equivalence and local bit-sensitivity witnesses."""
import argparse,json,subprocess,tempfile
from pathlib import Path
from rtlprep.decoder_composition_candidates import decoder_model


def expression(m,addr="a",enable="e"):
    return (f'(ite (= ((_ zero_extend {m["zero_fill_count"]}) {addr}) '
            f'(_ bv{m["index"]} {m["comparison_width"]})) {enable} #b{m["false_value"]})')


def execute(out):
    out=out.resolve(); out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out)); path=run/"summary.json"
    report={"status":"incomplete","scope":"binary_decoder_composition_models",
            "rtl_equivalence":"not_performed","temporal_proof":"not_performed",
            "global_influence":"not_proven"}
    def save(): path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    try:
        report["z3_version"]=subprocess.check_output(["z3","--version"],text=True,timeout=10).strip()
        queries=[]
        for k in range(32):
            m=decoder_model(k); expr=expression(m)
            spec=f'(bvand e (ite (= a (_ bv{k} 6)) #b1 #b0))'
            queries.append((f"index_{k}_composition",f"(distinct {expr} {spec})","unsat"))
            for b in range(6):
                flip=f"(bvxor a (_ bv{1<<b} 6))"
                queries.append((f"index_{k}_address_bit_{b}",f"(distinct {expr} {expression(m,addr=flip)})","sat"))
            queries.append((f"index_{k}_enable",f"(distinct {expr} {expression(m,enable='(bvnot e)')})","sat"))
        expr=expression(decoder_model(7))
        queries.extend([
            ("mutant_drop_high_bit",f"(distinct {expr} (ite (= ((_ extract 4 0) a) (_ bv7 5)) e #b0))","sat"),
            ("mutant_wrong_index",f"(distinct {expr} {expression(decoder_model(8))})","sat"),
            ("mutant_swap_branches",f"(distinct {expr} (ite (= a (_ bv7 6)) #b0 e))","sat")])
        lines=["(set-logic QF_BV)","(set-option :timeout 10000)","(declare-fun a () (_ BitVec 6))",
               "(declare-fun e () (_ BitVec 1))"]
        for _,expr,expected in queries:
            lines.extend(["(push 1)",f"(assert {expr})","(check-sat)","(pop 1)"])
        smt=run/"models.smt2"; smt.write_text("\n".join(lines+["(exit)"])+"\n")
        p=subprocess.run(["z3","-smt2",str(smt)],capture_output=True,text=True,timeout=120)
        (run/"stdout.log").write_text(p.stdout); (run/"stderr.log").write_text(p.stderr)
        actual=p.stdout.splitlines()
        report["queries"]=[{"name":q[0],"expected":q[2],"actual":actual[i] if i<len(actual) else None} for i,q in enumerate(queries)]
        assert p.returncode==0 and actual==[q[2] for q in queries],(p.stdout,p.stderr)
        report.update(status="passed",query_count=len(queries),unsat=actual.count("unsat"),sat=actual.count("sat"),
                      local_sensitivity_queries=224,mutants=3)
        assert (len(queries),report["unsat"],report["sat"])==(259,32,227)
    except Exception as exc:
        report.update(status="failed",error=f"{type(exc).__name__}: {exc}"[:2000]); raise
    finally:
        save(); print(path.read_text(),flush=True); print(f"Summary: {path}",flush=True)
    return path


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--out",type=Path,required=True)
    execute(p.parse_args().out)

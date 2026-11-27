"""Independent four-state RTL fixture (Icarus) and finite encoded Z3 models."""
import argparse,json,subprocess,tempfile
from pathlib import Path
from rtlprep.state_conversion_candidates import state_map
from rtlprep.census_query import file_sha

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/"tests/fixtures/state_conversions_pr118.sv"
TB=ROOT/"tests/fixtures/state_conversions_pr118_tb.sv"


def execute(out):
    out=out.resolve(); out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out)); path=run/"summary.json"
    report={"status":"incomplete","scope":"four_state_fixture_and_encoded_state_models",
            "rtl_equivalence":"not_performed","temporal_proof":"not_performed"}
    def save(): path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    def command(args,filename):
        p=subprocess.run(args,capture_output=True,text=True,timeout=120)
        (run/(filename+".stdout.log")).write_text(p.stdout)
        (run/(filename+".stderr.log")).write_text(p.stderr)
        if p.returncode: raise RuntimeError(f"{args[0]} failed: {p.stderr[-1500:]}")
        return p.stdout
    save()
    try:
        report["iverilog_version"]=command(["iverilog","-V"],"iverilog-version").splitlines()[0]
        report["z3_version"]=command(["z3","--version"],"z3-version").strip()
        binary=run/"fixture.vvp"
        command(["iverilog","-g2012","-s","state_conversions_pr118_tb","-o",str(binary),str(FIXTURE),str(TB)],"compile")
        output=command(["vvp",str(binary)],"four-state")
        assert output.splitlines().count("PR118_FOUR_STATE_PASS checks=128")==1,output
        report["four_state_fixture"]={"status":"passed","vectors":64,"word_checks":128,
            "fixture_sha256":file_sha(FIXTURE),"testbench_sha256":file_sha(TB)}
        save()
        table=state_map("logic","bit")
        def encoded(t):
            # 00=0, 01=1, 10=X, 11=Z.
            return "(ite (= s #b00) #b"+t["0"]+" (ite (= s #b01) #b"+t["1"]+\
                   " (ite (= s #b10) #b"+t["x"]+" #b"+t["z"]+")))"
        spec="(ite (= s #b01) #b1 #b0)"
        up=state_map("bit","logic")
        queries=[("four_to_two",f"(distinct {encoded(table)} {spec})","unsat"),
                 ("two_to_four",f'(distinct (ite (= b #b1) #b0{up["1"]} #b0{up["0"]}) ((_ zero_extend 1) b))',"unsat")]
        for state,new in [("x","1"),("z","1"),("1","0")]:
            queries.append(("mutant_"+state,f"(distinct {encoded({**table,state:new})} {spec})","sat"))
        lines=["(set-logic QF_BV)","(set-option :timeout 10000)","(declare-fun s () (_ BitVec 2))",
               "(declare-fun b () (_ BitVec 1))"]
        for _,expr,_ in queries:
            lines+=["(push 1)",f"(assert {expr})","(check-sat)","(pop 1)"]
        smt=run/"models.smt2"; smt.write_text("\n".join(lines+["(exit)"])+"\n")
        actual=command(["z3","-smt2",str(smt)],"z3").splitlines()
        assert actual==[q[2] for q in queries],actual
        report.update(status="passed",queries=[{"name":q[0],"expected":q[2],"actual":a} for q,a in zip(queries,actual)],
                      query_count=5,unsat=2,sat=3)
    except Exception as exc:
        report.update(status="failed",error=f"{type(exc).__name__}: {exc}"[:3000]); raise
    finally:
        save(); print(path.read_text(),flush=True); print(f"Summary: {path}",flush=True)
    return path


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--out",type=Path,required=True)
    execute(p.parse_args().out)

"""Run reviewed formal properties; distinguish proof, cover and counterexample."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from rtlprep.formal import _sby_status
from scripts.run_cva6_ras import verify
from scripts.run_priority_pr47 import mutate

FIXTURES = Path(__file__).resolve().parents[1] / "tests/fixtures"

def verdict(mode, status, returncode, traces):
    if mode in ("prove","cover"):
        return "passed" if status == "PASS" and returncode == 0 and (mode != "cover" or traces) else "failed"
    if mode == "bmc":
        return "expected_counterexample" if status == "FAIL" and returncode != 0 and traces else "failed"
    raise ValueError("unsupported mode")

def config(mode, filenames, top, ras=False, plugin=False):
    if mode not in ("prove","cover","bmc"):
        raise ValueError("unsupported mode")
    if ras:
        rtl = filenames[:-1]
        script = ("plugin -i slang\n" if plugin else "") + "read_slang --top ras_formal_probe " + " ".join(rtl) + "\n"
        script += "read -formal -sv " + filenames[-1] + "\n"
    else:
        script = "read -formal -sv " + " ".join(filenames) + "\n"
    return f"[options]\nmode {mode}\ndepth 16\nmulticlock on\n\n[engines]\nsmtbmc z3\n\n[script]\n{script}prep -top {top}\n\n[files]\n" + "\n".join(filenames) + "\n"

def task(out, sources, top, mode, ras=False, plugin=False):
    out.mkdir(parents=True, exist_ok=True)
    names = [p.name for p in sources]
    if len(set(names)) != len(names):
        raise ValueError("duplicate source basename")
    for source in sources:
        shutil.copyfile(source,out/source.name)
    (out/"task.sby").write_text(config(mode,names,top,ras,plugin))
    proc = subprocess.run(["sby","-f","-d","work","task.sby"],cwd=out,
                          stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=300)
    (out/"console.log").write_text(proc.stdout)
    status = _sby_status(out/"work/status")
    traces = sorted(str(p.relative_to(out)) for p in (out/"work").glob("**/trace*.vcd"))
    return {"mode":mode,"sby_status":status,"returncode":proc.returncode,"traces":traces,
            "status":verdict(mode,status,proc.returncode,traces),
            "source_sha256":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}}

def execute(root,out):
    root,out=root.resolve(),out.resolve()
    if out==root or out.is_relative_to(root) or root.is_relative_to(out):
        raise ValueError("source/output must be disjoint")
    if any(not shutil.which(t) for t in ("yosys","sby","z3")):
        raise RuntimeError("Yosys, SBY and Z3 required")
    sources=verify(root)
    before=[hashlib.sha256(p.read_bytes()).hexdigest() for p in sources]
    out.mkdir(parents=True,exist_ok=True)
    report_path=out/"reset_formal.result.json"
    report_path.unlink(missing_ok=True)
    helptext=subprocess.check_output(["yosys","-Q","-T","-p","help read_slang"],text=True)
    plugin="No such command" in helptext
    fixture=[FIXTURES/"reset_formal_pr48.sv",FIXTURES/"reset_properties_pr48.sv"]
    ras=sources[:-1]+[FIXTURES/"cva6/ras_formal_probe.sv",FIXTURES/"cva6/ras_formal_properties.sv"]
    results={}
    report={"status":"not_run","tasks":results,"scope":"reviewed fixture and pinned RV32 depth-two RAS; formal model, not physical reset timing",
            "assumptions":["initial reset asserted","two-state formal semantics"],
            "design_coverage":"not_measured"}
    try:
        for label,files,top,is_ras in (("fixture",fixture,"reset_properties_pr48",False),("ras",ras,"ras_formal_properties",True)):
            for mode in ("prove","cover"):
                key=label+"_"+mode
                results[key]=task(out/key,files,top,mode,is_ras,plugin)
                if results[key]["status"]!="passed":
                    raise RuntimeError(key+" failed")
        # A real counterexample on the flush-priority mutant validates the
        # property harness, not just the simulator exit status.
        generated=out/"generated"
        generated.mkdir(exist_ok=True)
        altered=generated/"ras.sv"
        altered.write_text(mutate(sources[-2].read_text(),"flush_priority"))
        results["ras_mutant"]=task(out/"ras_mutant",ras[:-3]+[altered]+ras[-2:],
                                   "ras_formal_properties","bmc",True,plugin)
        if results["ras_mutant"]["status"]!="expected_counterexample":
            raise RuntimeError("mutant did not yield a formal counterexample")
        report["status"]="passed"
    finally:
        verify(root)
        if before!=[hashlib.sha256(p.read_bytes()).hexdigest() for p in sources]:
            raise ValueError("source snapshot changed")
        report_path.write_text(json.dumps(report,indent=2))
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-root",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(execute(a.source_root,a.out),indent=2))

if __name__=="__main__":
    main()

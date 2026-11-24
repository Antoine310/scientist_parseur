"""Run fresh static RAS probe and behavioral gold test on verified sources."""
import argparse
import hashlib
import json
from pathlib import Path
from cocotb_tools.runner import get_runner
from rtlprep.simulation import parse_cocotb_results
from scripts.run_cva6_ras import run, verify, TOP

def execute(root,out):
    root,out = root.resolve(),out.resolve()
    if out == root or out.is_relative_to(root) or root.is_relative_to(out):
        raise ValueError("disjoint output required")
    sources = verify(root)
    before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in sources]
    static = run(root,out/"static")
    out.mkdir(parents=True,exist_ok=True)
    xml = out/"simulation_results.xml"
    xml.unlink(missing_ok=True)
    report_path = out/"ras_simulation.result.json"
    report_path.unlink(missing_ok=True)
    runner = get_runner("verilator")
    runner.build(sources=sources, includes=[root/"core/include"], defines={},
                 hdl_toplevel=TOP, build_dir=out/"simulation_build",
                 build_args=["--timing","-Wno-fatal"], timescale=("1ns","1ps"),
                 always=True,clean=True)
    runner.test(hdl_toplevel=TOP,test_module="rtlprep.sim_tests.cva6_ras_official",
                build_dir=out/"simulation_build",test_dir=out,results_xml=str(xml),
                timescale=("1ns","1ps"))
    report = parse_cocotb_results(xml)
    verify(root)
    if before != [hashlib.sha256(p.read_bytes()).hexdigest() for p in sources]:
        raise ValueError("source snapshot changed")
    passed = (report["tests"],report["passed"],report["failed"],report["skipped"]) == (1,1,0,0)
    report.update({"status":"passed" if passed else "failed",
                   "source_fingerprint":static["source_fingerprint"],"top":TOP,
                   "clocked_vectors":263 if passed else None,
                   "asynchronous_reset_checks":2 if passed else None,
                   "scope":"depth_two_RAS_top_output_two_state",
                   "formal_proof":"not_performed","design_coverage":"not_measured"})
    report_path.write_text(json.dumps(report,indent=2))
    if not passed:
        raise RuntimeError("RAS behavioral test failed")
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-root",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(execute(a.source_root,a.out),indent=2))

if __name__=="__main__":
    main()

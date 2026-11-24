"""Evaluate frozen source-derived labels against real slang extraction."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile

from rtlprep.annotated_evaluation import load_annotations, evaluate_case
from rtlprep.manifest import load_design
from rtlprep.runner import dependency_design
from scripts.rtl_fixtures import load_lock, verify_checkout, blob_sha
from scripts.run_scalability_pr55 import ALU_FILES, write_manifest

ROOT=Path(__file__).resolve().parents[1]
ANNOTATIONS=ROOT/"benchmarks/annotations/pr56.json"


def execute(out,timeout=180):
    if type(timeout) is not int or not 10<=timeout<=600:
        raise ValueError("invalid timeout")
    out=out.resolve()
    entries=load_lock()
    for entry in entries:
        root=(ROOT/entry["destination"]).resolve()
        if out==root or out.is_relative_to(root):
            raise ValueError("output cannot be inside official RTL")
    entry=next(e for e in entries if e["repository"]=="openhwfoundation/cv32e40p")
    upstream=ROOT/entry["destination"]
    verify_checkout(upstream,entry)
    data=load_annotations(ANNOTATIONS)
    out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out))
    report_path=run/"evaluation.result.json"
    report={"schema_version":1,"status":"incomplete",
            "annotation_sha256":hashlib.sha256(ANNOTATIONS.read_bytes()).hexdigest(),
            "annotation_method":data["annotation_method"],"scope":data["scope"],
            "official_rtl_commit":entry["commit"],"cases":[],
            "design_coverage":"not_measured","formal_proof":"not_performed"}
    def save():
        report_path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    try:
        for case in data["cases"]:
            if case["name"]=="fixture":
                source=ROOT/"tests/fixtures/annotated_pr56.sv"
                sources=[source]
                includes=[]
                expected_source="tests/fixtures/annotated_pr56.sv"
            else:
                expected_source="rtl/cv32e40p_alu.sv"
                source=upstream/expected_source
                sources=[upstream/p for p in ALU_FILES]
                includes=[upstream/"rtl/include"]
            if case["source"]!=expected_source or blob_sha(source)!=case["git_blob"]:
                raise ValueError("annotation source identity mismatch")
            lines=source.read_text(encoding="utf-8").splitlines()
            if any(type(row.get("line")) is not int or not 1<=row["line"]<=len(lines)
                   for channel in ("signal","bit") for row in case[channel]):
                raise ValueError("annotation line outside source")
            directory=run/case["name"]
            directory.mkdir()
            manifest=directory/"design.json"
            write_manifest(manifest,case["top"],sources,includes)
            result=dependency_design(load_design(manifest),directory,timeout)
            if result["status"]!="passed":
                raise RuntimeError(f"extraction failed: {result}")
            graph=json.loads((directory/"rtl_dependencies.json").read_text(encoding="utf-8"))
            evaluated=evaluate_case(case,graph)
            for channel in ("signal","bit"):
                findings=evaluated[channel].pop("findings")
                (directory/f"{channel}.findings.json").write_text(json.dumps(findings,indent=2),encoding="utf-8")
            row={"name":case["name"],"source":case["source"],"git_blob":case["git_blob"],
                 "source_fingerprint":graph["source_fingerprint"],**evaluated}
            report["cases"].append(row)
            save()
            print(json.dumps(row,indent=2),flush=True)
        verify_checkout(upstream,entry)
        report["status"]="passed"
    except Exception as exc:
        report["status"]="failed"
        report["error"]=str(exc)
        raise
    finally:
        save()
        print(f"Report: {report_path}",flush=True)
    return report_path


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--timeout",type=int,default=180)
    args=p.parse_args()
    execute(args.out,args.timeout)

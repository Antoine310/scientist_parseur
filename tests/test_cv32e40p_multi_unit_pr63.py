import subprocess
from pathlib import Path
import pytest

from scripts import cv32e40p_pr63 as spec
from scripts.run_cv32e40p_multi_unit_pr63 import qualified_labels, score_unit, check_structure
from scripts.rtl_fixtures import FixtureError

@pytest.mark.parametrize("name",list(spec.CASES))
def test_label_provenance_and_uniqueness(name):
    case=spec.CASES[name]
    rows=qualified_labels(case)
    keys={(r["source"],r["target"],r["kind"],r["sequential"]) for r in rows}
    assert len(keys)==len(rows)
    assert {r["label"] for r in rows}=={"positive","negative"}
    assert all(r["line"]>0 and r["note"] for r in rows)
    assert all(r["source"].startswith(case["owner"]) and
               r["target"].startswith(case["owner"]) for r in rows)
    assert case["file"] in case["sources"]

def test_new_candidate_count():
    assert sum(len(c["labels"]) for c in spec.CASES.values())==37
    assert sum(r["label"]=="positive" for c in spec.CASES.values() for r in c["labels"])==27
    assert len(spec.EXTRA_BLOBS)==6

def graph_for(case,select):
    rows=qualified_labels(case)
    top=case["top"]
    nodes={top+"."+r[k] for r in rows for k in ("source","target")}
    edges=[{**r,"source":top+"."+r["source"],"target":top+"."+r["target"]}
           for r in rows if select(r)]
    return {"top":top,"nodes":sorted(nodes),"edges":edges}

def test_perfect_label_score():
    case=spec.CASES["register_file"]
    score=score_unit(case,graph_for(case,lambda r:r["label"]=="positive"))
    assert (score["tp"],score["tn"],score["fn"],score["fp"])==(8,2,0,0)

def test_missed_labels_reported_not_hidden():
    case=spec.CASES["decoder"]
    score=score_unit(case,graph_for(case,lambda r:r["label"]=="negative"))
    assert (score["tp"],score["tn"],score["fn"],score["fp"])==(0,0,6,2)

def test_missing_label_endpoint_rejected():
    case=spec.CASES["controller"]
    g=graph_for(case,lambda r:False)
    g["nodes"].pop()
    with pytest.raises(ValueError,match="absent"):
        score_unit(case,g)

def test_wrapper_has_explicit_parameters():
    assert ".ADDR_WIDTH(6)" in spec.REGFILE_WRAPPER
    assert ".DATA_WIDTH(32)" in spec.REGFILE_WRAPPER
    assert ".FPU(0)" in spec.REGFILE_WRAPPER
    assert ".ZFINX(0)" in spec.REGFILE_WRAPPER

def command(directory,*args):
    return subprocess.check_output(["git","-C",str(directory),*args],text=True).strip()

@pytest.fixture
def checkout(tmp_path,monkeypatch):
    repo=tmp_path/"repo"
    repo.mkdir()
    command(repo,"init","-q")
    command(repo,"config","user.name","RTLPrep Test")
    command(repo,"config","user.email","rtlprep@example.invalid")
    command(repo,"config","core.autocrlf","false")
    (repo/"one.sv").write_bytes(b"module one; endmodule\n")
    (repo/"two.sv").write_bytes(b"module two; endmodule\n")
    command(repo,"add","one.sv","two.sv")
    command(repo,"commit","-qm","fixture")
    commit=command(repo,"rev-parse","HEAD")
    pins={p:command(repo,"rev-parse","HEAD:"+p) for p in ("one.sv","two.sv")}
    monkeypatch.setattr(spec,"COMMIT",commit)
    monkeypatch.setattr(spec,"EXTRA_BLOBS",{"two.sv":pins["two.sv"]})
    entry={"repository":"openhwfoundation/cv32e40p","commit":commit,"blobs":{"one.sv":pins["one.sv"]}}
    return repo,entry,pins

def test_materialization_exact_and_read_only(tmp_path,checkout):
    repo,entry,pins=checkout
    # Remove an extra working-tree file: materialization uses the committed blob,
    # not this worktree. Production runner separately requires a clean checkout.
    (repo/"two.sv").unlink()
    before=command(repo,"status","--porcelain")
    dst=tmp_path/"snapshot"
    assert spec.materialize(repo,dst,entry)==pins
    assert spec.blob_bytes((dst/"two.sv").read_bytes())==pins["two.sv"]
    assert not (repo/"two.sv").exists()
    assert command(repo,"status","--porcelain")==before
    assert command(repo,"rev-parse","HEAD")==entry["commit"]

def test_wrong_blob_rejected(tmp_path,checkout):
    repo,entry,_=checkout
    entry["blobs"]["one.sv"]="0"*40
    with pytest.raises(FixtureError,match="tree blob mismatch"):
        spec.materialize(repo,tmp_path/"snapshot",entry)

def test_existing_snapshot_not_overwritten(tmp_path,checkout):
    repo,entry,_=checkout
    dst=tmp_path/"snapshot"
    dst.mkdir()
    (dst/"keep").write_text("keep")
    with pytest.raises(FileExistsError):
        spec.materialize(repo,dst,entry)
    assert (dst/"keep").read_text()=="keep"

def test_wrong_commit_rejected(tmp_path,checkout):
    repo,entry,_=checkout
    entry["commit"]="0"*40
    with pytest.raises(FixtureError,match="lock identity"):
        spec.materialize(repo,tmp_path/"snapshot",entry)

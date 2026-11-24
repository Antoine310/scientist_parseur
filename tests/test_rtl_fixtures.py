import subprocess
from pathlib import Path
import pytest
from scripts import rtl_fixtures as f


@pytest.fixture
def local_repo(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    f.git(source, "init", "--quiet")
    (source / "rtl").mkdir()
    path = source / "rtl/test.v"
    path.write_text("module test; endmodule\n")
    f.git(source, "add", "rtl/test.v")
    f.git(source, "-c", "user.email=test@example.invalid", "-c", "user.name=Test",
          "commit", "--quiet", "-m", "fixture")
    f.git(source, "remote", "add", "origin", "https://github.com/ZipCPU/wbuart32.git")
    entry = {"repository":"ZipCPU/wbuart32","destination":"checkout",
             "commit":f.git(source,"rev-parse","HEAD"),"blobs":{"rtl/test.v":f.blob_sha(path)}}
    return source, entry


def test_reviewed_lock():
    entries=f.load_lock()
    assert len(entries)==4
    assert sum(len(e["blobs"]) for e in entries)==15


def test_existing_clean(local_repo):
    source,entry=local_repo
    f.verify_checkout(source,entry)
    f.verify_checkout(source,entry)


def test_dirty_not_modified(local_repo):
    source,entry=local_repo
    path=source/"rtl/test.v"
    path.write_text("changed")
    with pytest.raises(f.FixtureError,match="Dirty"):
        f.verify_checkout(source,entry)
    assert path.read_text()=="changed"


def test_wrong_revision(local_repo):
    source,entry=local_repo
    entry=dict(entry,commit="0"*40)
    with pytest.raises(f.FixtureError,match="Wrong revision"):
        f.verify_checkout(source,entry)


def test_wrong_blob(local_repo):
    source,entry=local_repo
    entry=dict(entry,blobs={"rtl/test.v":"0"*40})
    with pytest.raises(f.FixtureError,match="Blob mismatch"):
        f.verify_checkout(source,entry)


def test_offline_missing_does_not_create(tmp_path,local_repo):
    _,entry=local_repo
    with pytest.raises(f.FixtureError,match="Missing checkouts"):
        f.run(tmp_path,entries=[entry])
    assert not (tmp_path/"checkout").exists()


def test_install_and_repeat(tmp_path,local_repo,monkeypatch):
    source,entry=local_repo
    real_git=f.git
    calls=[]
    def local_git(directory,*args,network=False):
        if args[0]=="fetch":
            calls.append(args)
            args=tuple(str(source) if a=="origin" else a for a in args)
        return real_git(directory,*args,network=network)
    monkeypatch.setattr(f,"git",local_git)
    assert f.run(tmp_path,install=True,entries=[entry])==0
    assert f.run(tmp_path,install=True,entries=[entry])==0
    assert f.run(tmp_path,entries=[entry])==0
    assert len(calls)==1
    assert (tmp_path/"checkout/rtl/test.v").read_bytes()==(source/"rtl/test.v").read_bytes()


def test_existing_conflict_blocks_all(tmp_path,local_repo):
    _,entry=local_repo
    conflict=tmp_path/"conflict"
    conflict.mkdir()
    (conflict/"keep").write_text("keep")
    second=dict(entry,destination="conflict")
    with pytest.raises(f.FixtureError):
        f.run(tmp_path,install=True,entries=[entry,second])
    assert not (tmp_path/"checkout").exists()
    assert (conflict/"keep").read_text()=="keep"


def test_symlink_refused(tmp_path,local_repo):
    source,entry=local_repo
    (tmp_path/"checkout").symlink_to(source,target_is_directory=True)
    with pytest.raises(f.FixtureError,match="Symlink"):
        f.run(tmp_path,install=True,entries=[entry])

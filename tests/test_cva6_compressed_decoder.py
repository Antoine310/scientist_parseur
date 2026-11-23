"""PR35: integrity gates, conservative reports and pinned real CVA6 decoder."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from rtlprep.field_validation import git_blob_sha1
from scripts import run_cva6_compressed_decoder as probe


def make_checkout(tmp_path: Path, monkeypatch, data: bytes = b"module fake; endmodule\n"):
    root = tmp_path / "upstream"
    path = root / "core/compressed_decoder.sv"
    path.parent.mkdir(parents=True)
    path.write_bytes(data)
    monkeypatch.setattr(probe, "PINNED_SOURCES", (
        ("core/compressed_decoder.sv", git_blob_sha1(data)),
    ))
    return root, path


def test_pinned_upstream_file_is_verified_before_eda(tmp_path, monkeypatch):
    root, file = make_checkout(tmp_path, monkeypatch)
    sources, revision = probe.verify_pinned_sources(root)
    assert sources == [file]
    assert revision == "not_checked_no_git_checkout"
    file.write_bytes(b"module tampered; endmodule\n")
    with pytest.raises(ValueError, match="git blob mismatch"):
        probe.verify_pinned_sources(root)


def test_missing_or_escaped_upstream_source_fails_closed(tmp_path, monkeypatch):
    root, file = make_checkout(tmp_path, monkeypatch)
    file.unlink()
    with pytest.raises(ValueError, match="missing or outside checkout"):
        probe.verify_pinned_sources(root)
    outside = tmp_path / "unexpected.sv"
    outside.write_bytes(b"module fake; endmodule\n")
    file.symlink_to(outside)
    with pytest.raises(ValueError, match="missing or outside checkout"):
        probe.verify_pinned_sources(root)


def test_git_checkout_commit_is_checked_not_inferred_from_blobs(tmp_path, monkeypatch):
    if shutil.which("git") is None:
        pytest.skip("git missing")
    root, _ = make_checkout(tmp_path, monkeypatch)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run([
        "git", "-C", str(root), "-c", "user.name=RTLPrep",
        "-c", "user.email=rtlprep@example.invalid", "commit", "-qm", "test",
    ], check=True)
    with pytest.raises(ValueError, match="Unexpected CVA6 checkout"):
        probe.verify_pinned_sources(root)


@pytest.mark.parametrize("timeout", [0, 901, 1.5, True, "30"])
def test_timeout_is_bounded_before_external_tools(tmp_path, timeout):
    with pytest.raises(ValueError, match="timeout"):
        probe.run_probe(tmp_path / "missing", tmp_path / "output", timeout=timeout)


def test_output_cannot_modify_upstream_checkout(tmp_path):
    root = tmp_path / "upstream"
    root.mkdir()
    for dest in (root, root / "reports", tmp_path):
        with pytest.raises(ValueError, match="disjoint"):
            probe.run_probe(root, dest)


def test_upstream_metadata_and_configuration_are_explicit():
    assert probe.UPSTREAM_COMMIT == "742dc82a0c706e0a3bfb98b709fd3ee06d50d12a"
    assert probe.UPSTREAM_REPOSITORY == "openhwfoundation/cva6"
    assert probe.CONFIGURATION == "cv32a6_imac_sv32"
    assert probe.TOP == "rtlprep_cva6_compressed_decoder"
    assert len(probe.PINNED_SOURCES) == 5
    assert len({path for path, sha in probe.PINNED_SOURCES}) == 5
    assert all(len(sha) == 40 for _, sha in probe.PINNED_SOURCES)
    harness = probe.WRAPPER.read_text(encoding="utf-8")
    assert "build_config_pkg::build_config(cva6_config_pkg::cva6_cfg)" in harness
    assert "compressed_decoder #(.CVA6Cfg(SelectedCfg))" in harness


@pytest.mark.skipif(shutil.which("slang") is None, reason="real slang unavailable")
def test_real_pinned_cva6_module_and_report(tmp_path):
    root = Path("upstream_cva6").resolve()
    if not root.is_dir():
        pytest.skip("pinned CVA6 sparse checkout unavailable")
    result = probe.run_probe(root, tmp_path / "cva6", timeout=240)
    assert result["elaboration"] == "passed", result
    assert result["checkout_revision_status"] == "verified_exact_commit"
    assert result["source_integrity"] == "verified_pinned_git_blobs"
    assert result["design_coverage"] == "not_measured"
    assert result["accuracy"] == "not_measured_without_independent_exhaustive_oracle"
    assert result["functional_correctness"] == "not_tested"
    assert result["benchmarked_llm"] is False
    assert result["graph_counts"]["nodes"] > 0
    assert result["graph_counts"]["edges"] > 0
    assert result["ports"]["instr_i"] == "In"
    assert set(probe.OUTPUTS) <= set(result["ports"])
    assert set(probe.OUTPUTS) == set(result["fanin_outputs"])
    assert Path(tmp_path / "cva6/cva6_compressed_decoder_report.json").is_file()
    on_disk = json.loads((tmp_path / "cva6/cva6_compressed_decoder_report.json")
                         .read_text(encoding="utf-8"))
    assert on_disk["upstream_commit"] == probe.UPSTREAM_COMMIT
    assert on_disk["warnings_total"] == result["graph_counts"]["warnings"]
    # Observations from this exact pinned Git snapshot with slang v12.1.
    # This baseline must not silently lose assignments or dependencies.
    assert result["graph_counts"] == {"nodes": 12, "edges": 13, "warnings": 0}
    assert result["observed_analyzers"]["expressions"]["counts"]["captured"] == 93
    assert result["observed_analyzers"]["expressions"]["counts"]["partial_expressions"] == 0
    assert result["observed_analyzers"]["register_flow"]["counts"]["captured"] == 0
    # PR39 measured on official pinned CVA6 with real slang v12.1.
    # Positional *syntax* only, not an exhaustive functional correctness oracle.
    bits = result["observed_analyzers"]["bit_accesses"]["counts"]
    assert bits["assignments_seen"] == 93
    assert bits["captured"] == 52
    assert bits["precise"] == 52
    assert bits["partial"] == 0
    assert bits["unsupported_targets"] == 0
    assert bits["unsupported_statements"] == 0
    assert bits["procedural_blocks_visited"] == 1
    assert bits["truncated"] is False
    snapshot = json.loads((tmp_path / "cva6/rtl_dependencies.json").read_text())
    from collections import Counter
    reasons = dict(sorted(Counter(item["reason"] for item in
                                  snapshot["bit_accesses"]["items"]
                                  if item["coverage"] == "partial").items()))
    assert reasons == {}
    # PR40: the one previously partial UnaryOp is a width-preserving
    # BitwiseNot. Preserve the positional source AND the inverted value.
    inversions = [
        item for item in snapshot["bit_accesses"]["items"]
        if any(segment.get("value_transform") == "bitwise_not"
               for segment in item["source_segments"])
    ]
    assert len(inversions) == 1, inversions
    item = inversions[0]
    assert item["target"].endswith(".decoder_i.instr_o"), item
    assert item["source"]["line"] == 708, item
    transformed = [segment for segment in item["source_segments"]
                   if segment.get("value_transform") == "bitwise_not"]
    assert len(transformed) == 1, transformed
    assert transformed[0]["source"] == (
        "rtlprep_cva6_compressed_decoder.instr_i"
    )
    assert transformed[0]["selection"] == {"kind": "bit", "index": 15}
    assert "value_transform" not in next(
        seg for seg in item["source_segments"]
        if seg["selection"].get("kind") == "range"
    )
    print("PR40_CVA6_BITWISE_NOT", {
        "precise": bits["precise"], "partial": bits["partial"],
        "inversion_source": transformed[0]["source"],
        "inversion_index": transformed[0]["selection"]["index"],
    })
    assert result["design_coverage"] == "not_measured"
    assert result["coverage_assessment"] == "no_reported_limits_within_scopes"
    assert result["warnings_sample"] == []
    assert all(row["observed_input_reachable"] and not row["truncated"]
               for row in result["fanin_outputs"].values())
    # No reported analyzer limits does not establish full design coverage.
    assert result["design_coverage"] == "not_measured"

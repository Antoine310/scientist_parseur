"""Régression de la liste blanche de contenus OpenHW pour EQY.

Les tests ci-dessous n'ont besoin ni d'EDA ni de fichiers tiers ;
l'essai sur le vrai CV32E40P est exécuté séparément en CI.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rtlprep import equivalence
from rtlprep.manifest import load_design


ORIGINAL = (
    "module cv32e40p_popcnt(input wire [31:0] in_i, output wire [5:0] result_o);\n"
    "  wire [4:0] cnt_l4 [0:1];\n"
    "  assign result_o = {1'b0, cnt_l4[0]} + {1'b0, cnt_l4[1]};\n"
    "endmodule\n"
)


def manifest(path: Path, source: Path):
    path.write_text(json.dumps({
        "top": "cv32e40p_popcnt",
        "sources": [str(source)],
        "include_dirs": [], "defines": [],
    }))
    return load_design(path)


def pair(tmp_path, monkeypatch, variant="cv32e40p_popcnt_refactored.sv"):
    reference = tmp_path / "cv32e40p_popcnt.sv"
    gate = tmp_path / variant
    reference.write_text(ORIGINAL)
    gate.write_text(equivalence.popcnt_variant(ORIGINAL, filename=variant))
    monkeypatch.setattr(equivalence, "POPCNT_GOLD_BLOB",
                        equivalence.git_blob_digest(reference.read_bytes()))
    return manifest(tmp_path / "gold.json", reference), manifest(tmp_path / "gate.json", gate)


def test_both_approved_variants_are_exact_deterministic_transformations(tmp_path, monkeypatch):
    for variant in ("cv32e40p_popcnt_refactored.sv", "cv32e40p_popcnt_buggy.sv"):
        gold, gate = pair(tmp_path, monkeypatch, variant)
        equivalence.validate_pair(gold, gate)
        cfg = equivalence.make_eqy_config(gold, gate)
        assert "prep -top cv32e40p_popcnt" in cfg
        assert variant in cfg


def test_reject_unknown_gold_even_when_name_matches(tmp_path, monkeypatch):
    gold, gate = pair(tmp_path, monkeypatch)
    gold.sources[0].write_text(ORIGINAL + "// extra code\n")
    with pytest.raises(ValueError, match="différente"):
        equivalence.validate_pair(gold, gate)


def test_reject_candidate_changed_or_code_injection(tmp_path, monkeypatch):
    gold, gate = pair(tmp_path, monkeypatch)
    gate.sources[0].write_text(gate.sources[0].read_text() + "\ninitial $display(\"UNSAFE\");\n")
    with pytest.raises(ValueError, match="non conforme"):
        equivalence.validate_pair(gold, gate)


def test_reject_unknown_candidate_filename_and_absent_anchor(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="non approuvée"):
        equivalence.popcnt_variant(ORIGINAL, filename="other.sv")
    with pytest.raises(ValueError, match="absente"):
        equivalence.popcnt_variant(ORIGINAL.replace(equivalence.POPCNT_ASSIGN, ""),
                                   filename="cv32e40p_popcnt_buggy.sv")
    gold, gate = pair(tmp_path, monkeypatch)
    changed = tmp_path / "other.sv"
    changed.write_bytes(gate.sources[0].read_bytes())
    with pytest.raises(ValueError, match="Noms des fichiers"):
        equivalence.validate_pair(gold, manifest(tmp_path / "bad.json", changed))


def test_no_broad_allowlist_for_same_top(tmp_path, monkeypatch):
    gold, gate = pair(tmp_path, monkeypatch)
    gate.sources[0].write_text(ORIGINAL)
    with pytest.raises(ValueError, match="non conforme"):
        equivalence.validate_pair(gold, gate)


def test_git_blob_digest_uses_actual_nul_separator():
    data = b"hello\n"
    import hashlib
    expected = hashlib.sha1(b"blob 6\x00hello\n").hexdigest()
    assert equivalence.git_blob_digest(data) == expected

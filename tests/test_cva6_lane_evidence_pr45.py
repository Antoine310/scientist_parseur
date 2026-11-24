import pytest
from rtlprep.cva6_lane_evidence import _reference_pairs, compare_lanes

CHILD = "top.decoder_i"

@pytest.mark.parametrize("family,src,dst", [
    ("addi",12,31), ("addi",7,15), ("addi4spn",6,22),
    ("lw",5,26), ("sw",6,9),
])
def test_reference(family,src,dst):
    assert _reference_pairs(family)[src,dst] > 0

def graph(rows, truncated=False):
    return {"schema_version":1,"bit_accesses":{"items":rows,"counts":{"truncated":truncated}}}

def row():
    return {"target":CHILD+".instr_o","source":{"file":"/p/compressed_decoder.sv","line":267},
            "coverage":"rhs_lanes_only","target_selection":{"kind":"whole"},"rhs_width":32,
            "source_segments":[{"source":CHILD+".instr_i","selection":{"kind":"bit","index":6},
                                "rhs_lsb":9,"rhs_msb":9}]}

def relation(g):
    return next(r for r in compare_lanes(g,child_instance=CHILD)["relations"]
                if (r["family"],r["source_bit"],r["target_bit"]) == ("sw",6,9))

def test_match_and_missing():
    assert relation(graph([row()]))["static_status"] == "matched"
    r = row()
    r["source_segments"][0]["rhs_lsb"] = r["source_segments"][0]["rhs_msb"] = 10
    assert relation(graph([r]))["static_status"] == "not_observed"

def test_abstention():
    assert relation(graph([]))["static_status"] == "unknown"
    assert relation(graph([row(),row()]))["static_status"] == "unknown"
    assert relation(graph([row()],True))["static_status"] == "unknown"

def test_inversion_not_identity():
    r = row()
    r["source_segments"][0]["value_transform"] = "bitwise_not"
    assert relation(graph([r]))["static_status"] == "not_observed"

def test_no_proof_from_gold():
    result = compare_lanes(graph([row()]),child_instance=CHILD,gold_passed=True)
    assert result["formal_proof"] == "not_performed"
    assert result["design_coverage"] == "not_measured"
    assert all(r["formal_proof"] == "not_performed" for r in result["relations"])

"""Compare audited assignment-local lanes against independent RV32C references.

No control-path feasibility, full graph recall or formal proof is implied.
"""
from collections import Counter
from rtlprep.cva6_compressed_reference import FAMILIES, encode, expected

# Audited assignment locations in the pinned CVA6 decoder. These are
# provenance anchors, not an inference that a branch guard is reachable.
ANCHORS = {"addi": 336, "addi4spn": 57, "lw": 96, "sw": 267}

def _reference_pairs(family):
    """Derive identity lanes from independent oracle one-bit perturbations.

    Only pairs of ordinary valid encodings are considered. Require every
    admissible pair for a source bit to toggle the destination bit.
    """
    table = {encode(family, p): expected(encode(family, p)) for p in range(2048)}
    result = {}
    for bit in range(2, 13):
        common, count = 0xFFFFFFFF, 0
        for word, ref in table.items():
            if word & (1 << bit) or ref.classification != "valid":
                continue
            other = table.get(word ^ (1 << bit))
            if other is None or other.classification != "valid":
                continue
            common &= ref.instruction ^ other.instruction
            count += 1
        for target in range(32):
            if count and common & (1 << target):
                # Ensure identity, rather than inversion or a conditional XOR.
                if all(((w >> bit) & 1) == ((r.instruction >> target) & 1)
                       for w, r in table.items() if r.classification == "valid"):
                    result[(bit, target)] = count
    return result

def compare_lanes(graph, *, child_instance, gold_passed=False):
    if graph.get("schema_version") != 1:
        raise ValueError("graph schema v1 required")
    section = graph["bit_accesses"]
    rows = section["items"]
    records = []
    summaries = {}
    for family, line in ANCHORS.items():
        reference = _reference_pairs(family)
        candidates = [r for r in rows if r.get("target") == child_instance + ".instr_o"
                      and r.get("source", {}).get("line") == line
                      and str(r.get("source", {}).get("file", "")).endswith("/compressed_decoder.sv")]
        observed = set()
        complete = False
        if len(candidates) == 1:
            row = candidates[0]
            # The pinned declaration is logic [31:0] instr_o. RHS lanes
            # therefore map directly only for this audited whole assignment.
            complete = (row.get("coverage") == "rhs_lanes_only"
                        and row.get("target_selection") == {"kind": "whole"}
                        and row.get("rhs_width") == 32
                        and not section.get("counts", {}).get("truncated", True))
            if complete:
                for seg in row["source_segments"]:
                    if seg.get("source") != child_instance + ".instr_i":
                        continue
                    select = seg.get("selection", {})
                    if select.get("kind") == "bit":
                        lo = hi = select["index"]
                    elif select.get("kind") == "range":
                        lo, hi = select["lsb"], select["msb"]
                    else:
                        complete = False
                        continue
                    dst, end = seg["rhs_lsb"], seg["rhs_msb"]
                    if hi - lo != end - dst or not (0 <= lo <= hi < 32 and 0 <= dst <= end < 32):
                        complete = False
                        continue
                    transform = seg.get("value_transform", "identity")
                    observed.update((lo + k, dst + k, transform) for k in range(hi - lo + 1))
        counts = Counter()
        for (src, dst), pairs in sorted(reference.items()):
            status = ("matched" if (src, dst, "identity") in observed else
                      "not_observed" if complete else "unknown")
            counts[status] += 1
            records.append({"family": family, "source_bit": src, "target_bit": dst,
                            "assignment_line": line, "static_status": status,
                            "reference_valid_pairs": pairs,
                            "behavioral_scope": "gold_family_suite_passed" if gold_passed else "not_validated",
                            "formal_proof": "not_performed"})
        extras = sorted(observed - {(a,b,"identity") for a,b in reference})
        summaries[family] = {"reference_relations": len(reference), "counts": dict(counts),
                             "unmatched_observed_lanes": [list(x) for x in extras],
                             "assignment_candidates": len(candidates),
                             "supported_assignment": complete}
    return {"schema_version": 1, "scope": "audited_assignment_local_identity_lanes",
            "families": summaries, "relations": records,
            "design_coverage": "not_measured", "formal_proof": "not_performed",
            "accuracy": "not_measured_globally",
            "limitations": ["No guard feasibility or intermodule proof",
                            "Unmatched observed lanes are not automatically false positives",
                            "Gold suite association is not a separate per-relation simulation"]}

# PR45 — CVA6 assignment-local lane evidence

This experiment joins fresh RTLPrep static output with fresh PR44 gold and
negative-control runs on the same pinned RV32 CVA6 checkout and wrapper.
It reuses the existing probe and simulation runner; no official RTL changes.

The independent Python ISA oracle is evaluated over all 2048 lower halfwords
per family. For each variable input bit, compare valid encodings differing
only in that bit. Retain identity output lanes with at least one admissible
pair and the same value for every valid encoding. This is a reference
relation, not an observation from slang.

The static comparison is limited to four manually audited assignment
locations in the pinned decoder (ADDI, ADDI4SPN, LW, SW). Whole 32-bit
assignments with positioned RHS lanes are compared at the child instance.
The report distinguishes matched, not_observed and unknown, and lists
unmatched observed lanes without automatically calling them false positives.
Branch guard feasibility, intermodule propagation, global precision/recall,
formal proof, and direct per-relation simulation measurements are out of scope.
Gold association means the corresponding family suite passed, not a new
per-relation experiment. Four mutants are associated at family level only.

Reproduce with slang and Verilator available:

    python -m pytest -q tests/test_cva6_lane_evidence_pr45.py
    python -m scripts.run_cva6_lane_evidence --source-root upstream_cva6 --out reports/pr45

Output: reports/pr45/cva6_lane_evidence.json, static graph and simulation
reports/XML. Source hashes are checked before and after the combined run.
The report includes graph and gold-report digests, not producer authentication.
MCP exposure of this new report is not implemented in this PR; existing
read-only evidence interfaces remain unchanged. Results pending CI.

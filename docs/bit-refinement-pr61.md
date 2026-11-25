# PR61 — targeted bit-dependency refinement on pinned CV32E40P

## Measured baseline (PR60)

Legacy bit graph: 479 assignments, 222 supported, 257 partial, 445
edges, not truncated. Of the partial rows 223 had partial_bit_access,
32 unvalidated_ast_positions, one unproven_packed_layout and one
target_rhs_width_mismatch. The separate array graph had 94 rows,
one supported, 93 partial, five edges. The two inventories overlap.

## Changes

* Accept direct elaborated parameter ports only when the caller explicitly
  enters an instance body; preserve exact semantic identity, lexical
  inheritance, duplicate rejection and typed nonnegative bounds.
  The default localparam-only API is unchanged. No source-level default
  is substituted for the elaborated parameter value.
* For direct continuous array assignments, resolve an explicit Conversion
  to a proven unsigned scalar/vector of a bounded nonnegative constant.
  Recognize the exact slang system call $unsigned with one proven
  integral constant operand and matching input width. Apply truncation
  or zero extension and check any serialized constant tags against
  independently computed values. Store each constant destination
  coordinate and bit value separately; no synthetic source edges.
  Runtime conversions, signed targets, negative/unknown values and
  unsupported types/operators remain outside this extension.
* Keep the PR60 historical legacy graph counts as a regression floor
  (same assignment universe, no loss of supported rows or edges,
  no truncation), rather than an exact ceiling. The new PR61 oracle
  separately checks the recovered positions. The frozen PR56 annotations
  are unchanged. The historical graph's width-preserving conversion
  policy is unchanged.

## Source-derived official RTL oracles

Pinned CV32E40P commit b353438ff469c030c89f6804f3b24a2852880e8b:
rtl/cv32e40p_alu_div.sv line 95, ResReg_DP_rev[index] =
ResReg_DP[C_WIDTH-1-index], 32 exact positions for the instantiated
width. rtl/cv32e40p_ff_one.sv gen_index_lut, index_lut[j] =
$unsigned(j), 32 elements of five constant bits, 160 coordinates.
These are independently calculated from the source assignments, not
from graph predictions. They are targeted development oracles, not
a representative whole-ALU or independently human-reviewed corpus.
No simulation of the official ALU is added by this PR.

Expected legacy improvement: at least 32 more supported assignments,
at most 225 partial, at least 477 edges, no truncation. The LUT oracle
tests 32 constant assignments in the separate array graph, not 160
source dependencies. Do not add the two graphs' counts or equate
them with design coverage.

## Independent fixture

Two differently specialized module instances (W=8, W=5), reversal
using W-1-k and LUT assignment using $unsigned(k+8) to a 3-bit element.
Exact 13 reversal edges, 39 constant coordinates, and 256 vectors
in Verilator/cocotb. The 5-bit input is a deterministic transform of
the 8-bit input, not a Cartesian product.

    python -m pytest -q -rs tests/test_bit_refinement_pr61.py
    python -m pytest -q -rs
    python -m scripts.run_bit_refinement_pr61 --out reports/pr61

Report: reports/pr61/run-*/bit_refinement.result.json. AST, graph and
diagnostics are retained in per-case subdirectories. Official RTL is
verified against the existing lock before and after execution, never
modified. Actual real-slang compatibility, metrics and CI are pending.

Further work: classify partial_bit_access at the underlying reason level,
then handle selected muxes, arithmetic candidate semantics and dynamic
indices separately. No functional influence, formal proof, whole-core
coverage or arbitrary conversion correctness is claimed.

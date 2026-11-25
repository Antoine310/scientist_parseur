# PR71 — Fixed multidimensional packed coordinates

## Scope

PR70 is merged; the flat graph has 1,199 captured assignments,
531 supported, 668 partial, 2,842 edges. ALU 479/254/225/477.
The original coordinate analyzer already supports 33 of 94 ALU
rows and 94 of 221 core rows. In particular the 29 unimplemented
mhpmcounter_q words (line 1462) and the ALU LUT constants were
already represented: they are not new recoveries.

Extend array_dependencies with evidence for existing continuous
partial rows and already-captured procedural assignments whose
root selection involves an explicitly declared multidimensional
packed logic/bit vector. No new flat rows, flattened indices or
changes to the historical flat graph. A word selection is not a
one-bit selection. Coordinates retain each outer dimension and
the final declared bit index (including nonzero lower bounds and
ascending dimensions).

Resolve declaration identity through the existing SignalResolver.
Require the same declared base layout and verify each selection's
elaborated result type, exact bounds, orientation, lexical parameter
identity and final assignment type. Support complete selected words,
optional final simple ranges/bits, direct equal-width same-state
copies, and explicitly typed literal-only Conversion chains.
The latter yield constant_target_positions (no dynamic RHS source,
no value field), distinct from PR61's evaluated
constant_target_coordinates. No constant-value or X/Z proof.
Dynamic casts, operators, aggregate copies, runtime selectors,
unpacked procedural arrays, aliases and unsupported contexts remain
partial or outside this captured scope.

Reuse the existing bounded bit-access traversal (including guard,
event, NBA and timing metadata). Link via in-memory node identity
and the sorted flat assignment ordinal; no AST address is persisted.
For continuous rows, retry only existing partials with an exact
link; append procedural rows after the legacy inventory. Prior
supported coordinate rows and their edges remain identical.
Existing array row, width, dimension and shared edge/constant-position
caps remain unchanged. Partial rows never emit a partial mapping;
budget exhaustion is reported by the existing analyzer limits.
No procedural priority, final-write, temporal or influence claims.

## Validation

24 unit cases: coordinate and constant oracles, negatives for
dynamic/out-of-bounds selectors, types, casts, assignment forms and
operators, legacy graph equality, duplicate prevention, lexical
identity, budget and unsupported timing, ascending/final range/bit.

Real slang fixture with two 4-bit packed words [2:1][7:4]:
eight dynamic position edges and eight reset constant positions,
256 exhaustive two-state word permutations in Verilator/cocotb and
one reset check. This is not a proof of arbitrary four-state behavior.

Compare old/new policies on identical elaborated AST/index; retain
all prior supported coordinate rows and their edges, exact flat
graph and other fields. Validate artifact-local flat assignment
links (target, source location, unique ordinal), report new supported
coordinate rows that were flat-partial, by instance, dynamic edges
and constant positions separately. Do not add all array rows to flat
support counts. Exact prior core/ALU flat and array baseline gates.

Independent register-file source-derived oracle (official pinned
cv32e40p_register_file_ff.sv, integer configuration):
- lines 119 and 122: mem[0] constant writes, 32 positions each.
- line 131: 31 reset words (1..31), 992 constant positions.
- lines 133/134: 31 writes each from wdata_b_i/wdata_a_i,
  32 edges each with matching source/target bit number.
- expected 95 assignment-local rows, 1,984 dynamic edges and
  1,056 constant positions. Require all exact word indices and
  source positions. These are expected, not measured results.
  No proof of register priority or x0 behavior in the real CPU.

The reference diagnostics retain frozen PR56 labels and PR65
signal labels/paths. The new workflow runs on PR, main pushes and
manual dispatch, not duplicate feature-branch pushes; existing
workflow policies are unchanged.

    python -m pytest -q -rs tests/test_packed_coordinates_pr71.py
    python -m pytest -q -rs
    python -m scripts.run_packed_coordinates_pr71 --out reports/pr71

Report: reports/pr71/run-*/packed_coordinates.result.json.
24 targeted cases, 941 total expected from PR70's 917, 41 PR
workflows expected. Actual local and CI validation pending.
Remaining semantic and census debts are tracked in
docs/rtlprep-backlog.md; no official RTL modification.

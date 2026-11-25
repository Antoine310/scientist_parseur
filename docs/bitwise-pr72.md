# PR72 — Syntactic bitwise influence candidates

## Baseline and semantics

PR71 merged: core flat 1199/531/668/2842
(assignments/supported/partial/edges); arrays 378/245/133/2469;
151 uniquely linked flat-partial rows with new coordinate support.
Minimum combined support 682/1199, 517 without flat support or
a new PR71 link. Standalone ALU flat 479/254/225/477; arrays
130/61/69/21, 28 linked rows. Do not sum core and standalone ALU.

New bitwise_dependencies channel operates only on existing flat-partial
captured assignments. Preserve flat and array graphs verbatim.
For BinaryAnd/Or/Xor/Xnor, take the union of source coordinates at
each corresponding lane. For BitwiseNot, retain the lane's candidates;
for BitwiseAnd/Or/Xor/Nand/Nor/Xnor reductions, union all operand
lanes into the scalar destination. Nested expressions, bounded
concatenations/replications, fixed packed coordinates, elaborated
literal positions and explicitly equal-width conversions are supported
within the validated type/layout/state scope. Differing state domains
are accepted only for operands with no dynamic leaf. No alias guessing,
implicit resizing, dynamic index, arbitrary logical/comparison operator,
mux, function or arithmetic modeling. No inferred guard feasibility,
NBA priority, temporal semantics or cross-module composition.

Each edge says syntactic_influence_candidate, NOT copy, exact Boolean
dependence or actual sensitivity. Example a & 0 retains a's syntactic
candidate edges even though simulation always gives zero. Repeated
source coordinates are deduplicated within a target lane; cancellation
is not inferred. Constant target positions indicate no runtime RHS leaf,
not a computed value. Preserve fixed multidimensional coordinates;
never invent flattened bit indices.

Existing captured assignment ordinals link the new channel to flat
rows. Preserve procedural metadata. Explicit bounded scan, expression
depth, node/width/row/pair and shared edge/constant-position limits;
reject rows atomically when unsupported. Report truncations under
analysis_limits. Eleven analyzers for new graphs; stored legacy graphs
without the new channel remain readable. Historical PR69/70/71 policy
comparisons explicitly disable the new analyzer.

## Validation

32 unit cases, including all four binary operators and six reductions,
nested inversion, masking/cancellation, constants, replication,
negative types/layouts/indices/timing/operators, budget visibility,
unchanged flat and coordinate graph, and legacy artifact compatibility.
Historical analyzer-count assertions change from ten to eleven;
historical semantic checks remain intact.

Real slang fixture: 7 assignments, 48 exact candidate edges,
256 exhaustive two-state input pairs and 1792 output checks with
Verilator/cocotb. Includes fixed packed words and a masked output
which is always zero despite candidate edges. Not a four-state or
functional influence proof.

Same AST/index comparison with enable_bitwise=False/True on pinned ALU
and whole core. Verify exact PR71 counts, previous graph identity,
unique flat assignment links and candidate edge consistency. Source-
derived oracle from cv32e40p_alu.sv line 889:
div_op_a_signed = operand_a_i[31] & div_signed.
Require exactly the two corresponding source coordinates in both
ALU contexts. Require additional unique supported rows and no new
truncation. Deduplicate against PR71 linked support; count candidates
separately from position-copy edges. Minimum combined representation
support is NOT full RTL coverage or proven influence.

Run:
    python -m pytest -q -rs tests/test_bitwise_pr72.py
    python -m pytest -q -rs
    python -m scripts.run_bitwise_pr72 --out reports/pr72

Only share the compact summary, not the full detailed report:
    cat "$(ls -td reports/pr72/run-*/ | head -n 1)summary.json"

Full bitwise.result.json remains in the run directory and CI artifact.
Expected 32 targeted / 973 total tests and 42 PR workflows. Actual
local/CI results pending. No official RTL changes. See backlog v1.6.

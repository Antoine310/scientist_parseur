# PR74 — Bounded dynamic index candidates

## Baseline

PR72 merged (977 local tests, 42/42 CI), PR73 merged (43/43 CI).
Verified PR73 CI artifact 15042130934, run 45652297684,
head 2e00299: core flat 1199/531/668/2842; arrays
378/245/133/2469; bitwise 66/24/42/375; mux 165/39/126/2030.
Minimum combined linked support 745/1199, 454 without linked
support. PR73 adds 39 unique rows, 1184 data candidates,
846 control candidates, 28 branch-constant positions. ALU alone
318/479; do not add standalone ALU to whole core.

## Scope

A separate dynamic_dependencies channel handles previously captured
flat-partial assignments with one runtime ElementSelect at either
root (read or write), including fixed outer or final selections.
Validate declaration identity and explicit packed/unpacked logic/bit
dimensions and the result type at every selection. Accept only direct
same-width same-state copies or literal-only RHS chains with proven
destination width. No dynamic casts or other assignment operators.

For a proven plain unsigned scalar/vector selector (up to 32 bits),
enumerate the intersection of the declared nonnegative dimension
and the numeric range of its type. Use existing bounded bitwise
expression rules to identify selector leaves; require actual resolved
runtime leaves, never trust a folded constant tag alone. A candidate
value is not necessarily reachable. Keep distinct alternatives per
numeric selector value; source/target unpacked indices, outer packed
indices and final bit remain separate. For each alternative emit
data candidates for corresponding lanes and control candidates from
selector leaves to destination lanes. A constant write has
alternative-local constant positions, no value assertion. Preserve
guard/event/NBA metadata, not final writer or priority semantics.
Explicit numeric out-of-range and unknown-state possibility flags
describe type/domain, not observed reachability. Do not model the
behavior of invalid/unknown reads or writes.

Reject signed/enum/alias indices, unsupported layout, indexed
part-selects, multiple runtime indices, dynamic selections under
other operators or conversions, aggregate copies and unsupported
contexts. Remaining CSR index enum resolution and ff_one constant
selector arithmetic are separate tasks. Existing row/edge/coordinate
caps and explicit choice/node/pair budgets; atomic rejection with
truncation reported. No claim of exact functional influence or
RTL coverage. Previous channels unchanged; historical policy
comparisons disable the new channel. Fresh graph has 13 analyzers.
Legacy stored graphs remain readable. Test discovery is explicitly
restricted to tests/, not user-local upstream repositories.

## Validation

30 unit cases expected: exact read/write word coordinates for
packed/unpacked, dynamic bit in fixed word, literal write, unsigned
domain bounds, nonzero/ascending dimensions, unsupported cases,
identity, budgets and legacy graph compatibility.

Real slang fixture: 5 assignments, 20 alternatives, 52 data and
136 control candidates, 16 alternative-local constant positions.
1024 two-state input vectors (256 patterns x 4 indices), 5120 output
checks with Verilator/cocotb; not exhaustive over all possible
packed input words or a four-state proof.

Same AST and index comparison on official ALU/core, exact historical
counts and old graph identity, unique flat assignment IDs and
per-alternative coordinate integrity. Deduplicate against linked
PR71/72/73 support. Report compact counts separately from detailed
candidates. Core FIFO source-derived oracle:
cv32e40p_fifo.sv line 77, mem_n[write_pointer_q] = data_i,
default core FIFO has two 32-bit words. Require indices 0,1,
64 data and 64 control candidates, exactly matching source and
destination bit coordinates and pointer [0]. No claim that both
writes occur simultaneously, or that push guards are feasible.
Require at least this new linked row and zero truncation on official
ALU/core; standalone ALU need not gain support in this scope.
Independent frozen prior annotations retained.

    python -m pytest -q -rs tests/test_dynamic_pr74.py
    python -m pytest -q -rs tests/
    python -m scripts.run_dynamic_pr74 --out reports/pr74

Share only the compact summary:
    cat "$(ls -td reports/pr74/run-*/ | head -n 1)summary.json"

Detailed dynamic.result.json retained with CI artifact.
Expected 30 targeted / 1040 total tests and 44 PR workflows.
Actual local and CI validation pending, no official RTL changes.

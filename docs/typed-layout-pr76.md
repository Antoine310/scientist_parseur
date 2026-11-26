# PR76 — Package typedef and enum layout candidates

## Measured baseline

PR75 merged at c6e4cc03a796e920753a7ed42038b460d8b6b1be,
1074 local tests and 45/45 CI. Core minimum linked support 809/1199,
390 without linked support; standalone ALU 381/479. All 63 constant
selector residuals recovered with 527 candidates and one constant.
The archived PR75 core AST (artifact 15101889262, run 45787214945)
exposes six remaining PR74 layout residuals.

## Scope and proof rules

Use only named packages directly present in the elaborated root or
compilation units. Resolve exact address + package-qualified name
tokens of TypeAlias and EnumType declarations; validate uniqueness
and bounded alias chains. Enum base types must be explicit unsigned
logic/bit scalars or vectors. Other aliases may use explicit fixed
logic/bit layouts. No name-only fallback, signed/opaque types, local
or anonymous types, struct/union parsing, or enum value-set proof.

A resolved signal must agree with the original type string in the
structural index and its declaration identity. A local package
parameter used as an index must match its declaration address,
name, type and known nonnegative value; check any folded constant
tag rather than using the tag as proof. Refuse ambiguous inventory,
unproven layouts and unsupported expressions.

Private assignment rewriting retains only canonical layouts for
proven type tokens and integer literals for proven package constants.
Reuse PR74 coordinate and runtime selector validation. The separate
typed_layout channel is restricted to flat-partial rows refused by
PR74 for unproven_declared_layout or unproven_packed_layout.
Produce fixed-position candidates or numeric-index alternatives,
with data and control roles, preserving coordinate dimensions and
procedural metadata. Persist proof paths, qualified names and layouts,
never type addresses in new proofs. Previous channels unchanged.
Bound package/type inventories, traversal, proofs and edges; atomic
rejection. Fresh graphs have 15 analyzer reports, older graphs remain
readable; disable this pass in historical policy comparisons.

## Validation

32 targeted cases expected: exact tokens, alias chains, enum base,
cycles and duplicate declarations, package constant identity, fixed
and dynamic coordinates, unsupported types and atomic budgets.

Real slang fixture: one fixed enum bit, one read and one write indexed
by a two-bit enum slice. 3 rows, 1 fixed + 32 data + 64 control
candidates = 97. Verilator/cocotb 1024 two-state input patterns,
3072 checks (not exhaustive over all input words or four-state logic).

Independent official RTL oracle from pinned CV32E40P commit
b353438ff469c030c89f6804f3b24a2852880e8b:

* controller lines 1544–1546: debug_fsm_cs[0/1/2] to three scalar
  debug outputs, exact package constants and debug_state_e base.
* CSR lines 549,583,1405: csr_addr_i[4:0] selects one of 32
  words, 32 output/write lanes per alternative. Verify 3072 data
  and 15360 control candidates, exact coordinate sets and selector
  sources, csr_num_e base logic[11:0]. These are numeric alternatives,
  not proof of feasible CSR addresses, guards or simultaneous writes.

Expected six newly linked rows, 18435 candidates (3 fixed and
18432 conditional), zero overlap and truncation, unchanged earlier
graphs on the same AST/index, minimum combined 815/1199. Standalone
ALU remains 381/479. Actual results pending. Large increase in candidate
count reflects explicit alternatives; compact representation is future
work. No inference of whole-design coverage, functional influence or
formal proof. No official RTL changes.

    python -m pytest -q -rs tests/test_typed_layout_pr76.py
    python -m pytest -q -rs tests/
    python -m scripts.run_typed_layout_pr76 --out reports/pr76

Share only the compact summary:
    cat "$(ls -td reports/pr76/run-*/ | head -n 1)summary.json"

Detailed typed_layout.result.json retained with CI artifact.
Expected 1106 total tests and 46 workflows.
Structures/unions and LHS concatenation remain a separate PR77
proposal in backlog v1.10, arithmetic PR78.

# PR69 — Conservative bit-width conversion candidates

First part of PR61-BIT-02 / PR39-WIDTH-01 / PR64-CAST-01.
Do not equate all 310 historical width-related partial rows (or 320
including unsized literals and unknown width) with recoverable rows.

## Semantics and boundaries

Only already-captured assignment rows passing the existing strict AST
position gate are eligible. New support is limited to explicit
Conversion nodes whose integral input and output types have recognized
descending packed or predefined integer layouts, and compatible state
domains. No implicit resizing inferred just because assignment widths
differ. Preserve the previous equal-width path and legacy schema.
The new parser recognizes explicit scalar/packed logic, bit, reg,
and predefined integer atom types with signedness, as in slang v12.1.
Reject ascending, multidimensional, aliases, excessive widths and
ambiguous layouts.

Slang v12.1 ConversionExpression::serializeTo writes the operand but
not ConversionKind. Its convert method distinguishes Propagated
conversions (destination signedness) from others (source signedness).
For widening, require source and destination signedness to agree.
For narrowing, retain the least significant positions. Zero extension
adds constant target positions without runtime source; sign extension
repeats the source MSB. No four-state/two-state conversion added.
Signedness changes while widening, state conversion, unresolved
operand layouts, unsupported operators and unsized literals stay
partial. See upstream v12.1 source/ast/expressions/ConversionExpression.cpp
and source/ast/types/AllTypes.cpp for the exact serializer and types.

New conversion_view selection describes a slice or repeat relative to
the original segment's LSB, with base width retained. The bit graph
validates the original selection and declared width before expanding,
and refuses malformed, overlapping or out-of-range mappings atomically.
The existing segment/width/edge limits remain; no arbitrary flattening.
Bit positions are candidates, not equality of values or global
functional influence. Constant target positions do not encode literal
values. Signed extension uses repeated source positions, not invented
independent sources. Existing transforms stay explicit.

## Evidence

Synthetic AST unit oracles: typed shape, nonzero lower bounds,
zero/sign extension and truncation, ambiguous signedness/state/alias
rejection, segment cap and source view validation. Real slang fixture
with independent expected 24 bit edges, four constant target positions
and exhaustive 256 pairs of 8-bit input patterns (three checked outputs,
768 checks) with Verilator/cocotb. This is two-state simulation, not
four-state validation or a formal proof.

Rerun the pinned ALU and 24-instance core through PR67, preserve
PR56 annotations and PR65 labels/paths. Rebuild legacy and current
graphs on the identical AST and index using enable_width_conversions
False/True. Require exact legacy counts, unchanged non-target graph,
unchanged prior supported assignment records and their edges, same
assignment identities/denominator, no new bit graph truncation; every
recovered row must carry explicit conversion evidence. Report actual
recovered rows, modes, reasons and remaining partial reasons. Require
at least one recovered core row. Historical PR67/68 runners now require
the historical minimum counts rather than exact current supported
counts, while this PR retains the exact legacy baseline gate; no old
frozen labels changed.

    python -m pytest -q -rs tests/test_bit_width_pr69.py
    python -m pytest -q -rs
    python -m scripts.run_bit_width_pr69 --out reports/pr69

Report: reports/pr69/run-*/bit_width.result.json.
24 new unit cases, 880 total expected from 856 baseline. Actual local
and CI validation pending; no number of recovered official assignments
claimed yet. PR69 stacked on PR68 while its CI is pending; retarget
after PR68 is merged, then verify checks. Keep remaining width debts
open and revisit after measuring.

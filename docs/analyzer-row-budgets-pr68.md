# PR68 — Targeted analyzer row budgets

## Evidence and policy

PR67 measured two row caps in the pinned CV32E40P core: expressions
2000 (1803 cap-check hits, not a count of omitted eligible assignments)
and complex_constructs 2000 (38102 visited, 41 pending at stop).
The 732 partial bit assignments are a separate issue.

Change only the two default row limits to 4096. The optional
AnalysisBudget(expression_rows=..., complex_rows=...) fields accept
integers 1..8192; None uses the corresponding analyzer default.
Direct analyzer calls also accept row_limit. No global mutation,
no environment-variable override. The effective limit is recorded
in each payload and in analysis_limits.analyzers.*.configured_limits.
Archived PR67 reports retain their original settings; do not infer
historical effective limits by re-summarizing old payloads without
the new row_limit field.

Keep the complex traversal cap 50000, depth cap 48, per-record
argument/reference caps, all expression tree caps, global AST
and graph gates and all other analyzers unchanged. Coverage findings
still have their independent display cap. Reaching a row cap is a
conservative stop condition (not a count of omitted eligible rows).
A different cap may become visible on continuing traversal; record
it explicitly rather than silently increasing it.

The PR55 fresh worker now reads ASTs through read_ast before index
construction. This adds the existing byte/depth/value admission
checks to that path. It does not provide an OS memory, CPU or disk
quota; the slang subprocess and intermediate graph allocation are
not bounded by the JSON publication gate.

## Evaluation

Regenerate PR67 diagnostics with the same official commit, core
configuration and standalone ALU. Keep the frozen PR56 annotations,
PR65 direct labels and paths, official source verification and bit
baseline. Reuse exactly the same elaborated AST for each policy
comparison, with fresh Linux workers, separate AST SHA-256 checks,
one sample per policy/design. Record AST read, index, graph,
serialization and total time excluding slang; peak Python RSS and
serialized graph size. Measurements are descriptive, not a stable
performance distribution.

Require exact equality of non-target graph fields and all other
analyzer reports; verify a multiset inclusion of old target rows
(including duplicates) and the original complex traversal prefix.
ALU must retain the original 479/254/225/477 bit counts; core
1199/467/732/2842. The legacy core policy must reproduce both row
cap hits; the expanded policy must add rows and not hit either row
cap. ALU must not add rows. Record all residual analyzer truncation
and the independent coverage finding truncation. A passed comparison
means the targeted row caps are removed, not necessarily all
truncations: the result separately reports all_analyzer_truncations_removed.
If a new traversal/depth/nested cap appears, inspect evidence before
changing that policy.

## Reproduce

    python -m pytest -q -rs tests/test_analyzer_row_budgets_pr68.py
    python -m pytest -q -rs
    python -m scripts.run_analyzer_row_budgets_pr68 --out reports/pr68

Output: reports/pr68/run-*/row_budgets.result.json, plus reference
diagnostics and per-design/per-policy graph and measurement files.
Do not overwrite the PR67 historical artifacts.

23 new unit cases; 855 total expected (832 prior expected).
Local and CI validation pending. No new RTL, semantic bit support,
simulation or formal proof; no design-coverage claim.

Backlog PR65-LIMIT-01, PR62-LIMIT-01/02, PR68-ROW-01, PR68-AST-01.
The register records the PR65–67 merges and actual PR67 results.
PR69 will address width/cast cases only after budget validation;
all 732 core partial bit rows remain a tracked baseline.

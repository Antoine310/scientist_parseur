# PR47 — local NBA order and real RAS priority

The sequential analyzer rejects nonpositive, duplicate or decreasing
execution-order metadata instead of inventing a last write. Gaps are
allowed because other targets may be written between two writes to q.

A separate RTLPrep-owned fixture tests full-width NBA writes in one always_ff:
the later enabled write wins, neither enabled retains state. Real slang
extracts the paths and Verilator checks 64 clocked vectors. This is not
a claim of cross-process ordering, partial-lane overlap or formal proof.

CVA6 RAS has a single NBA state commit; its next-state priorities are
blocking assignments in always_comb, NOT competing NBAs. Two isolated
copies of the verified upstream RAS disable the simultaneous push/pop
override or suppress flush during push. The directed oracle requires
exact counterexample text and one passing unaffected scenario in each
mutant. Compile failure cannot count. No upstream files are edited.

Reproduce in the activated environment:
    python -m pytest -q tests/test_nba_priority_pr47.py tests/test_sequential_candidates.py
    python -m scripts.run_priority_pr47 --source-root upstream_cva6 --out reports/pr47

The runner emits priority.result.json, static graph and actual xUnit files.
No global design coverage or formal proof. Results pending CI.
A separate follow-up should add a non-destructive pinned external RTL
checkout installer, covering all integration-test dependencies; no change
to the existing installer in this PR.

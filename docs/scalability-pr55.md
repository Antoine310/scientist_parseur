# PR55 — reproducible scaling baseline (Linux)

This benchmark complements the existing Phase G query/context benchmark:
it measures real slang elaboration and RTLPrep extraction, not agent
accuracy or token savings. It does not optimize the engine or claim
processor-wide scalability yet.

## Workloads

The generated RTL instantiates a chain of identical 8-bit permutation
and register stages at 8, 64, 256 and 520 instances (plus top).
For each stage an independent oracle requires exact instance identity,
five observed signal links, and eight reviewed bit positions. Signal
links are a required subset, not a proof that every emitted edge is
correct. All emitted bit positions must match the oracle without
duplicates; missing positions are rejected unless truncation is
explicit. The 520-stage case deliberately exceeds the 512-process
register_flow budget: the truncation must be reported. Passing the
benchmark is not the same as complete analysis.

The real case uses the official pinned CV32E40P ALU with its four
dependency files (package, popcount, first-one and divider). The
existing fixture lock and checkout verification are reused before and
after measurements; no upstream files are modified. The ALU case is a
measurement of real RTL, not a complete CPU or a new independent
functional oracle.

## Methodology

Fresh Python worker per sample; default three repetitions per case
(two in CI). The worker calls the existing analyze function (slang,
JSON summary) then loads AST, builds index, builds dependency graph
and serializes index/graph. This deliberately separates the phases
instead of timing the deps CLI with repeated AST reads. Report
slang subprocess elapsed time separately; it is included in
analyze_including_summary and must not be added twice.

Linux resource.ru_maxrss records separate peak RSS for the Python
worker and slang child, in KiB. These are process high-water marks,
not per-phase allocation or a combined simultaneous peak. The worker
peak is sampled before running the independent oracle. The pipeline
wall time excludes the oracle, worker launch and source preparation.
No cache flushing, CPU pinning, or performance pass threshold is
imposed; timeouts are operational bounds only. Report min/median/max
of raw samples; compare on the same hardware and software versions.
Semantic counters and source fingerprints must agree across repeats.
The path-dependent source fingerprint is only comparable within a run;
source SHA-256 enables comparison across runs. Report tracks revision,
tracked dirty state, Python, slang, OS and CPU model/count.

Every sample retains AST, index, graph and analysis logs locally.
CI uploads the summaries, manifests, generated source and logs, not
all large JSON artifacts. New run directories avoid overwriting
previous reports. Report analyzer counters and truncation flags
without interpreting them as percentages of design coverage.

## Reproduce

    python scripts/rtlprep_env.py --check-rtl-fixtures
    python -m pytest -q -rs tests/test_scalability_pr55.py
    python -m scripts.run_scalability_pr55 --out reports/pr55

Optional smaller smoke run:

    python -m scripts.run_scalability_pr55 --out reports/pr55-smoke --sizes 8 64 --repetitions 1 --synthetic-only

Main report path is printed at completion:
reports/pr55/run-*/scalability.result.json.
Do not treat an incomplete or failed report as a benchmark pass.
Actual performance measurements and regression CI remain to be run.

## Limits and follow-ups

No speedup claim, functional proof, simulation, or whole-CPU capacity
claim. No new MCP API. This baseline is intended to guide subsequent
profiling/optimization, independently annotated precision/recall
evaluation, and larger real CPU hierarchy evaluation.

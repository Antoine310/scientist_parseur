# PR63 — CV32E40P multi-unit evaluation

## Scope

Evaluate six separately elaborated cases on the official CV32E40P commit
b353438ff469c030c89f6804f3b24a2852880e8b. No RTLPrep semantic engine
changes. This is not yet an integrated processor or execution-stage
elaboration.

| Case | Configuration |
| --- | --- |
| ALU | Same five official files and defaults as PR61/62 |
| Compressed decoder | Official module defaults |
| Instruction decoder | Official defaults, including COREV_PULP=1, FPU=0 |
| Register file | Official FF implementation with wrapper ADDR_WIDTH=6, DATA_WIDTH=32, FPU=0, ZFINX=0 |
| Multiplier | Official module |
| Controller | Official defaults, COREV_CLUSTER=0, COREV_PULP=0, FPU=0 |

The register file has 32 integer entries, including x0, in the selected
configuration. The standalone controller and decoder are not claimed
to share a coordinated whole-core configuration; that is future work.

## Reproducibility and source safety

Keep the original fixture lock untouched. PR63 adds six explicit blob
pins (decoder, register file FF, multiplier, controller, APU and FPU
packages) in scripts/cv32e40p_pr63.py. Verify the existing official
checkout, then read the twelve pinned blobs from the immutable Git tree
into a fresh run-local snapshot. Verify the commit tree and SHA-1 blob
bytes before use, then verify snapshot bytes and official checkout after
the run. No sparse-checkout changes, fetch, checkout or source edits.
The existing fixture installer fetches the pinned commit without a
blob filter; if a local partial clone lacks an object, materialization
fails rather than fetching silently. The generated wrapper is a
separate local test source with its own SHA-256. Source fingerprints
include absolute paths, so snapshots in new run directories naturally
have different fingerprints from PR61; compare source blob pins and
configurations rather than expecting identical fingerprints.

## Evidence

- Retain the ALU frozen PR56 signal and bit scores and PR61/62 baseline
  (479 assignments, 254 supported, 225 partial, 477 bit edges).
- 37 new manually source-derived labelled direct signal candidates:
  27 positive, 10 negative. Provenance file per case and line/note per
  label. These are development annotations selected before execution,
  not a blinded corpus, not independently human-reviewed, and not
  statistically representative. Score positive/negative candidates,
  retain per-label findings and unlabelled predictions. No inference
  of functional influence from syntactic links.
- New cases verify exact instance paths, selected top port directions,
  graph endpoint integrity and nonempty edges. Register-file wrapper
  checks 6-bit address, 32-bit data and 32x32 packed integer storage.
- Report all ten analyzer budgets, partial reasons, warnings and
  truncation flags per case. New unit label misses remain visible;
  they do not cause the evaluation itself to fail. Only the ALU frozen
  regression is a strict score gate. A passed run means six analyses
  executed and structural checks passed, not that every prediction is
  correct. No new bit labels for the five new cases and no new
  simulation or formal proof.

## Reproduce

    python -m pytest -q -rs tests/test_cv32e40p_multi_unit_pr63.py
    python -m pytest -q -rs
    python -m scripts.run_cv32e40p_multi_unit_pr63 --out reports/pr63

Report: reports/pr63/run-*/multi_unit.result.json.
The report starts incomplete, records each completed case, and records
failure explicitly if an exception occurs. Per-case manifests, ASTs,
indices and graphs remain in the fresh local run directory.
The CI installs the existing pinned fixtures and pinned slang.
14 unit tests and six real case evaluations are planned; actual
measurements and CI remain pending.

Next: use the observed limitations to prepare an integrated execution
subtree with a coordinated configuration and independently annotated
cross-instance port relationships. Do not extrapolate these standalone
unit results to whole-core coverage.

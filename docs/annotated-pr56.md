# PR56 — source-derived dependency evaluation baseline

## Purpose

Freeze a small, explicitly annotated candidate universe independently
of the extraction algorithm. This is a pilot corpus, NOT a representative
whole-CPU benchmark or a blinded external evaluation. The labels were
prepared by the implementation assistant from the source statements,
without extracting the predictions to generate the labels. A second
human reviewer and a larger independently sampled test corpus are
needed before publication-level accuracy claims.

The corpus in benchmarks/annotations/pr56.json contains 207 candidate
relations. The fixture has 19 signal and 40 bit labels; the pinned
official CV32E40P ALU has 17 signal and 131 bit labels. Each label has a
positive, negative or unknown class, a source line and a rationale.
Source blob identities are checked; official source files are verified
against the existing fixture lock before and after the run.

## What is scored

Signal keys: source, target, edge kind, sequential flag.
Bit keys: source, source bit, target, target bit. These are
assignment-local fixed positional candidates, not value equivalence
or a test of transforms. A direct read is not transitive influence.
A negative label is an explicitly annotated absent direct relation,
not a relation assumed absent because the extractor omitted it.

TP: labelled positive predicted. FN: labelled positive not predicted.
FP: labelled negative predicted. TN: labelled negative not predicted.
Precision = TP/(TP+FP); recall = TP/(TP+FN);
F1 = 2TP/(2TP+FP+FN). Undefined denominators produce JSON null.
A missing positive is an FN in this retrieval task even if extraction
was incomplete or conservatively abstained. Unknown-labelled
relations and unlabelled predictions are reported separately; neither
is silently counted as correct or incorrect. Duplicate prediction
records are counted separately from unique predicted keys.

The ALU includes generated reverse-bit permutations: these are
deliberate opportunities to detect missed positions, not success
thresholds. The fixture includes an unresolved function call and
dynamic selection. No minimum metric is imposed in this first
baseline; a passed run means extraction and scoring completed.
Per-relation findings permit manual inspection of all results.
Do not pool across signal/bit channels or extrapolate to a whole core.
No formal proof or design coverage is claimed.

## Reproduction

    python scripts/rtlprep_env.py --check-rtl-fixtures
    python -m pytest -q -rs tests/test_annotated_pr56.py
    python -m scripts.run_annotated_pr56 --out reports/pr56

Report: reports/pr56/run-*/evaluation.result.json.
Each case retains signal.findings.json, bit.findings.json, the graph
and source manifest. New run directories preserve previous evidence.
The report includes the annotation SHA-256 and the source fingerprints.
Actual benchmark scores and CI remain to be validated.

## Next steps

Review the corpus with a second annotator; add stratified direct signal
and bit samples for function returns, bounded loops, array indices,
port mappings, NBA guards and unsupported constructs. Keep a frozen
holdout separate from the development cases used to fix missed edges.
Then scale the reference protocol to the decoder, register file,
execution hierarchy and eventually the complete elaborated CV32E40P.
For functional/security properties, use independently specified
formal or simulation evidence, not syntactic metrics alone.

# PR48 — reset, enable and real RAS formal properties

Two proof harnesses are deliberately separate. The small fixture checks
reset/enable/hold against an independent register model. The real RAS
harness elaborates the exact verified CVA6 sources with Yosys read_slang,
depth two, RV32 configuration. The formal-only wrapper exposes both packed
entries for an inductive invariant, without changing upstream RTL.
The separate property module uses the native Yosys formal frontend.

The RAS reference uses an independent two-entry model with reset, flush,
push, pop, simultaneous push/pop and hold. Assertions compare both entries
and the observable top. Initial reset is assumed; after initialization,
controls, data and clock/reset events remain unconstrained in the formal
model. Cover tasks require witnesses of nontrivial states. The negative
control uses the isolated PR47 flush-priority mutant and requires SBY FAIL
with an actual VCD counterexample (not a tool error).
No physical reset timing, metastability, X/Z behavior, global design coverage
or full CPU proof is claimed. Proof means successful SBY prove mode, not
a finite BMC pass; a cover witness is a distinct result.

Run with activated EDA tools and pinned upstream checkout:
    python -m pytest -q tests/test_reset_formal_pr48.py
    python -m scripts.run_reset_formal_pr48 --source-root upstream_cva6 --out reports/pr48

Requires Yosys with read_slang (built in or plugin), SBY and Z3. CI installs
the locked OSS CAD Suite release. Reports include distinct task statuses,
source hashes, logs and VCD witnesses. Results pending CI/local verification.
The existing approved formal suites are not broadened to arbitrary inputs.

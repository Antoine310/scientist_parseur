# Reproducible external RTL fixtures (issue #49)

The external RTL installer is separate from the EDA toolchain installer.
Its lock records the four repositories and fifteen exact source blobs
used by the existing pinned CVA6, CV32E40P and third-party RTL workflows.
The nine previously skipped pytest cases depend on three of these files:
axis_register.v, priority_encoder.v and rxuart.v.

From the repository root:

    python scripts/rtlprep_env.py --check-rtl-fixtures
    python scripts/rtlprep_env.py --install-rtl-fixtures
    python scripts/rtlprep_env.py --check-rtl-fixtures
    python -m pytest -q -rs

The check is offline/read-only. The install only fetches missing repositories,
at exact reviewed commits, with sparse checkout of the listed files. It stages
and verifies each new checkout before publishing it; repeated runs verify
existing checkouts without fetching again. It does not install tools or
Python packages; activate the existing slang/EDA environment for tests.

An existing repository with another revision, origin, dirty state, symlink,
or missing pinned file is refused before any installation. No reset, clean,
checkout, sparse-checkout change, or deletion is performed on existing
repositories. For a clean checkout already at the correct revision but
missing a sparse path, review the displayed paths and explicitly add them
yourself using git sparse-checkout add, then rerun the check. If another
revision or dirty checkout is present, preserve it separately rather than
resetting it. New checkouts are installed individually, not as a global
atomic transaction; rerunning after a network failure is supported.

CI installs the real repositories, verifies the pins, repeats installation,
and requires zero skipped cases in the four relevant test files. The
original skip guards remain intact for users without external fixtures.
Actual results pending CI and local validation. This lock is not a promise
to include all future optional RTL dependencies; update pins with reviewed
changes when adding new external modules.

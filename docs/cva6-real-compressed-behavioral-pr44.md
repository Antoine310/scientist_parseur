# PR44 — multi-family CVA6 compressed decoder oracle

Pinned CVA6 commit 742dc82a0c706e0a3bfb98b709fd3ee06d50d12a,
configuration cv32a6_imac_sv32, same verified five source blobs and wrapper as PR43.
Reference: RISC-V unprivileged ISA, C extension, CI/CIW/CL/CS formats:
https://docs.riscv.org/reference/isa/unpriv/c-st-ext.html

| Family | Lower halfwords | Ordinary | Other |
|---|---:|---:|---|
| ADDI | 2048 | 1953 | 94 HINT, 1 NOP |
| ADDI4SPN | 2048 | 2040 | 8 reserved |
| LW | 2048 | 2048 | 0 |
| SW | 2048 | 2048 | 0 |

Gold runs 8192 lower halfwords with upper zero plus 1024 seeded upper-halfword samples.
HINT expansion is an implementation policy check. Reserved ADDI4SPN checks
flags only, not the undefined instruction result. Tests use a two-state simulator.
No global design coverage, formal proof or analyzer accuracy is claimed.

Independent bit mapping annotations for future PR45 (conditional on family):
- ADDI: input 12 -> output 31:25 (sign); input 6:2 -> output 24:20;
  input 11:7 -> output 19:15 and 11:7.
- ADDI4SPN: input 10:7 -> output 29:26; input 12:11 -> output 25:24;
  input 5 -> output 23; input 6 -> output 22.
- LW: input 5 -> output 26; input 12:10 -> output 25:23; input 6 -> output 22.
- SW: input 5 -> output 26; input 12 -> output 25;
  input 11:10 -> output 11:10; input 6 -> output 9.
These are ISA-format reference annotations, not measured RTLPrep relations.

Each isolated mutant must fail exactly one family on a valid instruction with
the exact expected XOR, while the other three family tests pass. Compilation
failure or missing XML does not count as detection.

Reproduction in the activated RTLPrep environment:

    python -m pytest -q tests/test_cva6_compressed_pr44.py
    python -m scripts.run_cva6_compressed_oracle --source-root upstream_cva6 --out reports/pr44-gold --variant gold
    for family in addi addi4spn lw sw; do
      python -m scripts.run_cva6_compressed_oracle --source-root upstream_cva6 --out "reports/pr44-$family" --variant "$family"
      test "$?" -eq 2 || break
    done

Gold exit 0; detected mutant exit 2; other failure exit 1. JSON and xUnit
are emitted in each output directory. Negative runs stop a family at first
failure, so their planned vector counts are not completed counts.
Results are pending CI and local reproduction at the time of writing.

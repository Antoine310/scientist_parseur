# Constant increments — local binary model

Artifact CI #97 15184969853 : 32 CSR rows at line 1387 and one prefetch address at line 138 in residual report; AST group inspection (not a substitute for exact replay identity). CSR packed word [63:0] with lexical generate index, Add + Conversion of int literal 1. Address {trans_addr_q[31:2], 2'b0} + Conversion of 32'd4. PR98 supports direct unsigned same-state signal + proven literal 1 (1–64 bits), or 32-bit aligned low-two-zero concat + literal 4, using PR97 exact endpoint and lexical proof. Single literal or one conversion, value recomputed and tag checked, no arbitrary constant tag, dynamic selection or general composition. Same captured residual IDs and same AST/index; continuous/AlwaysComb blocking only. Binary defined inputs, no X/Z, no global proof, priority or temporal semantics.

Counter model has 2080 possible pairs per 64-bit word, compact 128 coordinates. Address model 465 possible pairs, 62 coordinates, two constant low result bits. Frozen coordinate oracle for 32 CSR words and one prefetch address expects 67025 pairs,4158 coordinates; exact disjoint union with #97 31 popcnt IDs gives all 64 Add roots in core, 31 ALU. No historical graph promotion; these are candidate records, not coverage of whole RTL. Real support is an expectation pending validation.

Python exhaustive widths1–4; negative cases exact reason; fixture slang + Verilator/cocotb 32 checks of 4/64-bit increment and aligned address wrap. Z3 independent binary models 4/64/32 bits:100 UNSAT noninterference,1 UNSAT alignment-zero,2555 SAT pair witnesses,3 SAT carry-free mutant; 2659 queries. Proof of abstract arithmetic only, not RTL equivalence or actual CPU behavior. No upstream modification. Existing workflow jobs reused. No arbitrary command execution.

```bash
python -m pytest -q tests/test_constant_increments_pr98.py
python -m pytest -q
python -m scripts.run_constant_increments_pr98 --out reports/pr98
python -m scripts.prove_constant_increments_pr98 --out reports/pr98-formal
```

## Correctif fixture
Correctif après validation locale initiale bc1dfc3 : 20/20 ciblés 0,10 s, 1524/1524 suite 6,65 s, Z3 2659/2659 (run-ibiaq9b8), mais reports/pr98/run-wy9h2wud/summary.json failed avant simulation et RTL réel. La fixture initiale a deux incréments de vecteurs entiers sans sélection, hors census historique selon bitaccess.extract/_contains_selection ; seul le concat d'adresse est éligible syntaxiquement. Corriger les deux entrées à 5/65 bits avec sélections [3:0]/[63:0], stimuler leur bit supérieur ignoré ; garder oracle trois résidus et mêmes coordonnées, diagnostiquer les comptes et publier détails/AST/graphe même en échec. Deux tests du gate, 22 ciblés/1526 suite attendue. Aucun changement analyseur ni formel. Ne pas réduire le dénominateur de fixture. La reproduction sur vrai slang reste à valider. Main #97 50/50.

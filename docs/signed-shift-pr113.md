# Décalages arithmétiques à signe conditionnel (#113)

AST archivé #105, artefact15198817914 ; jointure exacte #95/#102 par flat_assignment_id. ALU IDs402..407/core724..729, lignes275/278/284/287/290/293 de cv32e40p_alu.sv : deux demi-mots16 et quatre octets8, chacun `$signed({shift_arithmetic & shift_op_a[MSB], shift_op_a[hi:lo]}) >>> shift_amt_int[lo+m-1:lo]`. Conversion externe vers n bits unsigned logic, intermédiaire signed n+1, m=log2(n), quantité 0..n-1. Aucun opérateur ArithmeticShiftRight nested-only résiduel dans ces deux designs. 

Périmètre exact n=4/8/16, feuilles directes logic quatre états non signées descendantes et sélections simples fixes, identité et layout via #97, type de sélection sérialisé vérifié ; signe AND du véritable MSB et mode scalaire distinct, bit MSB partagé représenté une seule fois comme source. Conversion externe obligatoire vers les n bits de poids faible. Refus des autres formes (signed générique, extensions, amount plus large, overshift, alias, dynamique des indices, constantes, X/Z, effets temporels, contextes non validés). Budget2000 lignes/32768 coordonnées. Par sortie i : données i..n-1, toutes les m commandes de quantité, mode uniquement i>0. Nombre paires n(n+1)/2+n*m+n-1 : 67 (8),215 (16), total698 et154 coordonnées d'endpoints par design. Preuve du modèle local binaire, pas d'inférence de faisabilité des gardes ni de propagation globale. Deux racines logiques #112 distinctes, zéro promotion historique ; union indicative ALU47/98,core88/384 à recalculer.

Fixture2 sites (8 bits, tranche haute4),88 paires/31 coordonnées. Simulation exhaustive 4096 entrées×2 sorties=8192 assertions. 30 tests ciblés attendus,1935 suite, trois designs spécialisés. Z3 469 requêtes : 3 équivalences natives signed vs logique+remplissage UNSAT,157 noninterférences UNSAT,303 sensibilités SAT,6 mutants SAT (zéro-fill et mode ignoré). Modèles n4/8/16, pas preuve RTL. Corpus officiels inchangés, 50 jobs historiques conservés. PR112-SHIFT-SIGNED-01 à fermer seulement dans périmètre réel six sites ; cas génériques et X/Z restent ouverts. Multiplication ensuite (#114), jalon cœur indicatif.

```bash
python -m pytest -q tests/test_signed_shift_pr113.py
python -m pytest -q
python -m scripts.run_signed_shift_pr113 --out reports/pr113
python -m scripts.prove_signed_shift_pr113 --out reports/pr113-formal
```

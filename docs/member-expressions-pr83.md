# PR #83 — Expressions logiques et concaténation de membres

AST officiel #82, artefact 15127347670 : lignes CSR 1104/1105, arbres scalaires LogicalAnd/LogicalNot dont les feuilles sont les membres mie/uie, step, stepie. Six références structurales candidates, pas une relation de copie ni une preuve d'influence fonctionnelle. Ligne 467, concat RHS : les sept positions directes mstatus_q→csr_rdata_int sont déterminées par les largeurs exactes des opérandes, mais 25 bits opaques restent non modélisés. L'affectation reste partielle. Ligne 1223, StructuredAssignmentPattern non bloquant AlwaysFF : inventaire et refus explicite ; traitement temporel séparé.

Oracle fixture deux sites, 3 références logiques/3 positions concat, 2 bits opaques, 32 vecteurs/64 checks ; oracle core 4 sites, 2 supportés/1 partiel avec positions/1 sans positions, 6 références logiques et 7 positions. Le contrat #79 sur l'identité des champs reste conditionnel à l'AST. Aucun ajout aux graphes historiques.

```bash
python -m pytest -q tests/test_member_expressions_pr83.py
python -m pytest -q
python -m scripts.run_member_expressions_pr83 --out reports/pr83
```

Le job #80 conserve toutes les étapes antérieures, référence fraîche réutilisée. Résultats à mesurer.

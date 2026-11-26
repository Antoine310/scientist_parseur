# PR #89 — Constantes et références logiques du moteur

API Python opt-in : `enable_member_combinational=True`. Trois collections séparées : constantes locales quand instruction exécutée, constantes spécifiques à la configuration élaborée (preuve exacte par opérande), références logiques structurelles. Les constantes n'ont pas de source fictive, les références ne sont pas des copies de bits. Types et coordonnées contrôlés, provenance producteur/record/ordinal conservée. 805+3+6=814 records attendus sur 17 occurrences ; les 7 NBA restent hors canal. Les 660 positionnels de #88 restent séparés et compatibles. Une seule collecte fraîche des sept audits lorsque les deux options sont actives. Tests sur fixtures #82/#83/#85 existantes, oracles exacts core, partition CSR 32. Aucun changement des graphes historiques, aucun ajout de couverture globale. Mesure ponctuelle du temps de construction avec deux canaux ; benchmark répété à faire. Liaison indépendante des champs, priorité, reachability, temporalité, multi-config et CLI/MCP restent ouvertes.

```bash
python -m pytest -q tests/test_member_combinational_pr89.py
python -m pytest -q
python -m scripts.run_member_combinational_pr89 --out reports/pr89
```

CI même job partagé, validations antérieures conservées. Résultats à confirmer.

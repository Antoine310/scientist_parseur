# PR #90 — Canal NBA local à l'instruction

API Python opt-in : `enable_member_sequential=True` (défaut False). Deux collections distinctes : RHS échantillonnés lors de l'exécution de l'instruction NBA, constantes RHS. Recontrôle de l'occurrence AST, du contexte AlwaysFF, de l'affectation non bloquante et du pattern struct, résolution exacte de la destination et offsets typés. Partition complète de la cible de cette instruction uniquement. Aucun lien avec un front d'horloge spécifique, reset, garde, faisabilité, priorité, dernier écrivain ou latence de cycle inféré. Pas de preuve de next-state global. Les deux autres canaux restent séparés, collecte unique commune. Oracle core 2 RHS +5 constantes, partition mstatus_q 7 positions ; fixture #84 2+3, partition q 5 positions, anciennes simulations conservées. Unicité des IDs des 1481 records cumulés, graphe historique inchangé, budgets conservés. Pas de preuve indépendante de liaison des champs ni d'influence fonctionnelle. Mesure ponctuelle opt-in trois canaux ; CLI/MCP et benchmark répété restent ouverts.

```bash
python -m pytest -q tests/test_member_sequential_pr90.py
python -m pytest -q
python -m scripts.run_member_sequential_pr90 --out reports/pr90
```

CI même job partagé, référence fraîche. Résultats à confirmer.

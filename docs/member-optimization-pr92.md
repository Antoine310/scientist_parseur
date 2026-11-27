# PR #92 — Mutualisation locale de la collecte membre

Les sept audits indépendants reconstruisaient les mêmes inventaires et parcouraient l'AST à répétition. Nouveau contexte privé par appel collect_linked : inspect_ast unique, liste bornée des affectations actives, census membre conservant les ordinaux avant filtrage ; types package, observations globales, resolver, layouts index et instances partagés. Tous les prédicats producteurs, preuves et limites de budget sont conservés ; les inventaires local et paramètres restent indépendants. Les tokens observés hors sites actifs restent pris en compte pour l'ambiguïté. Aucun cache inter-appels ni mutation de l'AST/index. Les audits autonomes et collect() restent inchangés. Le chemin shared=False conserve la collecte indépendante #91. Sur ALU sans site, aucun site n'est transmis aux boucles des producteurs, mais les inventaires et validations sont toujours effectués.

Benchmark Linux frais : deux modes avec les trois canaux activés, seule collecte différente. Baseline = indépendante, all_channels = partagée (noms conservés du runner #91, interprétation modifiée explicitement). Alternance 3 paires ALU/core, une paire par fixture #87/#84/#85/#82. Comparer empreintes complètes sur mêmes AST/index, sept rapports exacts, enveloppe et liaison, payloads et provenance, oracles historiques. VmHWM et temps mur/CPU/JSON/sérialisation. Mesure du graphe entier, non profilage individuel ; aucun seuil arbitraire. Résultats à confirmer. Aucun changement sémantique attendu ; identité indépendante des champs, couverture globale, gardes, temporalité, CLI/MCP restent ouverts.

```bash
python -m pytest -q tests/test_member_optimization_pr92.py
python -m pytest -q
python -m scripts.run_member_optimization_pr92 --out reports/pr92 --repeats 3
```

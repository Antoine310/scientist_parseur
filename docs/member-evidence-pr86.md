# PR #86 — Enveloppe commune de preuves membres

Première étape d'intégration, sans modification des graphes historiques. Recalcul des sept audits #79 à #85 sur un seul AST/index. Enveloppe version 1 : métadonnées producteur, payloads intacts, identifiants locaux, catégories distinctes. Conservation des preuves de configuration au niveau des lignes et des coordonnées déclarées/offsets packed sans conversion. Les 56 lignes producteur attendues ne sont pas 56 occurrences ; les 1481 enregistrements ne sont pas des arêtes globales. Reconstruction exacte de chaque rapport comme oracle, budgets et refus de relations inconnues ou candidates orphelines. Aucune déduplication entre producteurs ou preuve d'identité indépendante des champs. SHA256 des fichiers du runner pour identifier l'extraction, pas une identité persistante des occurrences. Fixture #85 réutilisée, toutes simulations des PR antérieures conservées dans CI. Étape suivante : liaison par parcours AST et audit des recouvrements avant promotion.

```bash
python -m pytest -q tests/test_member_evidence_pr86.py
python -m pytest -q
python -m scripts.run_member_evidence_pr86 --out reports/pr86
```

Résultats à mesurer. 50 jobs CI attendus.

# Correction versionnée du filtre de sélection — #103

#102 a mesuré 13 omissions du cœur (7 sous Call.arguments, 5 dans ConditionalOp.conditions, 1 sous StructuredAssignmentPattern.memberSetters), zéro ALU. Artefact [15190879320](https://github.com/Antoine310/scientist_parseur/actions/runs/45985670286/artifacts/15190879320). Tous les sites omis ont une cible NamedValue. Les cinq cibles non supportées du CSR restent distinctes.

Nouveau mode opt-in selection_census_v2 : garde historique inchangée par défaut ; sur un résultat négatif seulement, parcours des conteneurs des opérandes hors métadonnées, borné à 4096 nœuds/64 niveaux par opérande. Échec explicite au budget, pas de résultat négatif inventé. Les lignes nouvelles restent strictement partielles (aucun segment, aucune arête, aucune constante) : le filtre d'admission ne prouve rien sur la sémantique. Pas de changement au pipeline historique, CLI/MCP ni schéma v1 exporté par défaut. Rapport v2 séparé, avec accès et graphe v2 internes, mapping ancien/nouveau par identité AST et instance, projection historique vérifiée ligne par ligne et arête par arête, refus de divergence. ID locaux au même AST (SHA256 + JSON pointer), pas de stabilité inter-élaborations.

Attentes : fixture3 occurrences, historique1/v2 2 ; ALU612/479/479 ; core3811/1199/1212, 13 nouvelles lignes partielles, zéro gain sémantique. Historique #95 et unions #97–101 restent inchangés ; ne pas ajouter les 13 aux 76 candidats caractérisés. Pas de preuve RTL/formelle nouvelle : changement de recensement, non de comportement. Les tests de non-régression et les validations historiques restent en CI. L'intégration versionnée au pipeline public et corpus indépendants restent ouvertes après validation.

```bash
python -m pytest -q tests/test_selection_census_pr103.py
python -m pytest -q
python -m scripts.run_selection_census_pr103 --out reports/pr103
```

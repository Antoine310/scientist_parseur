# PR #95 — Audit scientifique des résidus plats

Périmètre historique figé : ALU 479 lignes, 254 supportées +127 récupérées uniques =381, 98 résiduelles. Cœur 1199, 531+284=815, 384 résiduelles. Aucun ajout des 30 occurrences membres ni des 1481 records. Le dénominateur AST global (612/3811) est distinct.

Recalcul de l'union des six canaux #71–76 avec leurs IDs explicites, vérification des métadonnées et comptes. Replay bit_accesses et bit_dependency_graph sur le même AST/index : égalité des objets JSON ; association de la capture à son ordinal exact via identité objet, pas par rapprochement cible/ligne. Raison détaillée bit_access pour partial_bit_access seulement ; autres raisons plates préservées, refus spécialisés et absence de lien explicite par canal. Opérateurs RHS et racine après Conversion, types et contexte issus de l'affectation capturée. Scan borné et limitation explicite. Histogrammes par raison, racine, instance, module et contexte partitionnent les résidus ; opérateurs imbriqués et motifs de refus peuvent se chevaucher. Un opérateur observé ne signifie pas qu'il cause le refus, ni qu'il est récupérable, ni qu'il influence réellement un bit. Le rapport détaillé contient un enregistrement par ID résiduel et les liens partiels ; le résumé expose les distributions. Aucun changement moteur ou promotion. Entrées et graphe vérifiés inchangés. Pas de mesure de couverture globale, preuve ou simulation nouvelle.

Les chiffres détaillés seront mesurés par la validation. Priorité #96 à choisir sur résultats, puis oracle indépendant et simulation/formel selon domaine.

```bash
python -m pytest -q tests/test_residual_audit_pr95.py
python -m pytest -q
python -m scripts.run_residual_audit_pr95 --out reports/pr95
```

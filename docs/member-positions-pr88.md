# PR #88 — Canal positionnel typé du graphe

API Python opt-in : `build_dependency_graph(ast, expected_top=top, index=index, enable_member_positions=True)`. Nouveau champ `member_position_candidates`, distinct des arêtes signal/bit historiques ; désactivé par défaut. Vérification des positions selon déclarations exactes de l'index et layouts sérialisés, offset de struct, index déclaré, coordonnées packed multidimensionnelles distincts. Le champ indépendant reste non prouvé. Provenance producteur, record, ordinal même AST et source RTL conservés. Les 821 autres records (constantes/logique/NBA) ne sont pas promus. Artefact #87 15144428065 : 660 positions dont 640 PMP, 10 paires signal présentes ; comparaison plate incompatible quand un endpoint est un offset ou une coordonnée multidimensionnelle. Aucun ajout au dénominateur historique. Oracle compare graphe avant/après hors métriques de publication et fingerprint ajouté par pipeline, vérifie chaque coordonnée PMP et la fixture #87. Budget global de publication conservé. Pas de preuve fonctionnelle, de priorité, de temporalité ni de couverture globale. Pas encore de commande CLI/MCP opt-in, coûts des audits à mesurer. 

```bash
python -m pytest -q tests/test_member_positions_pr88.py
python -m pytest -q
python -m scripts.run_member_positions_pr88 --out reports/pr88
```

CI conserve les précédents jobs, référence fraîche partagée. Résultats attendus, non validés.

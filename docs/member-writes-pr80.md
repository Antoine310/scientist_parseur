# PR #80 — Écritures de champs scalaires

PR empilée sur #79 non fusionnée. L'AST #78 montre trois sélections fixes et sept conversions de littéraux binaires vers champs logic scalaires. La preuve reste conditionnée au type sérialisé et à la cohérence des tokens #79 ; aucune preuve de liaison indépendante aux déclarations de champs. Les écritures constantes sont des candidats locaux séparés, pas des arêtes. Pas de traitement des enums constants, gardes, priorités, NBA, conversions générales, Pmp_t multidimensionnel ou unions. Comparaison avec les sept sites historiques #79 sur le même AST, sans modification des graphes ni addition au dénominateur plat. Oracle prévu : 3 arêtes et 7 constantes dans le cœur, 4 sites fixture, 16 vecteurs binaires. Résultats à mesurer.

```bash
python -m pytest -q tests/test_member_writes_pr80.py
python -m pytest -q
python -m scripts.run_packed_members_pr79 --out reports/pr79
python -m scripts.run_member_writes_pr80 --out reports/pr80
```

Valider les deux heads exacts séparément, puis fusionner #79 et retarget #80 vers main, contrôler diff et CI avant fusion #80. Ne pas supprimer la branche #79 avant retarget.

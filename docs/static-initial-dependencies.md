# PR #33 — Sélections statiques et initialisations constantes

## Motivation vérifiée sur RTL externe

La validation épinglée de la PR #32 restait à 2 avertissements pour `priority_encoder` et 2 pour `rxuart`. Les sélections RHS et LHS imposaient systématiquement un avertissement « dépendance au signal entier », même quand leurs bornes étaient prouvées constantes dans l'AST slang. Le récepteur ZipCPU contient aussi des instructions `initial` simples, qui ne doivent pas être transformées en événements d'exécution.

## Interprétation bornée

- Le graphe reste au **niveau signal entier**, sans prétendre fournir des arêtes bit-à-bit.
- Les indices et bornes statiques sont enregistrés dans `static_selections`, avec rôle `read` ou `write`, identité du signal, sélection `bit`/`range` et source éventuelle.
- Les indices statiques sont reconnus seulement si les sous-expressions sont indépendantes des signaux à l'exécution, et si leur valeur numérique est explicitement décodable. Les indices dynamiques, imbriqués ou non démontrés conservent un avertissement et les dépendances conservatrices au niveau signal.
- Les blocs `Initial` ne sont reconnus que lorsqu'ils contiennent exclusivement des affectations directes de signaux à des expressions indépendantes des signaux à l'exécution (littéraux, paramètres/valeurs d'énumération reconnus par identité de déclaration slang, petites expressions constantes, sélections de paramètres).
- Ces affectations sont consignées dans `initializations` avec `scope: initial_only_not_runtime`. Elles **ne génèrent aucune arête** `data`, `control` ou `event`.
- Un bloc `initial` malformé, partiellement reconnu ou lisant un signal d'exécution est rejeté **en entier** et reste explicitement signalé.
- Les métadonnées sont additives au JSON existant (schéma graphe v1) ; elles ne prouvent ni un état initial en silicium, ni une équivalence, ni la précision globale du graphe. Les avertissements supprimés pour les sélections statiques correspondent à un cas désormais documenté dans les métadonnées, pas à une promotion générale de granularité.

## Régressions

```bash
python -m pytest -q tests/test_static_initial_dependencies.py tests/test_advanced_dependencies.py tests/test_timing_controls.py
python -m pytest -q -rs -o addopts='' tests/test_static_initial_dependencies.py
python scripts/validate_unknown_rtl.py --sources-root upstream_unknown --out reports/unknown-validation-pr33
```

La CI utilise slang 12.1 épinglé, les SHA des blobs Git amont et conserve les rapports des trois designs de terrain.

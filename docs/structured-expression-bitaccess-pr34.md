# PR #34 — AST d'expressions et accès imbriqués : réduction des enregistrements partiels

## Point de départ reproduit (corpus externe épinglé, PR #33)

| Cas | Expressions partielles | Accès bits partiels |
| --- | ---: | ---: |
| axis_register | 17 | 0 |
| priority_encoder | 2 | 7 |
| rxuart | 18 | 1 |

Zéro avertissement du graphe de dépendances dans les trois cas ne signifie
pas zéro enregistrement partiel dans les analyseurs indépendants.

## Analyseur `expressions`

Préserver explicitement les formes slang `ElementSelect`, `RangeSelect`,
`Concatenation`, `Replication` et `ConditionalOp` (conditions, branches,
sources et gardes) au lieu de retourner systématiquement `unsupported`.
Profondeur et budgets de nœuds existants conservés. Les formes malformées,
des motifs conditionnels non reconnus et les appels restent `partial`.

Le statut `syntax_supported` signifie **que la forme AST est représentée**,
jamais que l'équivalence RTL est prouvée, que toutes les plages sont évaluées
ou que les dépendances bit-à-bit sont correctes.

## Analyseur `bit_accesses`

Décoder les expressions arithmétiques `Add`, `Subtract`, `Multiply` bornées
utilisées par slang pour les indices de boucles `generate`. Un `NamedValue`
marqué `constant` ne suffit pas si son nom correspond à un signal d'exécution
de l'instance. Un indice dynamique conserve `partial`.

Conserver les sélections imbriquées sous `nested.selectors` dans leur ordre,
sans inventer de correspondance à un bit plat : un RHS de largeur connue
reste représentable comme `rhs_lanes_only`, mais **jamais**
`explicit_target_lanes` pour une LHS imbriquée. Les conversions redimensionnantes,
les opérations arithmétiques sur la valeur et les sources de largeur indéterminée
restent `partial` plutôt que d'inventer des positions.

## Vérifications

```bash
python -m pytest -q tests/test_structured_coverage_pr34.py \
  tests/test_expressions.py tests/test_bit_accesses.py tests/test_coverage.py
python -m pytest -q -rs -o addopts='' tests/test_structured_coverage_pr34.py
python scripts/validate_unknown_rtl.py --sources-root upstream_unknown \
  --out reports/unknown-validation-pr34
```

Le corpus réel, les empreintes Git, slang v12.1 et les seuils sur les
enregistrements partiels doivent être vérifiés en CI avant fusion. La couverture
du design entier reste `not_measured` sans oracle exhaustif indépendant.

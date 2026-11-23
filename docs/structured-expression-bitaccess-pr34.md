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

Les cibles sélectionnées `stage_valid[0][n]` ou `stage_enc[...][...]` sont
désormais rattachées à leur **déclaration de base vérifiée par identité slang**.
La syntaxe exacte de la cible est conservée dans `target_access` : aucune
position plate ne lui est imputée. Les genvars portant une valeur constante
fournie par slang sont représentés comme des références constantes uniquement
lorsqu'ils ne se résolvent pas en signaux RTL. L'index n'infère toujours pas
le sens complet des écritures de concaténations LHS.

Le budget de rendu est borné à **160 nœuds AST** et **16 niveaux** par
expression ; les entrées excédentaires restent `partial`, test compris.

Le statut `syntax_supported` signifie **que la forme AST est représentée**,
jamais que l'équivalence RTL est prouvée, que toutes les plages sont évaluées
ou que les dépendances bit-à-bit sont correctes.

## Analyseur `bit_accesses`

Décoder les expressions arithmétiques `Add`, `Subtract`, `Multiply` bornées
utilisées par slang pour les indices de boucles `generate`. Un `NamedValue`
marqué `constant` ne suffit pas si son nom correspond à un signal d'exécution
de l'instance. Un indice dynamique conserve `partial`.

Résoudre la déclaration de base par identité sémantique slang
(`SignalResolver`) plutôt que seulement par son nom : une référence homonyme
à mauvaise adresse est rejetée. Conserver les sélections imbriquées sous
`nested.selectors` dans leur ordre,
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

## Mesures sur les vrais RTL épinglés (GitHub Actions, slang 12.1)

| Cas | Expressions partielles avant → après | Expressions cibles exclues avant → après | Accès bits partiels avant → après | Avertissements graphe |
| --- | ---: | ---: | ---: | ---: |
| `axis_register` | **17 → 12** | 0 → 0 | 0 → 0 | 0 |
| `priority_encoder` | **2 → 0** | **6 → 0** | **7 → 5** | 0 |
| `rxuart` | **18 → 0** | 2 → 2 | 1 → 1 | 0 |

Le nombre d'expressions enregistrées pour `priority_encoder` passe de 3
à 9 : des affectations à des cibles sélectionnées apparaissent désormais
dans l'index au lieu d'être silencieusement exclues. Les **12** lignes
partielles de `axis_register` concernent le contexte d'événement implicite
sans liste de sensibilité explicitement détaillée. Les **5** accès aux bits
partiels de `priority_encoder` impliquent notamment réduction uniaire,
ternaire ou conversion : aucune correspondance positionnelle fictive n'est
créée. L'accès partiel de `rxuart` comporte une soustraction sur un RHS
concaténé ; les 2 cibles exclues côté expressions restent des LHS
concaténées hors de ce périmètre.

Ces nombres proviennent exclusivement du **corpus épinglé** avec slang réel.
Ils ne sont pas une mesure de couverture exhaustive, d'équivalence, de
synthétisabilité ou de précision à l'échelle du design. Le résumé global
continue de déclarer `observed_with_reported_limits` et
`design_coverage: not_measured`.

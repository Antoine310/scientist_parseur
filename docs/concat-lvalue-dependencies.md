# PR #32 — Cibles d'affectation en concaténation (périmètre borné)

## Observation reproductible

Le vrai récepteur UART ZipCPU `rxuart` (source épinglée dans
[le corpus externe](../benchmarks/unknown_designs_v1.json)) écrit plusieurs
registres à travers une concaténation dans un bloc séquentiel :

```systemverilog
{ck_uart, qq_uart, q_uart} <= {qq_uart, q_uart, i_uart_rx};
```

Avant cette PR, `rtlprep/dependencies.py` refusait la cible
`Concatenation` et ne construisait aucune dépendance pour cette affectation.
L'élaboration slang réussie ne rendait pas ces omissions visibles dans le
graphe, hormis l'avertissement explicite.

## Interprétation volontairement limitée

Pour une cible `Concatenation` :

- Les opérandes LHS doivent être des `NamedValue` identifiés par
  `SignalResolver` dans la même instance / le même AST.
  Si un seul opérande est inconnu, l'affectation est rejetée en entier.
- Les arêtes de contrôle et d'événement sont conservées pour chaque cible
  validée, même si les données ne peuvent être alignées.
- Les arêtes **data** positionnelles sont émises seulement si chaque
  opérande LHS est déclaré comme scalaire (type élaboré explicitement
  `logic`, `reg` ou `bit`) et si la RHS est :
  - une concaténation de même longueur, composée uniquement de signaux
    scalaires identifiés ou de littéraux **1 bit** de largeur explicite ;
  - un littéral entier ou de remplissage, éventuellement enveloppé
    dans des `Conversion` / `SignedConversion` simples et bornées dont
    l'opérande est entièrement littéral. Cela ne crée aucune dépendance
    de données, sans inférer la correspondance des bits constants.
- Une RHS arithmétique, une concaténation hétérogène, une sélection,
  des largeurs inconnues ou des membres LHS sélectionnés ne produisent
  **aucune correspondance data extrapolée**. Un avertissement documente
  cette analyse partielle, plutôt qu'une dépendance fictive entre tous les
  signaux de droite et toutes les cibles de gauche.
- Pas de correspondance de positions bit-à-bit générale, de simulation,
  de preuve fonctionnelle ou de couverture intégrale.

Sur le triplet de synchronisation UART, cela autorise uniquement :

| Source | Registre écrit |
| --- | --- |
| `qq_uart` | `ck_uart` |
| `q_uart` | `qq_uart` |
| `i_uart_rx` | `q_uart` |

Le reset `3'h0` n'apporte aucune arête `data` : il préserve néanmoins
les dépendances de contrôle (`i_reset`) et événementielles (`i_clk`)
vers chacun des trois registres.

## Validation

Tests sans EDA : `python -m pytest -q tests/test_concat_lvalue.py`.

Test réel, sur checkout upstream vérifié par Git blob SHA-1 et slang 12.1 :
`python -m pytest -q -rs -o addopts='' tests/test_concat_lvalue.py`.

Campagne de régression :
```bash
python scripts/validate_unknown_rtl.py \
  --sources-root upstream_unknown \
  --out reports/unknown-validation-pr32
```

La CI du corpus tiers exécute la régression réelle en plus des validations
existantes. Un meilleur graphe n'est ni une preuve d'équivalence ni une
mesure de précision globale ; les limitations de `Initial`, des sélections
et des autres analyseurs restent à traiter séparément.

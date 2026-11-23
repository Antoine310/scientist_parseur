# PR #36 — Membre de structure `MemberAccess` et CVA6 réel

## Preuve de départ : CVA6 épinglé de la PR #35

- Dépôt officiel : `openhwfoundation/cva6`, commit exact
  `742dc82a0c706e0a3bfb98b709fd3ee06d50d12a`.
- Configuration : `cv32a6_imac_sv32`, `core/compressed_decoder.sv`,
  élaboré avec slang v12.1 et les cinq fichiers amont vérifiés par SHA Git.
- Avant la PR #36 : **93 affectations** enregistrées,
  **57 expressions partielles**, **1 avertissement du graphe**.
  L'inspection des enregistrements montre que **toutes les 57** parties
  inconnues contiennent `MemberAccess`.

L'AST JSON de slang v12.1 utilise par exemple :

```json
{
  "kind": "MemberAccess",
  "member": "<semantic-declaration-address> FpPresent",
  "value": {
    "kind": "NamedValue",
    "symbol": "<semantic-declaration-address> CVA6Cfg",
    "constant": "<compiler-elaborated-constant>"
  }
}
```

Les adresses sémantiques sont propres à chaque exécution et ne sont
**jamais persistées** dans les graphes d'expressions.

## Sémantique conservatrice retenue

Le champ `member` de slang est analysé comme un couple identité/nom :
identifiant numérique valide et nom de membre borné. Une forme inattendue
n'est pas silencieusement acceptée : l'index d'expressions reste
`partial` et le graphe émet un avertissement.

- **Base constante démontrée** par un `Parameter` / `EnumValue`
  identifié sémantiquement, ou par un `NamedValue` non-signal
  marqué `constant` par slang : `member_access` est une expression
  structurée, mais il n'y a pas d'arête de dépendance runtime.
- **Base signal RTL identifié** par `SignalResolver` : l'expression
  conserve le champ, et le graphe suit une dépendance au **signal entier**.
  Il ne crée pas de bit-offset, de relation de champ synthétisée ou
  de fausse précision sur un champ packed.
- **Nom homonyme avec mauvaise adresse, nœud malformé ou valeur inconnue** :
  restent explicitement non résolus / partiels. Une propriété
  `constant` sur un signal runtime ne suffit **jamais** pour
  supprimer une arête de dépendance.

Le même prédicat conservateur est utilisé pour déterminer si un
`initial` composé uniquement de constantes peut être consigné comme
métadonnée sans arête de runtime.

**Non inclus** dans cette PR : les affectations à une LHS
`MemberAccess`, le mapping bit-à-bit des structures, les appels de
fonctions complexes, les chemins temporels, les propriétés fonctionnelles
ou une preuve d'exhaustivité.

## Résultat mesuré avec le vrai CVA6

| Indicateur | PR #35 | PR #36 |
| --- | ---: | ---: |
| Expressions capturées | 93 | **93** |
| Expressions partielles | 57 | **0** |
| Cibles d'expressions exclues | 0 | **0** |
| Avertissements du graphe | 1 | **0** |
| Nœuds du graphe | 12 | **12** |
| Arêtes du graphe | 13 | **13** |
| Sorties avec `instr_i` observable dans leur fan-in | 5/5 | **5/5** |

Les cinq traces sont non tronquées. Le changement de couverture porte
sur la **représentation de la syntaxe AST et des dépendances au niveau
signal**, pas sur une preuve que toutes les expressions sont correctement
calculées, ni qu'elles forment une couverture complète de la logique RTL.

Sur cette expérience, `coverage_assessment` devient
`no_reported_limits_within_scopes` ; `design_coverage` reste
`not_measured`, `functional_correctness` reste `not_tested`,
et `accuracy` reste
`not_measured_without_independent_exhaustive_oracle`.

## Validation

Le corpus `upstream_cva6` et les commandes d'installation
reproductible figurent dans
[`cva6-first-compressed-decoder.md`](cva6-first-compressed-decoder.md).

```bash
python -m pytest -q -rs tests/test_memberaccess_pr36.py
python -m pytest -q -rs tests/test_cva6_compressed_decoder.py
python scripts/run_cva6_compressed_decoder.py \
  --source-root upstream_cva6 --out reports/cva6-compressed-decoder-pr36 \
  --timeout 240
```

Les tests négatifs couvrent les homonymes, les champs malformés,
les `constant` trompeurs sur les signaux runtime, les initialisations,
les gardes procédurales et l'imbrication de champs. La CI
vérifie les compteurs issus du **vrai slang** sur le commit épinglé.

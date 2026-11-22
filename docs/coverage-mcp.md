# PR #23 — Couverture observée et limites d'analyse RTLPrep

## Objectif

Indiquer à Codex **ce que les analyseurs ont effectivement rapporté**
et **ce qu'ils n'ont pas pu traiter**, sans annoncer un faux
« pourcentage de RTL compris ».

La commande opérateur `python -m rtlprep deps` génère un graphe contenant
désormais `coverage` (schéma v1). L'outil MCP **lecture seule**
`rtl_coverage(signal=None, limit=20, offset=0)` consulte uniquement
ce rapport pré-calculé.

## Exemple

```bash
python -m rtlprep deps examples/advanced/design.json --out reports/advanced-coverage
python -m pytest -q tests/test_coverage.py
python -m pytest -q tests/test_integration_slang.py
```

Un serveur MCP pointant sur le graphe généré expose :

- `rtl_capabilities.coverage_available` : vrai si le snapshot contient
  le résumé v1.
- `rtl_coverage()` : bilan **global** par analyseur et page de constats.
- `rtl_coverage(signal="advanced_logic.picked")` : la même synthèse
  **globale**, mais seulement les constats associés *exactement*
  à cette cible. Les avertissements de graphe à granularité d'instance
  ne sont pas réattribués arbitrairement au signal.

Les résultats comportent `source_snapshot_status`, calculé à la
consultation avec le manifeste si disponible.

## Champs de la réponse

| Champ | Sens |
| --- | --- |
| `scope` | `observed_analyzer_records_only` |
| `design_coverage` | Toujours `not_measured` |
| `assessment` | `reported_limits` ou `no_reported_limits_within_scopes` |
| `analyzers.dependencies` | Nombre de nœuds, arêtes et avertissements |
| `analyzers.expressions` | Enregistrements `syntax_supported`, `partial` et inconnus |
| `analyzers.register_flow` | `syntactic_paths_supported`, `partial`, processus partiels |
| `analyzers.bit_accesses` | `explicit_target_lanes`, `rhs_lanes_only`, `partial` |
| `excluded_from_records` | Compteurs d'instructions ou de cibles ignorées quand disponibles |
| `related_process_limits` | Processus `always_ff` partiels (non confondus avec des cibles exclues) |
| `truncated` | L'analyseur a atteint une borne interne |
| `items` | Constats paginés : source de limite, cible si connue, motif |
| `global_findings_total` | Compte total des constats, même si la liste stockée est bornée |
| `global_findings_truncated` | Plus de 200 constats : la liste est incomplète |

Les constats stockés sont limités à **200** et les réponses MCP à
**100 par page**. Les comptes globaux de limites persistent même
quand les détails sont tronqués.

### Trois interprétations importantes

1. `no_reported_limits_within_scopes` signifie qu'aucune limite **observée
   par ces analyseurs** n'a été relevée. **Ce n'est jamais une preuve
   que l'ensemble du RTL est couvert.**
2. `no_observed_records` dans un analyseur signifie simplement qu'aucun
   enregistrement n'a été émis. Par exemple, `register_flow` ne couvre
   que certains `always_ff`, et `bit_accesses` ne couvre que certaines
   affectations continues.
3. Les unités de mesure diffèrent : une expression n'est ni un registre,
   ni une instruction ignorée, ni une arête du graphe. Les compteurs
   **ne sont pas additionnés pour fabriquer un pourcentage global**.

## Cas limites

Les statuts futurs/inconnus sont classés `unknown`, jamais
`syntax_supported`. Les compteurs malformés/incohérents font échouer
la construction plutôt que d'inventer des mesures. Les troncatures
restent visibles, les avertissements ne disparaissent pas et les
anciennes générations de graphes sans `coverage` exigent une nouvelle
commande `rtlprep deps`.

Le MCP n'exécute pas slang, simulateur ni preuve formelle.
La faisabilité des chemins, la causalité et le comportement ne sont
**pas** déduits du rapport.

## Test Codex conseillé

> Utilise uniquement le MCP `rtlprep-advanced`. Appelle
> `rtl_capabilities`, puis `rtl_coverage()` et
> `rtl_coverage(signal="advanced_logic.picked")`.
> Expose les limitations observées, le statut du snapshot et les
> différences de périmètre des analyseurs. Ne déduis ni un pourcentage
> global ni une preuve fonctionnelle. Ne lis pas les sources RTL,
> ne lance pas de commandes et ne modifie pas les fichiers.

Après régénération des rapports, **redémarrer Codex** pour recharger
le snapshot MCP.

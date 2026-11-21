# PR #20 — Gardes procédurales et événements dans l'AST slang

## Pourquoi ?

Le graphe de dépendances de RTLPrep répond à « quels signaux pourraient
influencer cette destination ? ». La PR #19 ajoutait l'arbre RHS des
`ContinuousAssign`. La PR #20 étend **le même outil MCP `rtl_expressions`**
aux affectations dans les blocs `always_ff`, `always_comb`, `always_latch`
et `always`.

Exemple pédagogique dans `examples/counter/counter.sv` :

```systemverilog
always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n)
        count <= 8'd0;
    else if (enable)
        count <= count + 8'd1;
end
```

La réponse peut contenir **deux affectations distinctes** vers
`counter.count`, chacune avec sa partie droite, les conditions
hiérarchisées qui mènent à l'affectation et les événements possibles
issus de l'AST.

## Format des observations

`rtlprep deps` insère les nouvelles données dans le bloc
`expressions` du `rtl_dependencies.json` **v1**. Aucun artefact séparé
ni nouvel outil MCP : `rtl_expressions(signal="counter.count")`
retourne les enregistrements paginés pour ce signal.

Les affectations procédurales portent :

- `assignment_kind="procedural"` et `procedure_kind="AlwaysFF"`
  (ou autre type reconnu) ;
- `expression` : arbre RHS de slang, sans lecture heuristique du RTL ;
- `guards` : chemin syntaxique ordonné de `if` avec `branch=then/else`,
  expression de condition ; pour `case` normal, sélecteur, étiquettes
  et branche `item/default` ;
- `events` : `PosEdge`/`NegEdge` et expression source lorsqu'il s'agit
  d'un `SignalEvent` exporté dans `EventList` ;
- `nonblocking` : booléen seulement si explicitement fourni par slang ;
- `coverage` : `syntax_supported` ou `partial` si une composante de la
  structure n'est pas reconnue ;
- `source` : référence à l'affectation fournie par slang, si disponible.

Les `ContinuousAssign` conservent leur arbre RHS et sont désormais
étiquetés `assignment_kind="continuous"`.

## Précautions de sémantique

**Ce n'est pas une simulation ni une preuve formelle.**

Une garde `if/else` est le chemin **syntaxique** jusqu'à l'affectation,
et non la preuve d'un changement observable à la sortie. Un événement
`posedge clk` signifie qu'un événement est listé par le bloc temporisé :
il ne prouve pas à lui seul un cycle de latence ni la priorité du reset.
Les affectations non bloquantes multiples, la priorité des affectations,
les expressions X/Z, le maintien implicite, les patterns, les `casez/casex`,
les écritures par bit/plage et les fonctions restent hors du calcul
fonctionnel. Les modes de comparaison `case` spéciaux sont marqués
partiels. Aucun algorithme n'essaie d'inférer une vulnérabilité.

Pour éviter les réponses trompeuses, l'index affiche également les
compteurs `unsupported_statements`, `unsupported_targets`,
`partial_expressions`, `procedural_blocks_visited`,
`procedural_blocks_skipped` et `truncated`.
Une requête vide **ne garantit pas** l'absence de logique. Les limites
sont de 2000 affectations par graphe, 96 nœuds d'arbre pour une entrée,
12 niveaux d'expression, 16 gardes et 16 événements transmis par entrée,
et 32 niveaux de parcours d'instructions.

## Test local sous Debian WSL

Depuis la branche de la PR #20, dans l'environnement Python du projet :

```bash
git fetch origin
git switch feat/rtl-procedural-guards-mcp
source .venv/bin/activate
slang --version
python -m pytest -q tests/test_expressions.py
python -m rtlprep deps examples/counter/design.json --out reports/counter-guards
```

Pour visualiser les affectations :

```bash
python - <<'PY'
import json
from pathlib import Path
graph = json.loads(Path("reports/counter-guards/rtl_dependencies.json").read_text())
for row in graph["expressions"]["items"]:
    if row["target"] == "counter.count":
        print(json.dumps(row, indent=2, ensure_ascii=False))
PY
```

Pour tester **Codex via MCP**, la configuration de la PR #19 est toujours
compatible, mais elle vise initialement `reports/hierarchy`. Si l'on
veut interroger `counter.count`, il faut **configurer un serveur MCP
avec les chemins du compteur** (ou remplacer temporairement les chemins
du serveur existant), puis démarrer une nouvelle session Codex.
Ne pas mélanger un index de hiérarchie et un graphe de compteur.

Exemple d'enregistrement d'un serveur distinct :

```bash
ROOT="$PWD"
codex mcp add rtlprep-counter -- "$ROOT/.venv/bin/python" -m rtlprep mcp \
  --index "$ROOT/reports/counter-guards/rtl_index.json" \
  --graph "$ROOT/reports/counter-guards/rtl_dependencies.json" \
  --manifest "$ROOT/examples/counter/design.json" \
  --reports-dir "$ROOT/reports/counter-guards"
```

Ensuite demander à Codex : « avec `rtlprep-counter`, appelle
`rtl_expressions` sur `counter.count` ; énumère chaque affectation,
les conditions imbriquées, les fronts et les limites. N'invente pas de
comportement ni de preuve de reset. »

La CI utilise le vrai slang et un **vrai client MCP stdio** pour tester
la sortie sur le compteur. Les tests de `case` portent également sur
`examples/advanced/design.json`. Le laboratoire CSR permet de
vérifier une condition de mise à jour `write_accepted_o` sans
assimiler la syntaxe à une preuve de sécurité.

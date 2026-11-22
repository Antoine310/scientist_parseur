# PR #24 — Candidats de transitions séquentielles (MCP lecture seule)

## Pourquoi une nouvelle vue ?

Les PR #20 et #21 fournissent des gardes, des événements et les
écritures non bloquantes (NBA) sur des chemins **syntaxiques** `always_ff`.
La PR #24 expose, séparément du `register_flow`, des informations
de **transition candidate** qui ne doivent pas être confondues avec
le résultat d'une simulation ou la preuve de l'état suivant.

Le bloc `sequential_candidates` est ajouté à `rtl_dependencies.json`
sans changer la version de son graphe. Le serveur MCP expose
`rtl_sequential_candidates(signal, limit=20, offset=0)`.
La consultation ne lance ni slang, ni Verilator, ni SBY/EQY.

## Champs

Pour chaque `target` et processus `always_ff` pris en charge :

- `events` : fronts observés dans l'AST slang (aucun rôle d'horloge
  ou reset inféré de l'événement **seul**) ;
- `paths` : alternatives syntaxiques avec gardes, `write_count` et
  `transition_candidate` ;
- `transition_candidate.kind=last_nba_rhs_syntax` : expression AST
  structurée de la **dernière** NBA sur ce chemin local, avec source
  et ordre. Ce n'est **pas** une valeur finale simulée ;
- `transition_candidate.kind=unwritten_in_this_process` : aucun
  écriture dans ce processus sur ce chemin ; ce n'est pas une
  preuve de maintien global du registre ;
- `transition_candidate.kind=unknown_rhs` : expression non résolue,
  donc aucune transition inventée ;
- `local_overwritten_orders` : ordres des NBA précédentes vers cette
  cible, **sur le même chemin** ;
- `multiple_processes_same_target` : d'autres processus analysés
  écrivent aussi cette cible ; aucune priorité entre ces processus ;
- `coverage=partial` : le processus/chemin est incomplet ; les
  `paths` de cet enregistrement sont volontairement vides.

### Reset : motif plausible, jamais preuve

Le champ `reset_like_guard_candidate` n'apparaît que si **toutes**
ces conditions syntaxiques sont réunies :

1. au moins deux signaux d'événements distincts ont été observés ;
2. la condition de garde **extérieure** est un signal simple ou
   sa négation `!` ; la branche sélectionnée implique `high` ou `low` ;
3. un front correspondant (`PosEdge` / `NegEdge`) de ce signal
   figure parmi les événements ;
4. la dernière NBA du chemin a une RHS littérale.

Exemple : `@(posedge clk or negedge rst_n)`, puis `if (!rst_n)`
et `count <= 8'd0` produit un motif
`reset_like_guard_candidate_not_proof`.
Si slang enveloppe le littéral dans un nœud `Conversion` ou
`SignedConversion`, la conversion est conservée dans
`rhs_conversion_kinds` : le littéral source est rapporté sans
évaluer sa valeur après conversion.

Cette correspondance **ne prouve pas** que `rst_n` réalise un reset
asynchrone, ni son comportement si d'autres processus ou X/Z
interviennent. Les resets synchrones, comparaisons complexes et
autres styles d'écriture ne sont pas classés ; l'absence d'un motif
ne prouve pas l'absence de reset.

### Priorités locales et transitions candidates

```systemverilog
always_ff @(posedge clk) begin
    q <= 8'd1;
    q <= 8'd2;
end
```

Un seul chemin comporte deux NBA ; la RHS de `q <= 8'd2` est la
dernière candidate, et la première écriture figure dans
`local_overwritten_orders`. À l'inverse, les branches
`if/else` exclusives ne sont **pas** rangées comme deux écritures
concurrentes sur un même chemin.

Les expressions arithmétiques comme `count + 1` sont rapportées
comme arbres syntaxiques `binary` ; les bits de résultat,
les débordements, les cycles, la faisabilité et la valeur finale
ne sont pas déduits.

## Test local WSL

```bash
cd ~/projets/scientist_parseur
git fetch origin
git switch feat/rtl-sequential-candidates-mcp
source .venv/bin/activate
python -m pytest -q tests/test_sequential_candidates.py
python -m rtlprep deps examples/counter/design.json --out reports/mcp-counter
```

Après régénération de `reports/mcp-counter`, **redémarrer Codex**
afin de recharger le snapshot du serveur `rtlprep-counter`.

Mission à donner à Codex :

> Utilise uniquement `rtlprep-counter`. Appelle `rtl_capabilities`,
> `rtl_register_flow(signal="counter.count")`, puis
> `rtl_sequential_candidates(signal="counter.count")`.
> Vérifie `source_snapshot_status=matching`. Décris les trois chemins
> syntaxiques et distingue une écriture littérale de zéro, un
> incrément `count+1` et un chemin non écrit. Présente le motif de
> reset comme **candidat**, sans conclure à un reset prouvé, à un
> cycle effectif ou à une transition d'état certaine.
> Ne lis pas les sources RTL et ne lance aucune commande EDA.

Pour les anciens snapshots sans `sequential_candidates`,
la requête renvoie une erreur et exige de relancer `rtlprep deps`.

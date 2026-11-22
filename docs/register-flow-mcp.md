# PR #21 — Chemins de mises à jour de registres (lecture seule)

## Contexte

La PR #19 extrait les arbres de la partie droite des affectations ; la PR #20
expose les conditions de branche `if/else` et les événements `AlwaysFF`.
Mais une liste d'affectations isolées ne dit pas **si elles se trouvent sur le
même chemin d'exécution**, ni si un chemin syntaxique évite toute écriture.

La PR #21 ajoute un résumé limité de **chemins syntaxiques** depuis l'AST
élaboré de slang. Il ne constitue pas une machine d'états finie, une
simulation ou une preuve de l'évolution des valeurs.

## Ce qui est analysé

Le bloc `register_flow` est ajouté à `rtl_dependencies.json` v1. Le
nouvel outil MCP en lecture seule `rtl_register_flow(signal, limit=20,
offset=0)` interroge ce bloc pré-calculé (pagination 1..100).

Pour chaque processus `always_ff` reconnu et chaque cible simple écrite
par affectation **non bloquante** :

- `process` : identifiant local stable à cette version du snapshot ;
- `events` : fronts `PosEdge` / `NegEdge` de `EventList` sur des
  signaux connus ;
- `paths` : alternatives syntaxiques `if/else`, avec conditions
  structurées, liste ordonnée des écritures et `last_nonblocking_write` ;
- `same_path_multiple_nba` : au moins un chemin comporte plusieurs NBA
  vers la même cible ; l'ordre est local au **même processus / chemin** ;
- `hold_candidate` : `syntactic_unwritten_path` si au moins un chemin
  énuméré n'écrit pas la cible ;
- `coverage` : `syntactic_paths_supported` ou `partial`.

Les valeurs de `hold_candidate` ont un sens restreint :

- `syntactic_unwritten_path` : une alternative syntaxique **sans écriture
  dans ce processus** existe. Cela ne démontre pas que ses conditions
  sont réalisables, ni que le signal global conserve sa valeur.
- `no_unwritten_path_in_enumerated_paths` : tous les chemins **modélisés**
  écrivent. Ce n'est pas une preuve générale de l'absence de maintien.
- `unknown` : présence d'une construction inconnue, d'une limite atteinte,
  ou d'un bloc partiellement analysé ; aucune conclusion de maintien.

### Exemple : compteur

```systemverilog
always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n)
        count <= 8'd0;
    else if (enable)
        count <= count + 8'd1;
end
```

Trois chemins syntaxiques sont attendus pour `counter.count` :

1. `!rst_n` (then) : une écriture du zéro, ligne 9 ;
2. `else` puis `enable` (then) : une écriture de l'incrément, ligne 11 ;
3. `else` puis `!enable` (else) : **aucune écriture dans ce processus**.

`rtl_register_flow` affiche donc `syntactic_unwritten_path`. Toute
inférence sur le reset asynchrone, le maintien réel ou les transitions
modulo 256 nécessiterait des règles de sémantique supplémentaires et, pour
une démonstration, un testbench ou une preuve formelle.

### Priorité locale

Dans une liste séquentielle :

```systemverilog
always_ff @(posedge clk) begin
  q <= 8'd1;
  q <= 8'd2;
end
```

les deux NBA se trouvent sur **le même chemin de ce processus**.
`writes_in_execution_order` reflète l'ordre et
`last_nonblocking_write` désigne la deuxième affectation. Cette
observation n'établit pas la valeur finale globale du signal si d'autres
processus interfèrent, ou si les expressions ont des effets de bord.

Une branche `if/else` exclusive ayant une écriture par branche n'est
**pas** considérée comme un cas de priorité entre deux NBA sur un même
chemin.

## Périmètre et garde-fous

- `always_ff` seulement ; instructions `List`, `StatementList`,
  `Block`, `Timed` explicite et `Conditional` à une expression simple ;
- cibles `NamedValue` (pas de bit/range-select), NBA explicites ;
- RHS simples sans appels ni affectations imbriquées ;
- pas de `case`, `casez`, boucles, `wait`, tâches, appels, sélections de
  bits, ni conditions composées non comprises ;
- refus de conclure si une branche / instruction nécessaire au parcours
  est non prise en charge ; l'objet reste `partial` et ses chemins sont vides ;
- bornes : 512 processus, 2000 cibles, 32 chemins par processus, 512
  instructions par analyse, profondeur 32, 16 gardes, 32 écritures par
  chemin ; pas de travail EDA dans le serveur MCP ;
- les chemins sont **syntaxiques** ; les conditions peuvent être
  impossibles ou dépendre de valeurs X/Z. Ce n'est pas un moteur SMT/BDD.

Les `counts` affichent `complete_processes`, `partial_processes`,
`always_ff_seen` et `truncated`. Les résultats `total=0` ne doivent
pas être utilisés pour affirmer qu'un registre n'a aucune logique si le
périmètre ne la couvre pas.

## Utilisation WSL

Depuis le dépôt local, avec slang déjà disponible dans `~/.local/bin` :

```bash
cd ~/projets/scientist_parseur
git fetch origin
git switch feat/rtl-register-paths-mcp
source .venv/bin/activate
slang --version
python -m pytest -q tests/test_register_flow.py
python -m rtlprep deps examples/counter/design.json --out reports/counter-guards
```

Le serveur `rtlprep-counter` existant conserve les bons chemins.
**Redémarrer Codex** pour charger le nouveau snapshot et le nouvel outil.
Ne pas réinstaller slang, ne pas créer de troisième serveur MCP.

Mission :

> Utilise uniquement `rtlprep-counter`. Appelle `rtl_capabilities`,
> puis `rtl_register_flow(signal="counter.count")` et
> `rtl_expressions(signal="counter.count")`. Décris les chemins
> d'écriture et le chemin sans écriture, puis distingue strictement
> observation syntaxique, maintien potentiel et preuve formelle.
> N'ouvre pas le RTL directement et ne lance aucun EDA.

Les tests CI couvrent des AST synthétiques (branches exclusives,
priorités locales, constructions refusées, explosion de chemins) et le
vrai slang sur compteur et CSR. Le protocole MCP stdio est testé avec
un véritable client SDK sur les rapports du compteur.

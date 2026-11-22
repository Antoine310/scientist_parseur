# PR #22 — Sélections de bits et concaténations via MCP

## Pourquoi une vue distincte ?

Le graphe de dépendances v1 considère chaque bus comme un **signal entier**.
Une arête `data` indique une influence structurelle possible et ne précise
ni les bits source, ni la plage affectée. La PR #22 conserve donc **toutes**
les arêtes existantes et ajoute un bloc JSON indépendant `bit_accesses`.

`rtl_bit_accesses(signal, limit=20, offset=0)` est un outil MCP **en lecture
seule**, alimenté par `rtlprep deps` via l'AST élaboré de slang. Il ne
recompile rien et ne lance aucun outil EDA.

## Couverture précise et limitations

Version 1 : affectations **continues** (`assign`) uniquement, expressions
constituées de sélections statiques `[n]`, `[msb:lsb]` descendantes et
de concaténations de segments dont la largeur est connue. Le nombre de
segments est borné à 32, la largeur à 1024 bits et les enregistrements
à 2000. Les constantes de sélection proviennent du littéral ou de
l'annotation de constante *élaborée* par slang ; le texte source RTL
n'est jamais analysé par regex.

Une entrée possède :

- `target` : nom exact du signal destination ;
- `target_selection` : `whole`, `bit`, ou `range` ;
- `source_segments` : sélection source et **position dans la RHS**
  (`rhs_lsb`, `rhs_msb`) de chaque segment ;
- `coverage` : `rhs_lanes_only`, `explicit_target_lanes`, ou `partial` ;
- `reason` si la reconstruction fiable est impossible ;
- `source` : provenance de l'affectation depuis slang.

**Attention :** lorsque la cible est un *signal entier*, les positions
de la concaténation sont celles de la **RHS**, pas nécessairement celles
du registre/fil destination. Les règles de dimensionnement SystemVerilog,
les conversions et les extensions/troncatures peuvent modifier la
correspondance effective. Pour une cible explicitement sélectionnée,
la correspondance `target_lsb/target_msb` est exposée **uniquement** si
la largeur explicite correspond exactement à la largeur RHS.

### Exemple sur le RTL avancé

```systemverilog
assign merged = {data_a[WIDTH-1:4], data_b[3:0]};
assign picked = data_a[idx];
```

Pour `WIDTH=8`, si slang élabore `WIDTH-1` en 7, les positions RHS
sont `data_a[7:4] → RHS[7:4]` et `data_b[3:0] → RHS[3:0]`.
Le premier résultat est `rhs_lanes_only`. Le second reste `partial`
avec `dynamic_or_unknown_index`. Il ne faut pas en conclure que
`picked` lit toujours un bit particulier.

Les cas non pris en charge (indices dynamiques, largeur inconnue,
opérateurs arithmétiques, casts, réplication, procédures, ports, etc.)
ne créent **aucune correspondance de bits inventée**. Une absence
d'enregistrement ne signifie donc **pas** une absence de dépendance :
la vue n'est pas exhaustive. La sémantique X/Z, les effets de bord,
les écritures multiples et la faisabilité ne sont pas prouvés.

## Reproduire les contrôles

```bash
python -m pytest -q tests/test_bit_accesses.py
python -m pytest -q tests/test_integration_slang.py
python -m rtlprep deps examples/advanced/design.json --out reports/advanced-bits
```

Dans Codex avec un serveur MCP pointant sur ces rapports :

> Appelle `rtl_capabilities`, puis
> `rtl_bit_accesses(signal="advanced_logic.merged")` et
> `rtl_bit_accesses(signal="advanced_logic.picked")`.
> Décris les positions **RHS** calculées et signale les accès dynamiques.
> Ne prétends pas avoir prouvé une correspondance de sortie ni un
> comportement fonctionnel.

Les anciens snapshots ne contiennent pas `bit_accesses` :
il faut relancer `rtlprep deps` et redémarrer le serveur MCP.

# PR #27 — Importer des filelists SystemVerilog en manifestes RTLPrep

## But

La commande **import-filelist** convertit une liste de fichiers de compilation
(`.f`) en `design.json` compatible avec l'analyse, l'indexation et le graphe
RTLPrep existants. Elle ne compile **rien** pendant l'import et n'exécute
**jamais** une commande présente dans une filelist.

```bash
python -m rtlprep import-filelist examples/filelist_project/compile.f \
  --root examples/filelist_project \
  --top imported_top \
  --out reports/imported/design.json

python -m rtlprep deps reports/imported/design.json \
  --out reports/imported
```

Le `--top` reste **obligatoire** : on ne déduit pas le top en fonction des
noms des fichiers ou d'un ordre heuristique. Le `--root` est la **racine de
confiance** ; la filelist d'entrée, les filelists imbriquées, chaque fichier
source et chaque répertoire include doivent rester **à l'intérieur** après
résolution de leurs liens symboliques.

## Syntaxe prise en charge

| Entrée | Traitement |
| --- | --- |
| `rtl/pkg.sv`, `rtl/mod.v` | Sources ajoutées dans l'ordre, doublons retirés |
| `-f listes/sub.f`, `-Flistes/sub.f` | Liste imbriquée, traitée sur place |
| `-I rtl/include`, `-Irtl/include` | Répertoire d'inclusion |
| `+incdir+rtl/include+rtl/headers` | Un ou plusieurs répertoires |
| `-D FOO=1`, `-DFOO=1` | Macro simple |
| `+define+FOO+BAR=1` | Macros simples |
| commentaires `#`, `//`, guillemets, continuation de ligne | Pris en charge |

**Toutes les entrées relatives sont interprétées par rapport au dossier du
fichier `.f` qui les contient, y compris `-f` et `-F`.** Ce choix est
explicite : ce n'est pas un émulateur complet de la résolution de chemins
de tous les simulateurs EDA ; certains outils interprètent `-f` par
rapport au répertoire de travail. Adapter les filelists en conséquence,
sans présumer une interchangeabilité totale des deux syntaxes.

Le code conserve l'ordre de compilation **donné dans la filelist** :
les packages qui doivent précéder les modules consommateurs doivent y
figurer avant eux. Il ne cherche pas encore à calculer un ordre de
dépendance entre packages.

Les fichiers d'en-tête `.svh`/`.vh` doivent être accessibles via
`include_dirs` et les directives d'inclusion du RTL ; ils ne sont
pas compilés comme sources autonomes.

## Exemple avec package et macro

La fixture [examples/filelist_project](../examples/filelist_project)
contient une liste racine, une liste imbriquée, un package importé, un
fichier d'inclusion, une macro et un module séquentiel. Le workflow
**Real slang integration** la compile avec slang v12.1, puis vérifie
l'index et le graphe issus du véritable AST.

Une seconde validation CI importe les **cinq sources réelles de l'ALU
OpenHW CV32E40P**, sur une révision upstream fixée et dont les hashes
Git sont vérifiés. Elle utilise le manifeste généré pour construire
un graphe réel et vérifier son top et ses dépendances.

## Contrat de sécurité et limites

La commande fonctionne localement, **hors MCP**. Le MCP reste strictement
en lecture seule. Les contraintes :

- **Fail closed** : les options non prises en charge `-y`, `-v`,
  `+libext+`, scripts, options arbitraires, substitutions de variables,
  expansions shell, jokers/globs, chemins hors racine ou fichiers absents
  produisent une **erreur** plutôt qu'une compilation partielle silencieuse.
- Cycles de filelists détectés, limites sur les niveaux, fichiers, nombre
  d'entrées et octets lus ; refus des symlinks qui quittent `--root`.
- Sources `.sv`/`.v` explicites seulement : pas de découverte récursive,
  pas d'auto-import de modules non listés, pas d'évaluation de `ifdef`
  pendant l'import.
- Le manifeste est écrit dans un fichier temporaire dans le dossier de
  sortie, validé avec `load_design`, puis remplacé atomiquement.
  Remplacer un manifeste existant exige **`--force`** ; l'entrée et les
  sources ne peuvent être écrasées par la sortie.
- Le manifeste conserve un bloc `filelist_import` avec les SHA-256 des
  filelists sources, leur ordre et la racine. Ces hashes décrivent
  l'import réalisé, **sans attester** l'identité de l'auteur des filelists.
- La fraîcheur `source_snapshot_status` dans le MCP continue de porter
  sur le contenu des **sources RTL déclarées** par le manifeste, et non
  sur la filelist d'entrée. Si celle-ci change, il faut **réimporter**
  et régénérer `rtlprep deps` avant de relancer Codex.

Cette PR ne résout pas encore automatiquement les `+libext+`,
`-y`, bibliothèques vendor, génération de sources, transformations
de scripts Tcl, substitutions de variables, options VCS/Questa,
langages VHDL ni toutes les dépendances d'un SoC. Les projets qui les
requièrent doivent préparer une filelist **déjà développée et explicite**
ou attendre un adaptateur spécialisé révisé.

## Sur WSL avec les dépendances installées

```bash
cd ~/projets/scientist_parseur
source .venv/bin/activate
source "$HOME/.local/share/rtlprep/toolchains/activate.sh"

python -m pytest -q tests/test_filelist.py
python -m pytest -q -rs tests/test_integration_filelist_slang.py

python -m rtlprep import-filelist \
  examples/filelist_project/compile.f \
  --root examples/filelist_project \
  --top imported_top \
  --out reports/filelist-demo/design.json

python -m rtlprep deps reports/filelist-demo/design.json \
  --out reports/filelist-demo
```

Un `deps` réussi confirme l'élaboration du RTL **déclaré** par cette
filelist avec slang et la construction du graphe dans la couverture
prise en charge. Il ne prouve ni la complétude du design, ni son
comportement fonctionnel, ni l'absence d'éléments SV non représentés.

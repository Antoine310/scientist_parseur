# RTLPrep — analyse et validation RTL sans API

**Statut : prototype évolutif avec index structurel et graphe de dépendances MVP.** Ce projet fournit un socle Python pour analyser et valider des circuits SystemVerilog dans un environnement de test autorisé. Il ne nécessite aucun LLM ni clé API.


## Préparer et mettre à jour les dépendances (Debian / WSL2)

Un **programme d'installation et de diagnostic** est fourni dans
[`scripts/rtlprep_env.py`](scripts/rtlprep_env.py).
Il installe les versions approuvées de slang et d'OSS CAD Suite
(**Verilator, Yosys, SBY, EQY, Z3**), ainsi que les dépendances Python
(**cocotb, MCP, pytest**) dans `.venv`.

```bash
python3 scripts/rtlprep_env.py                  # vérifie sans modifier
python3 scripts/rtlprep_env.py --install        # installe les versions épinglées
source .venv/bin/activate
source "$HOME/.local/share/rtlprep/toolchains/activate.sh"
python scripts/rtlprep_env.py --check
python scripts/rtlprep_env.py --check-updates   # cherche des versions nouvelles, sans installer
python scripts/rtlprep_env.py --update          # synchronise les versions approuvées du projet
```

**Sécurité :** l'installation est toujours explicite, sans `sudo` par
défaut, sans modifier `.bashrc`, avec empreintes SHA-256 verrouillées.
Les mises à jour utilisent les **versions testées par la CI**, pas la
dernière release publiée au hasard. L'archive OSS CAD Suite est
volumineuse (environ 754 Mo à télécharger, plus l'espace d'extraction).
L'installation cible Linux x86_64 / WSL2 avec Python 3.11 ou supérieur.

**[Guide détaillé : installation, dépannage, mise à jour des versions et
vérifications](docs/dependencies-bootstrap.md).**

## Import de projets SystemVerilog et filelists (PR #27)

RTLPrep sait préparer un manifeste `design.json` depuis une **filelist .f**
avec listes imbriquées, chemins RTL, packages ordonnés, `+incdir+`,
`+define+`, `-I` et `-D`. Aucune compilation ni commande externe n'est
lancée pendant l'import ; les chemins restent limités à `--root`.

```bash
python -m rtlprep import-filelist examples/filelist_project/compile.f \
  --root examples/filelist_project \
  --top imported_top \
  --out reports/filelist-demo/design.json

python -m rtlprep deps reports/filelist-demo/design.json \
  --out reports/filelist-demo
```

L'import **refuse les options non comprises**, les globs, les substitutions
shell, les fichiers manquants et les chemins qui sortent de la racine.
Il ne prétend pas détecter automatiquement les packages manquants ou
résoudre toutes les conventions de filelists utilisées par les EDA.
Une intégration CI exécute **slang réel**, y compris sur l'ALU CV32E40P.

[**Guide et limites de l'importeur SystemVerilog**](docs/filelists-systemverilog.md).

## Validation sur des RTL externes (PR #28)

Une campagne reproductible utilise **3 blocs de 2 projets open source tiers**
(registre AXI-Stream, encodeur de priorité et récepteur UART), à des
révisions Git et empreintes blob **épinglées**. Elle génère des rapports de
vraie élaboration slang, index, graphe, avertissements, couverture
**des enregistrements observés uniquement** et troncatures de fan-in
avec trois budgets de requêtes.

La campagne distingue un échec réel, une analyse partielle et une
observation sans limitation signalée, **sans prétendre mesurer la
correction fonctionnelle, la couverture totale du design ou la
précision de Codex**.

```bash
python scripts/validate_unknown_rtl.py \
  --sources-root upstream_unknown \
  --out reports/unknown-validation
```

La préparation et les revisions Git précises des deux dépôts sont dans
le [guide de validation des RTL externes](docs/unknown-designs-validation.md).
Les sources externes ne sont pas recopiées dans le dépôt et sont ignorées
par Git dans le dossier `upstream_unknown/`.

## Scopes generate et identités AST (PR #29)

RTLPrep indexe désormais les registres et nets déclarés dans des blocs
`generate` actifs **nommés**, avec chemins qualifiés (`genblk1.reg`).
Le graphe et les expressions relient leurs références aux adresses
sémantiques de slang **dans le même AST**, sans fusionner les homonymes.
Les adresses instables ne sont pas enregistrées dans les rapports.

Régression sur la véritable IP AXI-Stream `axis_register` et ses variantes
`REG_TYPE=0,1,2`. L'extraction de dépendances reste **syntaxique**
et ne couvre pas tous les scopes/événements de SystemVerilog.

[Guide PR #29 : résolution des signaux sous generate](docs/generate-scope-symbols.md).
## Événements SystemVerilog explicites et implicites

Le graphe de dépendances différencie désormais `always @*` (sensibilité
implicite, **sans arête `event` inventée**) et `always @(posedge clk)`
ou `@(negedge rst)` (front explicite, arête d'événement uniquement
sur une identité de signal réellement résolue par slang).

Les autres déclenchements temporels non pris en charge restent signalés.
La couverture de certains analyseurs demeure partielle.

[Guide de validation des événements temporels](docs/timing-events.md).
## 📚 Documentation pédagogique détaillée

Une documentation en français explique **tous les composants de RTLPrep v0.1**, avec extraits du code réel, schémas de circulation des données, tutoriels et exercices :

1. [Parcours d'apprentissage](docs/README.md) — guide des chapitres et vocabulaire de base.
2. [Architecture du projet](docs/architecture.md) — fichiers Python, manifeste et enchaînement des opérations.
3. [Analyseur SystemVerilog, AST et récursion](docs/parser-systemverilog.md) — explication ligne par ligne de `summarize_ast` et de slang.
4. [CLI et validation avec les outils EDA](docs/outils-et-validation.md) — `run_command`, Verilator, Yosys, logs et statuts.
5. [TP guidé sur le compteur](docs/tutoriel-compteur.md) — commandes à exécuter et résultats à inspecter.
6. [Tests et évolutions](docs/tests-et-evolutions.md) — pytest, tests d'intégration et préparation du graphe de dépendances.

Le cours précise ce qui est **implémenté** et ce qui reste **prévu**, pour éviter de confondre inventaire AST et véritable analyse de dépendances.

## Intégration avec le vrai compilateur slang

La CI GitHub Actions contient maintenant un workflow séparé
[`slang-integration.yml`](.github/workflows/slang-integration.yml) :
il installe **slang v12.1** sur Ubuntu et vérifie l'analyse réelle
du compteur et de la hiérarchie multi-modules. Le premier essai a révélé
que le cache d'instances de slang rendait certains corps incomplets pour
notre extracteur JSON. RTLPrep utilise provisoirement
`--disable-instance-caching` pour obtenir des instances distinctes.

**[Tutoriel : installation, explication du cache et tests réels](docs/slang-environnement.md).**

## Tests de parsing et hiérarchie

Le projet contient aussi `examples/hierarchy`, un design multi-modules avec
deux instances du même module. Les tests d'intégration `tests/test_integration_slang.py`
utilisent le véritable exécutable slang **s'il est installé**, sinon ils sont
explicitement marqués comme sautés. Les tests unitaires valident séparément les
erreurs d'AST, le top demandé et les chemins d'instance.

```bash
python -m pytest -q
python -m pytest -v tests/test_integration_slang.py
python -m rtlprep analyze examples/hierarchy/design.json --out reports/hierarchy
```

## Nouvel index RTL : navigation dans les modules et signaux

RTLPrep peut maintenant construire un **index JSON versionné** des modules,
instances, ports et déclarations de signaux depuis l'AST réel de slang.
Les positions de source (`source_file`, `source_line`, `source_column`)
sont recopiées depuis le compilateur, sans deviner les emplacements.

```bash
python -m rtlprep index examples/hierarchy/design.json --out reports/hierarchy
python -m rtlprep query reports/hierarchy/rtl_index.json modules
python -m rtlprep query reports/hierarchy/rtl_index.json tree
python -m rtlprep query reports/hierarchy/rtl_index.json module leaf
python -m rtlprep query reports/hierarchy/rtl_index.json signal hierarchy_top.first status
python -m rtlprep source examples/hierarchy/design.json leaf.sv --line 2
```

**[Documentation complète et explication du code de l'index](docs/index-rtl.md).**
C'est un index **structurel**, pas encore le graphe de fan-in/fan-out.

## Expressions RTL structurées pour Codex (PR #19)

`rtlprep deps` enregistre aussi dans `rtl_dependencies.json`
les arbres AST des **parties droites d'affectations continues simples**.
Le nouvel outil MCP `rtl_expressions(signal="instance.signal")`
interroge ces arbres sans exécuter slang ou lire de RTL à la demande.
Chaque réponse conserve les noms d'opérateurs issus de slang,
un chemin hiérarchique, la provenance source et un indicateur de portée.
Exemple : `LogicalAnd` n'est plus confondu avec `LogicalOr`
dans le laboratoire CSR, même si les arêtes de dépendances sont identiques.

Pour mettre à jour un rapport **déjà généré** avant cette évolution, relancer
`rtlprep deps` et **redémarrer Codex**, le MCP étant un snapshot.
Les procédures `always_*`, les conditions de branche, le mapping bit-à-bit et
les nœuds AST non couverts ne sont **pas** interprétés dans cette première phase.
Les arbres d'expression ne prouvent ni l'équivalence ni la sécurité d'un module.
[Documentation et protocole de test](docs/expressions-mcp.md).

## Chemins d'écriture always_ff et candidats de maintien (PR #21)

Le nouveau `rtl_register_flow` (MCP en lecture seule) expose, depuis
l'AST de slang, les alternatives syntaxiques `if/else` vers les écritures
non bloquantes d'un même `always_ff`. Il met en évidence une branche
sans écriture et distingue des NBA successives sur un **même chemin**
de branches mutuellement exclusives. Les structures inconnues donnent
`partial` / `unknown` : **aucune preuve de maintien ou de transition**
n'est inférée. [Guide](docs/register-flow-mcp.md).

## Gardes des `always_*` et événements de déclenchement (PR #20)

L'index d'expressions s'étend aux affectations procédurales des
`always_ff`, `always_comb`, `always_latch` et `always`.
`rtl_expressions` rend les conditions `if/else` imbriquées, le contexte
des branches `case` normales, la distinction affectation bloquante/non
bloquante lorsque slang l'indique, ainsi que les événements
`posedge/negedge` présents dans l'AST élaboré.

**Ces données restent syntaxiques** : elles ne calculent pas les priorités
des affectations, le maintien implicite, la latence ni la sémantique X/Z.
Les constructions non prises en charge sont signalées et les réponses MCP
sont bornées. Le serveur n'exécute toujours aucun EDA.
[Guide et commandes de test](docs/conditions-procedurales-mcp.md).

## Graphe de dépendances RTL (phase C — MVP)

Le nouveau module `rtlprep/dependencies.py` extrait un **graphe orienté**
depuis l'AST élaboré par slang. Il distingue les relations de **données**,
de **contrôle**, d'**événement** et de **port d'instance**.
Le parcours `fanin` / `fanout` est borné en profondeur et en nombre d'arêtes.

```bash
python -m rtlprep deps examples/dependencies/design.json --out reports/deps
python -m rtlprep trace reports/deps/rtl_dependencies.json fanin dependency_top.out --depth 6
python -m rtlprep trace reports/deps/rtl_dependencies.json fanout dependency_top.a --depth 6
```

**[Cours pédagogique : algorithme, exemples et limites du graphe](docs/graphe-dependances.md)**.

⚠️ Ce graphe n'est pas une preuve formelle et **n'est pas exhaustif**
pour toutes les constructions SystemVerilog. Les expressions non prises en
charge sont signalées dans `rtl_dependencies.json` (`warnings`).

## Constructions SystemVerilog avancées — tests réels avec slang

Le graphe analyse désormais des `case` ordinaires, les concaténations,
les lectures par sélection de bit/plage et des blocs `generate if`
**déjà élaborés** par slang. Les références de paramètres constants sont
distinguées des signaux RTL. La précision reste au niveau du **signal entier**.

```bash
python -m rtlprep deps examples/advanced/design.json --out reports/advanced
python -m rtlprep trace reports/advanced/rtl_dependencies.json fanin advanced_logic.result --depth 3
```

[**Cours détaillé : comprendre le vrai AST et le code Python**](docs/systemverilog-avance.md).

## Test sur un vrai module de processeur RISC-V

RTLPrep a été exécuté avec **slang v12.1** sur le décodeur d'instructions
compressées du **CV32E40P officiel** (révision Git et contenu des sources
vérifiés). Le compilateur et l'index ont réussi, et le fan-in de chacune
des trois sorties remonte à `instr_i`.

**Résultat : 4 nœuds, 4 arêtes et 12 avertissements ; la couverture reste
partielle.** Ce test a permis de corriger la traversée de `List` (blocs
`begin/end`) et le traitement de `Replication` (`{N{expr}}`).
Les constantes importées d'un package restent à reconnaître correctement.

```bash
python scripts/run_cv32e40p_decoder.py \
  --source-root upstream_cv32e40p \
  --out reports/cv32e40p
```

La récupération de la révision exacte et le test automatisé sont réalisés
par [GitHub Actions](.github/workflows/cv32e40p-real.yml).

**[Lire le rapport et le cours pédagogique du test CV32E40P](docs/test-cv32e40p-reel.md).**
Les sources du CPU ne sont pas recopiées dans ce dépôt.

## Premier module CVA6 officiel analysé (PR #35)

RTLPrep dispose maintenant d'une première expérience reproductible sur
le **vrai compressed decoder du CVA6**, avec le checkout Git officiel
`742dc82`, la configuration `cv32a6_imac_sv32` et slang 12.1.

La première exécution a élaboré **2 instances, 12 nœuds et 13 arêtes** ;
les cinq sorties sont reliées à `instr_i` par des traces `fanin`.
Mais le graphe présente encore **1 avertissement `MemberAccess`** et
l'index d'expressions compte **57 enregistrements partiels sur 93**.
**La couverture et l'exactitude fonctionnelle ne sont pas mesurées**.

[Voir les sources épinglées, la reproduction et les limites](docs/cva6-first-compressed-decoder.md).

## Accès aux champs dans le vrai CVA6 (PR #36)

Sur le même `compressed_decoder` CVA6 épinglé que la #35, RTLPrep
représente désormais les nœuds d'AST slang `MemberAccess` issus de
`CVA6Cfg` et les champs de signaux RTL **sans créer de fausses
dépendances runtime pour les constantes**. Une lecture d'un champ RTL
reste une dépendance au signal entier, sans mapping bit-à-bit.

Le vrai test slang v12.1 passe de **57 à 0 expressions partielles** sur
93 enregistrées, et de **1 à 0 avertissement** dans le graphe, sans
perdre les 12 nœuds ni les 13 arêtes observées. Les cinq fan-in jusqu'à
`instr_i` sont toujours présents et non tronqués. La couverture
totale reste `not_measured`, et la correction fonctionnelle n'est
pas prouvée.

[Mesures, limites et tests négatifs de la PR #36](docs/memberaccess-cva6-pr36.md).

## Écritures de membres de structures (PR #37)

L'index `expressions` accepte désormais les cibles `MemberAccess`
(`state.low <= data`) et conserve le champ écrit dans `target_access`.
Le graphe remonte les dépendances vers le **signal de base**, avec un
**avertissement explicite** : les champs et les bits affectés ne sont
pas localisés de manière prouvée. Les identités slang erronées ne sont
pas résolues par simple nom.

Une fixture de structure `packed` avec `always_ff` est testée par
**vrai slang v12.1** ; la CI exécute aussi la régression CVA6
épinglée. L'analyse des bits des processus n'est pas encore étendue.
La couverture totale et l'accuracy fonctionnelle ne sont pas mesurées.

[Guide, cas limites et reproduction de la PR #37](docs/member-lvalue-pr37.md).

## Reconnaissance sémantique des constantes et vraie ALU CV32E40P

Les paramètres et les valeurs d'énumération des packages SystemVerilog sont
maintenant identifiés grâce aux **identifiants de symboles fournis par slang**
— sans règle approximative basée sur un nom de type `OPCODE_*` ou `ALU_*`.

Deux expériences GitHub Actions sont reproductibles sur le **CV32E40P officiel**
et une révision figée : le décodeur compressé et l'ALU complète, avec ses
trois sous-modules. Les avertissements du graphe ont diminué de **12 à 1**
pour le décodeur et de **71 à 11** pour l'ALU. La couverture reste partielle.

```bash
python scripts/run_cv32e40p_alu.py \
  --source-root upstream_cv32e40p \
  --out reports/cv32e40p-alu

python -m rtlprep trace reports/cv32e40p-alu/rtl_dependencies.json \
  fanin cv32e40p_alu.result_o --depth 12
```

Les scripts vérifient la révision et les empreintes de chaque fichier source.
**[Cours détaillé et mesures réelles sur l'ALU](docs/constantes-et-alu-cv32e40p.md)**.
Ce benchmark ne prouve ni la complétude du graphe ni la correction du matériel.

## Simulation comportementale : Verilator + cocotb (PR #11)

La commande `simulate` exécute de **vrais tests de simulation**
via **Verilator 5.040** et **cocotb 2.0.1**. Elle vérifie les sorties
du matériel contre des modèles Python de référence et conserve des
rapports xUnit/XML et JSON.

```bash
python -m pip install -e '.[dev,simulation]'

# Compteur 8 bits : reset, enable, maintien et débordement
python -m rtlprep simulate examples/counter/design.json --out reports/sim-counter

# FSM : transitions IDLE / BUSY / DONE
python -m rtlprep simulate examples/fsm/design.json --out reports/sim-fsm

# Contrôle négatif attendu : cette simulation doit échouer (code 2)
python -m rtlprep simulate examples/counter/buggy_design.json --out reports/sim-buggy
```

Les tests cocotb sont des **bancs de test approuvés** dans
`rtlprep/sim_tests/` ; la CLI ne charge pas de Python arbitraire
indiqué par un design tiers. Si Verilator/cocotb manque, le statut est
`missing_tool` et aucun faux succès n'est affiché.

[**Cours détaillé : architecture, simulation réelle, rapport XML et
circuit volontairement faux**](docs/simulation-cocotb-verilator.md).

## Vérification formelle : SBY, Yosys et Z3 (PR #12)

En complément des simulations cocotb, RTLPrep peut maintenant exécuter
des **propriétés formelles approuvées** sur le compteur et une FSM,
puis chercher un témoin d'atteignabilité (`cover`).

```bash
# Nécessite la suite OSS CAD Suite (sby + yosys + z3)
python -m rtlprep formal examples/counter/design.json --out reports/formal-counter
python -m rtlprep formal examples/fsm/design.json --out reports/formal-fsm

# Cas FAUX volontaire : doit échouer et fournir un contre-exemple
python -m rtlprep formal examples/counter/buggy_design.json --out reports/formal-buggy
```

Le rapport `formal.result.json` distingue `passed`, `failed`,
`inconclusive` (SBY `UNKNOWN`), `missing_tool` et `timeout`.
Les contre-exemples VCD sont conservés ; la CLI ne lance que des bancs
de preuve inclus dans le paquet et **pas de configuration SBY arbitraire**
provenant d'un projet tiers.

**[Cours détaillé : induction, hypothèse de reset, non-vacuité et
contre-exemples](docs/preuves-formelles-sby.md).**

## Vérification d'équivalence RTL : Yosys EQY (PR #13)

RTLPrep peut maintenant comparer une **référence RTL (gold)** à une
**implémentation candidate (gate)** à l'aide de **Yosys EQY + SBY/Z3**.

```bash
# Refactorisation du compteur : équivalence attendue
python -m rtlprep eqy examples/counter/design.json \
  --gate examples/counter/refactored_design.json \
  --out reports/eqy-counter

# Refactorisation de la FSM : équivalence attendue
python -m rtlprep eqy examples/fsm/design.json \
  --gate examples/fsm/refactored_design.json \
  --out reports/eqy-fsm

# Contrôle négatif (+2 au lieu de +1) : non-équivalence ATTENDUE
python -m rtlprep eqy examples/counter/design.json \
  --gate examples/counter/buggy_design.json \
  --out reports/eqy-buggy
```

Les trois comparaisons sont exécutées dans la CI sur la vraie
**OSS CAD Suite 2026-11-18**. EQY a démontré l'équivalence
du compteur (**1 partition**) et de la FSM (**6 partitions**),
et fournit un **contre-exemple VCD** sur la variante incorrecte.

Le rapport `equivalence.result.json` distingue **`equivalent=true`**
(preuve), **`equivalent=false`** (contre-exemple réel) et
**`equivalent=null`** (résultat inconclusif). Les comparaisons
admises restent en **liste blanche** pour ce premier jalon.

[**Cours pédagogique : gold/gate, partitions, preuves, erreurs et limites**](docs/equivalence-eqy.md).

## Équivalence sur un vrai bloc RISC-V CV32E40P (PR #14)

Le backend **Yosys EQY** a maintenant été exécuté sur
**`cv32e40p_popcnt`**, véritable module du CV32E40P OpenHW.
Les sources officielles sont récupérées à une révision Git figée
et **vérifiées par leur hash** ; aucun RTL propriétaire ni module CPU
recopié n'est ajouté au dépôt.

Le script crée deux variantes locales : une addition à opérandes
permutés (**équivalente, 31 partitions prouvées**) et une soustraction
volontairement incorrecte (**non équivalente, trace VCD**).

```bash
# Après checkout du dépôt OpenHW à la révision épinglée
python scripts/run_cv32e40p_popcnt_eqy.py \
  --source-root upstream_cv32e40p \
  --out reports/cv32e40p-popcnt-eqy
```

**[Tutoriel : première équivalence réelle sur un sous-module RISC-V](docs/eqy-cv32e40p-popcnt.md)**.
La preuve d'équivalence concerne **ces deux versions**, pas la correction
du CPU ou la conformité fonctionnelle du module à sa spécification.

## Brancher RTLPrep sur Codex grâce au serveur MCP (PR #15)

**Première interface agent en lecture seule :** `rtlprep mcp` utilise
le **SDK MCP Python officiel 2.3.0** et le transport local `stdio`.
Codex peut interroger les modules, instances, signaux, dépendances et
rapports de validation existants, sans lancer d'outils EDA ni modifier
un fichier. Le SDK MCP est facultatif et demande Python **3.11+**.

```bash
python -m pip install -e '.[dev,mcp]'
python -m rtlprep deps examples/hierarchy/design.json --out reports/hierarchy

python -m rtlprep mcp \
  --index reports/hierarchy/rtl_index.json \
  --graph reports/hierarchy/rtl_dependencies.json \
  --manifest examples/hierarchy/design.json \
  --reports-dir reports/hierarchy
```

**Le programme attend sur stdin : c'est normal pour un serveur MCP.**
Pour l'utiliser depuis Codex, ajouter la commande comme serveur stdio
local avec `codex mcp add` et des **chemins absolus**.

[**Guide complet : configurer Codex, outils disponibles, sécurité,
protocole MCP et limites**](docs/mcp-codex-lecture-seule.md).

## Premier agent Codex sur WSL — recherche et fraîcheur MCP (PR #18)

Le serveur MCP en lecture seule permet maintenant de rechercher des
signaux/ports par nom (`rtl_find_signals`) et signale si les empreintes
du graphe, de l'index, des rapports et des sources déclarées sont
incohérentes ou non vérifiables. Un fichier RTL modifié depuis
l'analyse ne peut plus être présenté comme un extrait des mêmes sources
vérifiées lorsqu'une empreinte est disponible.

**[Guide pratique Debian WSL : connecter Codex à RTLPrep](docs/codex-wsl-premier-agent.md)**.
Cette intégration ne prouve ni une compréhension sémantique du RTL,
ni l'efficacité d'un agent sur des problèmes tenus secrets.

## Phase G — mesurer RTLPrep avant d'ajouter d'autres agents (PR #16)

Un premier **benchmark reproductible** combine le **vrai slang v12.1**,
quatre exemples SystemVerilog étiquetés et la **véritable ALU CV32E40P**
(OpenHW à révision et hash fixés). Il vérifie 35 relations
de dépendance positives, 16 négatives et 7 questions simples.

Trois stratégies de contexte pour un agent sont comparées
sur **les mêmes questions** : **A** = RTL brut, **B** = index seul,
**C** = index + parcours de graphe + extrait source limité.
Les volumes sont mesurés en **octets JSON**, **pas en tokens
d'IA** ni en précision réelle d'une réponse de Codex/ChatGPT.

```bash
# Exige le vrai slang dans le PATH
python scripts/run_rtl_benchmark.py \
  --out reports/rtl-benchmark --repeat 3

# Inclure aussi le vrai CPU après préparation OpenHW :
python scripts/run_rtl_benchmark.py \
  --out reports/rtl-benchmark --repeat 3 \
  --cpu-manifest reports/benchmark-cpu-prep/cv32e40p_alu_design.json
```

Le benchmark génère `benchmark_report.json` et des rapports par
circuit, rejette les résultats EDA manquants et les graphes
instables entre répétitions. La CI complète prépare et vérifie
elle-même les fichiers CPU officiels.

[**Lire le cours pédagogique et les mesures de la phase G**](docs/benchmark-phase-g.md).

## Laboratoire de sécurité RTL : contrôler les privilèges (PR #17)

Premier exercice défensif sur une **IP de formation inspirée d'un CSR RISC-V** :
trois versions d'un registre protégé (correcte, refactorisée,
**volontairement vulnérable**) et un contrat indépendant de contrôle d'accès.

Le même banc de test doit **réussir** pour le RTL sain et **échouer**
sur la variante où `machine_mode && !debug_locked` devient
`machine_mode || !debug_locked`. La CI utilise **le vrai slang,
Verilator/cocotb, Yosys/SBY et EQY** puis conserve les traces VCD.

```bash
# Générer les graphes comparés
python -m rtlprep deps examples/security_csr/design.json \
  --out reports/security-lab/rtl-gold
python -m rtlprep deps examples/security_csr/buggy_design.json \
  --out reports/security-lab/rtl-buggy

# Après installation facultative des outils de simulation et formels
python -m rtlprep simulate examples/security_csr/design.json \
  --out reports/security-lab/sim-gold
python -m rtlprep formal examples/security_csr/design.json \
  --out reports/security-lab/formal-gold
```

**Fait intéressant :** le circuit sain et le mutant ont les
**8 mêmes arêtes de dépendances typées**, malgré un comportement
de sécurité différent. Le graphe **localise les influences**,
mais **ne remplace pas** les assertions et les essais.

[**Tutoriel complet : scénarios, contrat de sécurité, contre-exemples et
exercice à poser à un agent**](docs/laboratoire-securite-csr.md).

**Cet exercice utilise une faille artificielle. Aucune vulnérabilité
n'est revendiquée sur le véritable processeur CV32E40P et aucun agent
autonome n'a encore été évalué.**

## Démarrage rapide

Sur Linux ou WSL2 avec Python 3.10+ :

```bash
python -m pip install -e '.[dev]'
python -m rtlprep doctor
python -m rtlprep analyze examples/counter/design.json --out reports/counter
python -m rtlprep lint examples/counter/design.json --out reports/counter
python -m rtlprep synth examples/counter/design.json --out reports/counter
python -m rtlprep all examples/counter/design.json --out reports/counter
python -m pytest -q
```

Les outils EDA sont **optionnels au démarrage**. Si slang, Verilator, cocotb ou Yosys sont absents pour leur opération respective, le programme renvoie explicitement `missing_tool` : il n'invente jamais un résultat.

## Outils EDA à installer

- [slang](https://github.com/MikePopoloski/slang) : élaboration SystemVerilog et export AST JSON (`slang` dans `PATH`).
- [Verilator](https://verilator.org/guide/latest/install.html) : analyse/lint RTL.
- [Yosys](https://github.com/YosysHQ/yosys) : synthèse logique des designs pris en charge.
- [OSS CAD Suite](https://github.com/YosysHQ/oss-cad-suite-build/releases) : distribution de Yosys et de plusieurs outils formels.

Pour les designs complexes comme CVA6, la prise en charge dépend du frontend, de la configuration et des packages : l'exemple livré est volontairement petit.

## Commandes

| Commande | Fonction |
| --- | --- |
| `doctor` | Vérifie les exécutables et modules Python disponibles |
| `analyze` | Génère l'AST élaboré slang et un inventaire JSON des instances/ports |
| `lint` | Exécute `verilator --lint-only` et conserve les journaux |
| `synth` | Synthèse Yosys et nombre de cellules dans le module top |
| `all` | Lance les trois opérations ci-dessus |
| `index` | Produit un index versionné des instances, ports et signaux |
| `query` | Interroge l'index sans relancer slang |
| `deps` | Produit le graphe typé des dépendances connues |
| `trace` | Recherche bornée `fanin` / `fanout` dans un graphe |
| `source` | Affiche un extrait d'un fichier source du manifeste |
| `simulate` | Lance un banc cocotb approuvé sous Verilator, produit JSON + xUnit |
| `formal` | Vérifie des assertions SBY approuvées et des témoins `cover` |
| `eqy` | Compare deux variantes RTL approuvées par équivalence formelle |
| `mcp` | Lance un serveur MCP local de consultation des résultats existants |

Les rapports sont écrits dans `reports/`, ignoré par Git. Les commandes créent aussi une empreinte SHA-256 du projet.

## Configurer un design

Créer un manifeste JSON, chemins relatifs au manifeste :

```json
{
  "top": "counter",
  "sources": ["counter.sv"],
  "include_dirs": [],
  "defines": []
}
```

## Limites explicites

- L'index structurel et le graphe de dépendances sont **des sous-ensembles du langage** : ils ne modélisent pas exhaustivement tous les circuits SystemVerilog.
- Le nombre de cellules Yosys ne mesure ni la surface physique ni la puissance.
- Les tests slang, les simulations cocotb/Verilator, les preuves **SBY/Yosys/Z3** et les premiers tests d'équivalence **EQY** sont validés sur des bancs contrôlés. Le CPU complet n'est pas prouvé correct ; l'équivalence EQY est limitée aux paires de RTL approuvées.
- Les logs d'outils sont des données non fiables et ne doivent jamais être exécutés comme des instructions par un futur agent.
- L'objectif actuel est l'analyse et la vérification de circuits de test ; le projet n'implémente pas l'insertion de Trojans.

## Feuille de route

Voir [docs/roadmap.md](docs/roadmap.md). Les instructions pour Codex se trouvent dans [AGENTS.md](AGENTS.md).

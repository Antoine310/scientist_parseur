# RTLPrep — analyse et validation RTL sans API

**Statut : prototype évolutif avec index structurel et graphe de dépendances MVP.** Ce projet fournit un socle Python pour analyser et valider des circuits SystemVerilog dans un environnement de test autorisé. Il ne nécessite aucun LLM ni clé API.


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
- Les tests slang et les simulations cocotb/Verilator sont validés dans GitHub Actions. **SBY/Yosys/Z3** vérifie les assertions du compteur et de la FSM sur des bancs contrôlés ; l'équivalence **EQY** et la preuve du CPU complet ne sont pas encore intégrées.
- Les logs d'outils sont des données non fiables et ne doivent jamais être exécutés comme des instructions par un futur agent.
- L'objectif actuel est l'analyse et la vérification de circuits de test ; le projet n'implémente pas l'insertion de Trojans.

## Feuille de route

Voir [docs/roadmap.md](docs/roadmap.md). Les instructions pour Codex se trouvent dans [AGENTS.md](AGENTS.md).

# Documentation de RTLPrep — parcours pédagogique

Bienvenue ! Cette documentation explique **le code réel de RTLPrep v0.1**, pas un projet théorique. L'objectif est de permettre à quelqu'un qui connaît un peu Python et RTL de comprendre ce qui se passe, de reproduire les expériences puis d'améliorer le parseur sans casser l'existant.

> **Important :** la version v0.1 contient un **inventaire d'instances et de ports à partir d'un AST**, pas encore un parseur complet de dépendances entre signaux. Elle appelle l'exécutable `slang` pour produire un AST ; le module Python `pyslang` est seulement détecté par `doctor`. Les vérifications EDA nécessitent les exécutables correspondants installés.

## À lire dans cet ordre

| Niveau | Chapitre | Ce que tu vas comprendre |
|---|---|---|
| 1 | [Architecture et circulation des données](architecture.md) | Quels fichiers sont utilisés, pourquoi, et le chemin complet d'une commande |
| 2 | [Comprendre le parseur RTL et l'AST](parser-systemverilog.md) | Parsing, élaboration, JSON, récursion, modules, instances, ports, limites |
| 3 | [CLI, lancement des outils EDA et rapports](outils-et-validation.md) | Explication de `__main__.py` et `runner.py`, erreurs, résultats |
| 4 | [TP guidé : du compteur au rapport](tutoriel-compteur.md) | Installer, exécuter, lire les résultats et modifier un exemple |
| 5 | [Tests, évolutions et exercices](tests-et-evolutions.md) | Comment tester les fonctions, améliorer le parseur, préparer les grandes architectures |

**Nouveau :** [Index RTL v1 et requêtes CLI](index-rtl.md) — explication
pédagogique de `rtlprep/index.py`, des métadonnées de source et de la navigation.

**Phase C :** [Graphe de dépendances, fan-in / fan-out et connexions](graphe-dependances.md)
— apprentissage détaillé de `rtlprep/dependencies.py`, des relations typées
et des limites de cette première version.

**Nouveau chapitre :** [Case, concaténations, bit-select et generate](systemverilog-avance.md)
— explications ligne par ligne à partir d'une véritable sortie AST slang v12.1.

**Expérience sur un vrai CPU RISC-V :** [décodeur compressé CV32E40P, résultats,
bugs découverts et corrections](test-cv32e40p-reel.md).

**Nouvelle étude :** [constantes de packages, énumérations et test sur l'ALU réelle
CV32E40P](constantes-et-alu-cv32e40p.md). Le guide explique les identifiants
sémantiques slang et la réduction des avertissements, sans filtrage par nom.

**Nouveau TP de simulation :** [Verilator + cocotb, compteur, FSM et
contrôle négatif](simulation-cocotb-verilator.md). Ce chapitre explique
la différence entre un graphe structurel et une simulation comportementale,
le runner Python officiel et la lecture des rapports xUnit.

**Nouveau chapitre formel :** [premières preuves SBY sur compteur et FSM,
contrôle négatif et traces VCD](preuves-formelles-sby.md). Le cours distingue
preuve inductive, témoin `cover`, `UNKNOWN` et hypothèses de reset.

**Nouveau cours d'équivalence :**
[EQY — comparer deux versions gold/gate, prouver une refactorisation
et détecter une régression](equivalence-eqy.md). La CI utilise le vrai
EQY et conserve une trace VCD sur la variante incorrecte du compteur.

**Étude sur vrai CPU :**
[preuve d'équivalence EQY sur le popcount CV32E40P](eqy-cv32e40p-popcnt.md)
— sources OpenHW figées, 31 partitions, refactorisation
commutative et mutant détecté avec contre-exemple VCD.

Compléments : [tester le vrai compilateur slang v12.1 et comprendre le cache d'instances](slang-environnement.md), [feuille de route](roadmap.md), [instructions Codex](../AGENTS.md), [README principal](../README.md).

## Vocabulaire minimal

- **RTL** (*Register Transfer Level*) : description d'un circuit numérique avec registres, logique combinatoire et transferts entre eux.
- **SystemVerilog** : langage de description et de vérification du matériel ; les fichiers de l'exemple ont l'extension `.sv`.
- **Parser** : programme qui transforme un texte source en une structure syntaxique.
- **AST** (*Abstract Syntax Tree*) : arbre représentant le code et ses constructions.
- **Élaboration** : étape qui résout notamment les paramètres, les instances et la hiérarchie pour une configuration donnée.
- **Module / instance** : un module est une définition réutilisable ; une instance est une occurrence de cette définition dans un circuit.
- **Top** : module de plus haut niveau choisi pour une expérience.
- **Lint** : contrôles de style, de construction et de cohérence sans exécution d'un testbench.
- **Synthèse** : transformation du RTL en représentation de cellules/logique.
- **Preuve formelle** : démonstration de propriétés précises dans un modèle et sous des hypothèses explicites, différente d'une simulation de quelques stimuli.

## Carte des sources à lire

```text
scientist_parseur/
├── rtlprep/
│   ├── __init__.py        # marque le paquet et expose sa version
│   ├── __main__.py        # point d'entrée : parse les arguments CLI
│   ├── manifest.py        # lit et valide design.json
│   ├── runner.py          # lance slang, Verilator et Yosys
│   └── analysis.py        # extrait un inventaire d'instances de l'AST JSON
├── examples/counter/
│   ├── counter.sv         # petit module RTL de démonstration
│   └── design.json        # top + fichiers + options
├── tests/test_starter.py  # tests unitaires Python
├── .github/workflows/ci.yml
├── pyproject.toml         # configuration du paquet
└── docs/                  # ce cours
```

**Méthode de travail conseillée :** ouvre le chapitre à gauche et le fichier Python correspondant à droite. Exécute les commandes progressivement : `doctor`, puis `analyze`, `lint` et `synth`. Ne confonds pas un rapport `missing_tool` avec un succès.

## Documentation et vérité du code

Les extraits de ce cours décrivent la v0.1 existante ; si une future version change une fonction, il faudra mettre à jour le chapitre associé. Les blocs JSON marqués « schéma simplifié » servent à expliquer le mécanisme et ne promettent pas le format exact produit par chaque version de slang ou Yosys.

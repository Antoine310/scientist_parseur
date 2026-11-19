# 1 — Architecture du projet et flux de données

## Ce que RTLPrep fait aujourd'hui

La v0.1 est une **CLI** (interface en ligne de commande) Python. Elle charge un manifeste, exécute un outil EDA externe et écrit des rapports. Ce n'est **pas** encore un agent LLM autonome, ni un moteur de transformation AST.

```text
Tu tapes une commande
       │
       ▼
rtlprep/__main__.py  ─── choisit analyze / lint / synth / all
       │
       ▼
rtlprep/manifest.py  ─── lit design.json et vérifie les chemins
       │
       ▼
objet Design (top, sources, includes, defines)
       │
       ├──► analyze → slang → AST JSON → analysis.summarize_ast → résumé JSON
       │
       ├──► lint    → Verilator → stdout, stderr, code retour
       │
       └──► synth   → Yosys → netlist JSON → statistiques de cellules
       │
       ▼
reports/ (résultats enregistrés)
```

Le **modèle Python ne simule pas un processeur** : il orchestre de vrais outils EDA et lit leurs sorties.

## Le rôle précis de chaque fichier

### `rtlprep/__init__.py`

Déclare le paquet Python et sa version : `__version__ = "0.1.0"`. Ce fichier ne fait pas de parsing.

### `rtlprep/__main__.py`

Est exécuté par `python -m rtlprep ...`. Son rôle est de **traduire une demande utilisateur** en appels de fonctions Python. Il n'est pas censé connaître la syntaxe SystemVerilog.

### `rtlprep/manifest.py`

Contient la dataclass immuable `Design` et la fonction `load_design`. Une *dataclass* rassemble les informations nécessaires à une expérience dans un objet typé.

```python
@dataclass(frozen=True)
class Design:
    manifest: Path
    top: str
    sources: tuple[Path, ...]
    includes: tuple[Path, ...]
    defines: tuple[str, ...]
```

- `manifest` : chemin du fichier de configuration lu.
- `top` : nom du module racine, par exemple `counter`.
- `sources` : liste ordonnée des fichiers source RTL.
- `includes` : dossiers contenant les fichiers inclus par le préprocesseur.
- `defines` : macros à transmettre aux outils, par exemple `FEATURE=1`.
- `frozen=True` : on ne peut pas réassigner un champ de l'objet accidentellement après sa création.

**Pourquoi un manifeste ?** Sur un circuit complexe, le même code peut être compilé de plusieurs façons suivant ses macros, paramètres et sources. Centraliser au moins une partie de ces informations évite que chaque commande utilise une liste de fichiers différente.

### `rtlprep/runner.py`

Définit les fonctions d'accès aux exécutables locaux :

- `doctor()` — repère les outils disponibles.
- `fingerprint()` — calcule une empreinte utile pour nommer/relier les expériences.
- `run_command()` — exécute une commande avec timeout, capture des logs et statut.
- `common_verilator_args()` et `common_slang_args()` — construisent les options CLI.
- `analyze()`, `lint()`, `synth()` — opérations utilisateur.

Tous les outils sont appelés via `subprocess.run`, **sans** invocation de shell dans cette version, avec les arguments séparés dans une liste.

### `rtlprep/analysis.py`

Contient `summarize_ast(ast)`, une fonction Python pure : elle reçoit un dictionnaire issu de JSON et retourne un dictionnaire résumé. C'est le **cœur actuel de l'extraction d'informations structurelles**, expliqué en détail dans le [chapitre suivant](parser-systemverilog.md).

### `tests/test_starter.py`

Vérifie les comportements de base sans installer slang ni Verilator : chargement du manifeste, format de l'empreinte, parcours d'un AST fictif, gestion d'un outil absent, présence des clés du diagnostic.

### `.github/workflows/ci.yml`

Installe Python et les dépendances de test sur GitHub Actions, puis lance `pytest` et `doctor`. Cette CI **ne prouve pas** encore le bon fonctionnement de slang, Verilator ou Yosys sur un projet réel : ce seront des tests d'intégration futurs.

## Le manifeste de l'exemple

Ouvre [examples/counter/design.json](../examples/counter/design.json) :

```json
{
  "top": "counter",
  "sources": ["counter.sv"],
  "include_dirs": [],
  "defines": []
}
```

Le chemin `counter.sv` est relatif au dossier **du manifeste**, pas au dossier duquel tu as lancé la commande. Le code réalise, en substance :

```python
path = Path(filename).expanduser().resolve()
source = (path.parent / "counter.sv").resolve()
```

Par exemple, tu peux lancer la commande depuis la racine du dépôt sans te placer dans `examples/counter/`.

### Validation réalisée par `load_design`

La fonction :

1. lit le JSON UTF-8 ;
2. vérifie que `top` ressemble à un identifiant simple ;
3. vérifie que `sources` est une liste non vide de chaînes ;
4. transforme les chemins en chemins absolus ;
5. vérifie l'existence des fichiers source et dossiers d'inclusion ;
6. vérifie les types des `defines` ;
7. renvoie l'objet `Design`.

**Ce qu'elle ne fait pas :** analyser une syntaxe SystemVerilog, vérifier les dépendances entre packages, détecter des cycles de modules ou assurer une isolation de sécurité des chemins. Des manifestes provenant de sources non fiables doivent être exécutés dans un environnement isolé.

## Comment lire une sortie de commande ?

Par exemple :

```bash
python -m rtlprep lint examples/counter/design.json --out reports/counter
```

Le code crée un dossier `reports/counter/`, un fichier `manifest_snapshot.json` et, selon l'outil, les fichiers `lint.result.json`, `lint.stdout.log` et `lint.stderr.log`.

La valeur de retour de la commande est déterminée par le statut :

- code `0` : les tâches demandées ont le statut `passed` ;
- code `2` : au moins une tâche n'a pas le statut `passed` ou une erreur de configuration est survenue.

Le statut `passed` ne signifie **pas** que le circuit est correct dans toutes les situations. Il signifie uniquement que **la commande considérée** a réussi.

## Pourquoi cette séparation de fichiers ?

Le principe de conception est simple : **une fonction a une responsabilité claire**.

- Modifier l'interface CLI ne doit pas nécessiter de réécrire l'analyse AST.
- Ajouter un autre parseur ne doit pas modifier la définition de `Design`.
- Remplacer Yosys ou ajouter EQY doit rester possible via une fonction isolée.
- Un futur LLM ne recevra idéalement que les résumés dont il a besoin, tout en pouvant demander les sources RTL exactes.

C'est la base d'un outil maintenable lorsque les architectures cibles changent.

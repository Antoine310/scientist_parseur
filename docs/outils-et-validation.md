# 3 — CLI, outils EDA et validation : lecture détaillée du code Python

Ce chapitre explique [`rtlprep/__main__.py`](../rtlprep/__main__.py) et [`rtlprep/runner.py`](../rtlprep/runner.py) fonction par fonction.

## 3.1 La CLI : comment une commande devient un appel Python

Quand tu écris :

```bash
python -m rtlprep analyze examples/counter/design.json --out reports/counter
```

Python exécute `rtlprep/__main__.py`, puis la fonction `main()`.

```python
p = argparse.ArgumentParser(prog="rtlprep", description="Outils RTL locaux, sans cle API")
sub = p.add_subparsers(dest="cmd", required=True)
sub.add_parser("doctor", help="afficher les outils et paquets disponibles")
```

- `ArgumentParser` sait lire et contrôler les options de la ligne de commande.
- `sub` contient les sous-commandes.
- `required=True` oblige à fournir `doctor`, `analyze`, `lint`, `synth` ou `all`.
- `dest="cmd"` signifie qu'une commande apparaîtra dans `args.cmd`.

Le code ajoute ensuite les mêmes arguments aux quatre opérations qui prennent un design :

```python
for name in ("analyze", "lint", "synth", "all"):
    s = sub.add_parser(name)
    s.add_argument("manifest", help="chemin vers design.json")
    s.add_argument("--out", default="reports", help="dossier de sortie")
    s.add_argument("--timeout", type=int, default=120, help="timeout par outil en secondes")
```

La valeur `120` est un timeout **par outil**, pas nécessairement la durée de l'opération `all` entière.

Après `parse_args()`, la fonction :

1. gère séparément `doctor`, qui n'a pas besoin de manifeste ;
2. charge le design avec `load_design(args.manifest)` ;
3. crée le dossier `--out` ;
4. écrit `manifest_snapshot.json` ;
5. sélectionne les fonctions `analyze` / `lint` / `synth` ;
6. exécute chaque fonction et imprime son statut.

```python
tasks = {"analyze": analyze, "lint": lint, "synth": synth}
keys = list(tasks) if args.cmd == "all" else [args.cmd]
```

Ce dictionnaire est une manière simple d'éviter quatre longues branches `if/elif`. Une fonction pourra être ajoutée plus tard en complétant ce dictionnaire et le parser.

Le code retourne `0` seulement lorsque **tous les statuts demandés** valent `passed`. Sinon il retourne `2`, par exemple si un exécutable manque.

## 3.2 `doctor()` : repérer les outils présents

```python
TOOL_NAMES = ("slang", "verilator", "yosys", "sby", "eqy", "openroad")

def doctor() -> dict:
    import importlib.util
    return {
        "tools": {name: shutil.which(name) for name in TOOL_NAMES},
        "python_modules": {
            name: importlib.util.find_spec(name) is not None
            for name in ("pyslang", "cocotb", "pytest")
        },
    }
```

`shutil.which("verilator")` renvoie le chemin de l'exécutable s'il apparaît dans le `PATH`, sinon `None`. `find_spec` vérifie la disponibilité d'un module Python.

**Limite :** cela n'exécute pas l'outil, ne vérifie pas sa version et ne garantit pas qu'il pourra compiler le design. De plus, `sby`, `eqy` et `openroad` sont ici **seulement détectés**, pas encore intégrés aux commandes de RTLPrep.

## 3.3 `fingerprint()` : garder une trace de l'expérience

```python
h = hashlib.sha256()
h.update(design.top.encode())
for source in design.sources:
    h.update(str(source).encode())
    h.update(source.read_bytes())
```

La fonction additionne au hash :

- le nom du module top ;
- le nom/chemin absolu de chaque fichier source ;
- le contenu exact de ces fichiers ;
- les noms des dossiers d'inclusion ;
- les chaînes de définition des macros.

Puis elle retourne `h.hexdigest()`, soit 64 caractères hexadécimaux.

**Attention :** la v0.1 ne hash pas le **contenu** des fichiers situés dans les dossiers d'inclusion ni les **versions des compilateurs**. Deux expériences avec la même empreinte peuvent donc différer si une dépendance incluse ou un outil change. Ce n'est pas encore une clé de cache reproductible suffisante.

## 3.4 `run_command()` : la fonction commune

Tous les lancements de programmes externes passent par cette fonction :

```python
def run_command(cmd: list[str], label: str, out_dir: Path, timeout: int = 120) -> dict:
    ...
```

### Vérifier l'installation

Elle commence par créer `out_dir` et rechercher `cmd[0]` avec `shutil.which`. Si `verilator` n'existe pas, le résultat contient :

```json
{
  "task": "lint",
  "status": "missing_tool",
  "returncode": null,
  "elapsed_seconds": 0.0,
  "error": "Outil absent du PATH: verilator"
}
```

Il peut y avoir d'autres clés comme `argv` et `timestamp` ; cet exemple met en évidence les informations principales.

### Exécuter avec délai maximal

```python
proc = subprocess.run(
    cmd,
    text=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    timeout=timeout,
    check=False,
)
```

- `cmd` est une **liste**, par exemple `["yosys", "-s", "..."]` : aucun shell n'est demandé.
- `stdout=PIPE` récupère la sortie normale.
- `stderr=PIPE` récupère les diagnostics/erreurs.
- `text=True` convertit ces sorties en chaînes.
- `timeout` évite qu'une commande continue indéfiniment dans les conditions habituelles de `subprocess.run`.
- `check=False` laisse le programme traiter un retour non nul au lieu de lever immédiatement une exception.

**Ce qui est mesuré :** le temps mural de la commande et son **code retour**. Un code retour nul produit `passed` ; non nul produit `failed`. Cela ne démontre pas à lui seul que les propriétés fonctionnelles attendues sont satisfaites.

### Les différents statuts

| Statut | Signification |
|---|---|
| `passed` | Le processus appelé a retourné `0` et les étapes de post-traitement éventuelles ont abouti |
| `failed` | Le processus a retourné un code non nul, ou un post-traitement requis a échoué |
| `missing_tool` | Exécutable absent du `PATH` |
| `timeout` | Temps imparti dépassé |
| `error` | Échec système, par exemple impossibilité de lancer le processus |
| `not_run` | Valeur initiale interne avant lancement ; pas un résultat de test final normal |

Le code écrit `<label>.result.json` et, si le programme a démarré, les fichiers `<label>.stdout.log` / `<label>.stderr.log`.

> **Sécurité :** lancer un compilateur sur du RTL tiers n'est pas une opération sans risque. Le fait d'utiliser une liste d'arguments évite une injection via un shell, mais **ne remplace pas** un conteneur isolé, des limites de ressources, ni un contrôle des chemins.

## 3.5 `lint()` : contrôles Verilator

```python
cmd = ["verilator", "--lint-only", "-Wall", "-Wno-fatal", *common_verilator_args(d)]
return run_command(cmd, "lint", out, timeout)
```

- `--lint-only` : effectue des contrôles sans construire la simulation.
- `-Wall` : active un ensemble élargi d'avertissements.
- `-Wno-fatal` : **les warnings ne provoquent pas à eux seuls l'échec** de la commande.

Cette dernière option compte : **`passed` ne veut pas dire « aucun warning »**. Pour compter les warnings, il faudra parser les logs ou choisir une politique plus stricte.

`common_verilator_args` fournit le `--top-module`, les `+incdir+...`, les `+define+...` et les chemins sources.

## 3.6 `analyze()` : de slang au résumé Python

```text
design.json
    │
    ▼
common_slang_args ─► commande slang
    │
    ▼
elaborated_ast.json
    │
    ▼
json.loads(...)
    │
    ▼
summarize_ast(...)
    │
    ▼
design_summary.json
```

La fonction `analyze` **ne parcourt pas elle-même l'AST** : elle délègue ce travail à `summarize_ast`. Le rôle de `analyze` est de préparer la commande, lancer slang, lire le JSON et sauvegarder le résultat.

`summarize_ast` est détaillé dans [le chapitre 2](parser-systemverilog.md).

**Si slang retourne 0 mais n'écrit pas de fichier valide**, RTLPrep marque l'analyse en `failed`. C'est important : un résultat vide ne doit pas être pris pour un design vide.

## 3.7 `synth()` : transformer le RTL avec Yosys

La fonction crée un fichier de commandes Yosys :

```yosys
read_verilog -sv "counter.sv"
hierarchy -check -top counter
proc
opt
synth -top counter
write_json "netlist.json"
```

Le fichier concret `synthesis.ys` contient des **chemins absolus**, les options de macros/d'inclusion et les options de synthèse adaptées au manifeste. Cet exemple montre seulement la séquence logique.

### Comprendre les commandes une par une

1. `read_verilog -sv` : lit le Verilog/SystemVerilog **pris en charge par le frontend Yosys**.
2. `hierarchy -check -top counter` : établit la hiérarchie et vérifie les modules manquants.
3. `proc` : transforme les processus procéduraux en éléments plus proches du modèle logique interne.
4. `opt` : réalise des optimisations simples.
5. `synth -top counter` : exécute une séquence de synthèse.
6. `write_json` : exporte une représentation du design synthétisé.

Le script est lancé avec `yosys -s chemin/synthesis.ys`.

### Compter les cellules

```python
raw = json.loads((out / "netlist.json").read_text(encoding="utf-8"))
selected = raw.get("modules", {}).get(d.top, {})
cells = selected.get("cells", {})
by_type = {}
for cell in cells.values():
    typ = cell.get("type", "unknown")
    by_type[typ] = by_type.get(typ, 0) + 1
```

Le résultat :

- `cell_count` : nombre d'entrées dans le dictionnaire `cells` **du top sélectionné** ;
- `cells_by_type` : répartition par type de cellule.

Ce n'est **ni** une mesure de surface en µm², **ni** une estimation de puissance, **ni** une mesure de temps critique. En cas de hiérarchie résiduelle ou de choix de technologie différents, les résultats ne sont pas directement comparables.

### La protection `_quote_yosys`

Le code vérifie certains caractères problématiques (saut de ligne, retour chariot, guillemet, point-virgule) et entoure les chemins de guillemets. C'est une protection limitée de la génération de scripts, **pas** un analyseur formel du langage de commandes Yosys ni une sandbox.

## 3.8 Tableau de synthèse : qui garantit quoi ?

| Action | Question à laquelle elle répond | Ne permet pas de conclure |
|---|---|---|
| `doctor` | « Est-ce que l'outil semble installé ? » | « Le design fonctionnera avec cet outil » |
| `analyze` | « L'AST est-il exportable et quelles instances sont reconnues ? » | « Je connais toutes les dépendances » |
| `lint` | « Quels problèmes Verilator signale-t-il ? » | « Le design est fonctionnellement correct » |
| `synth` | « Yosys peut-il synthétiser cette configuration ? » | « Le design respectera l'aire/timing physique » |
| `pytest` | « Les tests Python écrits passent-ils ? » | « Le parsing est validé sur CVA6 » |

Les preuves formelles SBY/EQY et la simulation cocotb font partie de la [feuille de route](roadmap.md) et **ne sont pas encore branchées** dans la v0.1.

## 3.9 Pour un futur agent LLM

Le bon contrat d'outil sera un résultat **structuré** :

```json
{
  "task": "lint",
  "status": "failed",
  "returncode": 1,
  "elapsed_seconds": 0.4
}
```

Le LLM doit pouvoir demander un extrait de log **en tant que donnée**, puis décider de la prochaine expérience. Il ne doit pas interpréter du texte de log comme une instruction d'exécuter des commandes arbitraires. Le statut doit rester calculé par Python, jamais inventé par un LLM.

# Installer et maintenir les dépendances RTLPrep (Debian / WSL2 x86_64)

RTLPrep fournit un outil de préparation de l'environnement, **sans dépendance Python
externe pour son propre fonctionnement** :

```bash
cd ~/projets/scientist_parseur
python3 scripts/rtlprep_env.py                  # diagnostic uniquement
python3 scripts/rtlprep_env.py --install        # installation explicite
source .venv/bin/activate
source "$HOME/.local/share/rtlprep/toolchains/activate.sh"
python scripts/rtlprep_env.py --check
python -m rtlprep doctor
```

Sur Debian/WSL, le programme suppose **Python >= 3.11** (pour le SDK MCP),
Linux x86_64 et les outils système `make` et `g++`. Il peut créer automatiquement
`.venv` à la racine du dépôt, puis installer les extras Python du projet avec
`pip install -e '.[dev,simulation,mcp]'` dans cet environnement virtuel.

Si les outils système sont absents, le programme **ne lance pas sudo** par défaut.
Sur Debian/Ubuntu, utiliser `sudo apt-get install -y build-essential` après
`sudo apt-get update`, ou autoriser explicitement cette seule opération avec :

```bash
python3 scripts/rtlprep_env.py --install --with-system
```

Cette dernière option utilise `sudo apt-get`, et nécessite donc ton autorisation
et le mot de passe du système. Les archives CAD/Python ne demandent pas `sudo`.

## Outils et versions gérées

Le fichier versionné [`scripts/toolchain.lock.json`](../scripts/toolchain.lock.json)
énumère les **versions testées par la CI** et leurs sommes SHA-256 exactes :

| Élément | Pin du projet | Installation |
| --- | --- | --- |
| OSS CAD Suite | `2026-11-18` | Archive officielle Linux x64, contient Yosys, SBY, EQY, Z3, Verilator, etc. |
| slang | `v12.1` | Archive officielle séparée pour préserver la version AST employée dans les tests |
| Verilator | `>=5.036` | Vérifié dans OSS CAD Suite pour cocotb 2.x |
| cocotb | `2.0.1` | Extra `simulation` du `pyproject.toml` |
| MCP | `2.3.0` | Extra `mcp` du `pyproject.toml` |
| pytest | `>=7` | Extra `dev` du `pyproject.toml` |
| make, g++ | Présence requise | Paquets système Debian / Ubuntu |

La suite téléchargée est volumineuse (archive Linux x64 d'environ **754 Mo**, plus
espace temporaire et extraction). Prévoir plusieurs gigaoctets disponibles sur WSL.
Le script vérifie **avant extraction** les empreintes exactes épinglées,
les tailles maximales, la structure des archives et leurs liens.

OpenROAD et le module facultatif `pyslang` ne sont pas requis pour ce parcours
RTLPrep ; ils ne sont donc pas installés automatiquement.

### Où les outils sont-ils placés ?

Par défaut, ils sont installés sans privilège administrateur dans :

```text
~/.local/share/rtlprep/toolchains/
  oss-cad-suite-2026-11-18/oss-cad-suite/bin/
  slang-v12.1/bin/
  activate.sh
```

L'activation ajoute les exécutables épinglés au `PATH` **sans modifier les
anciennes installations**. Si tu possèdes déjà un Verilator 5.008, il reste
présent sur le disque : après `source activate.sh`, le Verilator de la suite
est prioritaire. Le script garde `.venv/bin` avant l'interpréteur Python livré
avec OSS CAD Suite, pour que cocotb et le MCP utilisent le bon environnement.

**Important** : le script ne peut pas modifier l'environnement de son terminal
parent. Il faut effectuer les deux commandes `source` ci-dessus dans chaque
nouvelle session ou ajouter ces lignes manuellement dans ton profil shell si tu
veux le faire de façon permanente. Après modification du `PATH`, **relancer
Codex** pour qu'il redémarre les serveurs MCP héritant de cet environnement.

## Vérifier, mettre à jour ou voir les nouvelles versions

```bash
python scripts/rtlprep_env.py --check           # aucun réseau, aucune écriture
python scripts/rtlprep_env.py --verify-lock     # cohérence lock ↔ pyproject
python scripts/rtlprep_env.py --check-updates   # interroge les releases GitHub, n'installe rien
python scripts/rtlprep_env.py --update          # synchronise les pins du projet + extras Python
```

`--install` n'écrase pas un outil déjà installé avec la même empreinte ;
`--update` **n'installe jamais automatiquement une release non testée**.
La commande synchronise les versions verrouillées présentes dans le dépôt,
recrée la chaîne d'outils si ses empreintes sont modifiées et permet à `pip`
d'actualiser les dépendances conformément au `pyproject.toml`.

Lorsqu'une future version de Verilator, slang ou OSS CAD Suite devient
nécessaire, il faut mettre à jour dans **une PR revue et testée** :

- les versions, noms d'archives et SHA-256 de `toolchain.lock.json` ;
- si nécessaire les dépendances de `pyproject.toml` ;
- les versions utilisées par les workflows `.github/workflows/` ;
- les tests d'intégration réelle slang/MCP/cocotb/SBY/EQY.

La somme SHA-256 doit provenir de l'asset officiel sélectionné : il ne faut pas
remplacer un hash par la valeur d'un téléchargement non vérifié. Les commandes
`--check-updates` et `--update` sont **deux opérations distinctes**.

## Validation réelle des fonctionnalités

Après installation et activation :

```bash
verilator --version
slang --version
yosys -V
sby --version
eqy --version
z3 --version

python -m pytest -q tests/test_rtlprep_env.py
python -m rtlprep simulate examples/counter/design.json --out reports/sim-counter
python -m rtlprep formal examples/counter/design.json --out reports/formal-counter
```

Les deux dernières commandes exécutent **de vrais outils EDA** et produisent de
vrais rapports, pas une simulation fictive du bootstrap. Un statut de preuve
`passed`, `failed` ou `inconclusive` dépend des propriétés du banc, pas de la
présence des exécutables. Un échec d'installation ou de vérification n'est jamais
converti en succès silencieux.

Le serveur MCP lui-même reste **en lecture seule** et n'exécute aucune
installation, aucune simulation et aucune preuve.

# Utiliser le vrai compilateur slang (Linux / WSL2)

Cette page explique **pourquoi** RTLPrep a besoin d'un compilateur existant, comment
le valider et ce que les tests garantissent.

## Le problème découvert par les premiers tests réels

Le 19 novembre 2026, RTLPrep a été lancé dans GitHub Actions avec la **release
slang v12.1 (12.1.0+42710c788)**.

- Le compteur simple a été analysé correctement.
- Le circuit contenant deux instances de `leaf` a révélé un échec :
  `AST slang : Instance sans nom ou corps valide`.
- Le schéma simplifié utilisé par les tests unitaires ne reproduisait pas ce cas.

**Cause :** slang met en cache par défaut certains corps d'instance répétée.
La sérialisation JSON évite ainsi de répéter tous les membres d'une même
instance canonique. Le parseur RTLPrep v0.1, qui exige un dictionnaire complet
`InstanceBody`, ne sait pas encore suivre les références issues de ce cache.

**Solution transitoire dans `rtlprep/runner.py` :**

```python
cmd = [
    "slang", "--disable-instance-caching",
    "--ast-json", str(ast_path), "--ast-json-source-info",
    *common_slang_args(d),
]
```

Le compilateur est toujours **slang** ; notre code ne refait pas le parsing.
Avec ce drapeau, les instances d'un même module sont exportées avec leurs
corps complets pour notre extracteur JSON.

**Compromis :** cette option peut accroître le temps et la mémoire d'élaboration
d'un grand SoC. Lors de la phase « index structurel » nous chercherons une
solution plus efficace, compatible avec les références d'instance en cache ou
reposant sur les bindings `pyslang`.

## Version de référence

La CI télécharge une archive de la release officielle :
`v12.1/slang-linux-x86_64.tar.gz`.

Le workflow [slang-integration.yml](../.github/workflows/slang-integration.yml)
installe cette version sur un runner Ubuntu 24.04 et exécute la commande
`slang --version` afin de vérifier le binaire réellement utilisé.

Lien de la release : <https://github.com/MikePopoloski/slang/releases/tag/v12.1>.

### Installation manuelle sur Linux x86_64 / WSL2

Dans un terminal Linux, télécharge la release officielle depuis GitHub
(version fixée pour reproduire la CI) :

```bash
mkdir -p ~/tools/slang-v12.1
curl -fL --retry 3 \
  https://github.com/MikePopoloski/slang/releases/download/v12.1/slang-linux-x86_64.tar.gz \
  -o /tmp/slang-v12.1.tar.gz
tar -xzf /tmp/slang-v12.1.tar.gz -C ~/tools/slang-v12.1
find ~/tools/slang-v12.1 -type f -name slang -print
```

Si le binaire se trouve par exemple dans `~/tools/slang-v12.1/bin/slang`,
tu peux ajouter ce dossier au `PATH` :

```bash
export PATH="$HOME/tools/slang-v12.1/bin:$PATH"
slang --version
```

**Adapter ce chemin** à celui renvoyé par `find`. Si la disposition de l'archive
diffère, ne présume pas que le binaire se trouve dans `bin/`.

Pour Linux ARM, macOS ou Windows natif, voir la page officielle
[Building & Installation](https://www.sv-lang.com/building.html).

## Exécuter les tests

À la racine du dépôt :

```bash
python -m pip install -e '.[dev]'
python -m rtlprep doctor
python -m pytest -q tests/test_starter.py tests/test_analysis.py
python -m pytest -vv -rs tests/test_integration_slang.py
```

L'avant-dernière commande valide les **tests unitaires sans compilation**.
La dernière exécute le vrai compilateur slang **s'il est installé** ; sinon pytest
affiche `SKIPPED`. En CI, un job installe slang avant l'exécution, et vérifie
aussi sa présence via `slang --version`.

Pour observer le résumé :

```bash
python -m rtlprep analyze examples/hierarchy/design.json --out reports/hierarchy
python -m json.tool reports/hierarchy/design_summary.json
```

L'exemple doit contenir exactement trois chemins :

```text
hierarchy_top
hierarchy_top.first
hierarchy_top.second
```

Les deux instances `first` et `second` sont des occurrences du **même
module `leaf`**, mais ce sont deux objets distincts dans la hiérarchie.

## Ce que la CI vérifie réellement

1. Le **compilateur réel** peut élaborer le compteur.
2. Les ports `clk`, `rst_n`, `enable` et `count` sont reconnus,
   avec leur direction.
3. Les **trois chemins d'instance** du circuit multi-modules sont corrects.
4. Les ports de chaque instance `leaf` sont reconnus.
5. Les tests unitaires Python continuent de passer.

Ce n'est pas encore une validation des macros complexes, des packages, des
types paramétrés, des connexions entre tous les signaux, ni des circuits RISC-V.
Aucun fan-in/fan-out n'est encore calculé.

## Ce qu'on développera ensuite

Un index structurel versionné, associant chaque instance, port et signal à son
**chemin hiérarchique** et à sa **provenance dans le code source**. Cette
approche évitera de confondre la définition du module avec ses différentes
occurrences. Les tests devront continuer à se baser sur le compilateur réel,
et pas seulement sur de petites fixtures JSON artificielles.

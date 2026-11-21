# Phase H — Comprendre la structure des expressions RTL (PR #19)

## Objectif : distinguer des circuits au même graphe de dépendances

Sur le circuit éducatif `secure_csr` autorisé, le contrôle d'écriture
standard contient `write_i && machine_mode_i && !debug_locked_i`, alors que
la variante de test contient `write_i && (machine_mode_i || !debug_locked_i)`.
Ces deux versions font intervenir les mêmes signaux : les arêtes de
dépendances peuvent être identiques.

La PR #19 **préserve les opérateurs et leur imbrication** depuis le JSON
élaboré par **slang**, au lieu de se contenter des dépendances.
Elle n'évalue pas ces expressions : ni simulation, ni SAT/SMT, ni preuve de
correction, ni recherche autonome de failles.

## Périmètre implémenté

`rtlprep deps` ajoute un bloc `expressions` au
`rtl_dependencies.json` existant. Pour chaque
`ContinuousAssign` dont la cible est un simple `NamedValue`,
RTLPrep conserve un arbre borné de la partie droite :

- `binary` : `op`, `left`, `right` directement issus de slang ;
- `unary` : `op`, `operand` ;
- `signal` : chemin d'instance complet et nom de déclaration ;
- `literal` ou `constant_reference`, quand identifiable ;
- `conversion` : nœud de conversion, sans effacer son existence ;
- `unsupported` : construction non traitée ou limite atteinte.

Les opérateurs sont affichés comme **noms de slang** (par exemple
`LogicalAnd`, `LogicalOr`, `LogicalNot`, `BinaryAnd`), et non
reconstruits par recherche de texte. Chaque expression contient la cible,
la référence au code source si disponible et `coverage`.

Les résultats sont plafonnés à 2000 affectations par graphe,
96 nœuds et 12 niveaux par expression. Les chaînes de constantes et
les noms AST non pris en charge sont bornés.

**Limites actuelles** : pas d'interprétation des affectations
procédurales (`always_*`), ni de `case`, `?:`, concaténations
et sélections de bits. Le compteur `procedural_blocks_skipped`
et `partial_expressions` rendent ces limites visibles ; une sortie
MCP vide n'indique pas forcément une absence de logique.

## Test sur Debian WSL

Depuis la branche PR #19, avec `slang` et la venv actifs :

```bash
cd ~/projets/scientist_parseur
git fetch origin
git switch feat/rtl-expression-ast-mcp
source .venv/bin/activate
python -m pytest -q tests/test_expressions.py
python -m rtlprep deps examples/hierarchy/design.json --out reports/hierarchy
```

Pour inspecter les deux variantes du laboratoire CSR de test :

```bash
python -m rtlprep deps examples/security_csr/design.json --out reports/csr-good
python -m rtlprep deps examples/security_csr/buggy_design.json --out reports/csr-buggy
python -m pytest -q tests/test_integration_slang.py -k csr_operator
```

Les deux fichiers `rtl_dependencies.json` doivent conserver les mêmes
relations de données mais des arbres d'opérateurs distincts pour
`secure_csr.write_accepted_o`.

## Interrogation depuis Codex

La connexion MCP créée précédemment peut être conservée ; elle lit
`reports/hierarchy/rtl_dependencies.json` comme avant. Pour charger
le nouveau snapshot, il faut cependant **régénérer le graphe et
redémarrer Codex** :

```bash
codex mcp list
codex
```

Demander à Codex :

> Appelle `rtl_capabilities`, puis `rtl_expressions` sur
> `hierarchy_top.first.status` et `hierarchy_top.second.status`.
> Présente les arbres syntaxiques, la provenance et les limites de couverture,
> sans lire le RTL directement et sans lancer les EDA.

Le MCP fournit **12 outils**, dont le nouveau
`rtl_expressions(signal, limit=20, offset=0)` (pagination 1..100).
Il ne modifie aucun fichier. Codex peut, sous des permissions distinctes,
créer ensuite un rapport Markdown comme précédemment.

## Tests de non-régression

- `tests/test_expressions.py` : mêmes dépendances mais
  `LogicalAnd` contre `LogicalOr`, cas inconnu, couverture procédurale,
  paginations et anciens graphes.
- `tests/test_integration_slang.py` : analyse des deux vrais fichiers
  CSR avec le binaire slang et comparaison des arbres.
- `scripts/test_mcp_stdio.py` : appel `rtl_expressions`
  via un **vrai client MCP stdio** dans GitHub Actions.

Cette phase représente la **syntaxe élaborée** d'un sous-ensemble RTL.
Les prochaines phases devront modéliser les gardes des branches,
l'écriture par bits/tranches, le temps et les registres avant de
prétendre expliquer le comportement fonctionnel complet.

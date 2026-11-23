# PR #29 — Déclarations et identités dans les generate actifs

## Problème reproduit

Dans la campagne [PR #28](unknown-designs-validation.md), le module
tiers `axis_register` (version épinglée de `alexforencich/verilog-axis`)
était élaboré correctement par slang 12.1, mais RTLPrep n'émettait
**aucune arête** et rapportait **22 avertissements**.

Le diagnostic de l'AST réel a identifié la cause : avec
`REG_TYPE=2`, les registres de buffers et un net sont déclarés
dans `GenerateBlock genblk1`. `build_index` ne collectait que les
`Variable` et `Net` immédiatement dans `InstanceBody.members`.
Les affectations dans `genblk1` étaient bien visitées, mais
`build_dependency_graph` rejetait leurs références absentes de l'index.

## Correctif

- Pour chaque `GenerateBlock` **actif et nommé**, collecter les
  `Variable`/`Net` dans l'instance propriétaire, avec le chemin
  qualifié `axis_register.genblk1.m_axis_tdata_reg`.
- Conserver les chemins historiques des ports et signaux directs
  (`axis_register.m_axis_tdata`) ; les scopes generate ne sont **pas**
  des instances matérielles supplémentaires.
- Construire une table temporaire `(instance, addr) → chemin signal`
  en reparcourant l'**AST de la même élaboration**. Les identifiants
  sémantiques de slang servent aux lectures et aux cibles
  d'affectations du graphe et des expressions. Ils **ne sont pas
  persistés** dans les rapports JSON et ne sont pas supposés stables
  entre exécutions.
- Un ID inconnu ou ambigu ne retombe **jamais** sur un homonyme
  connu lorsque la déclaration possède une adresse AST. Les AST de
  tests synthétiques plus anciens, sans adresses, conservent un
  fallback limité et sans ambiguïté.
- `rtl_find_signals` conserve le chemin complet des locaux générés ;
  `rtl_signal(instance_path, name="genblk1.reg")` permet une
  consultation sans collision. Les anciennes requêtes de signaux
  directs fonctionnent toujours.
- Les analyseurs `register_flow` et `bit_accesses` ne résolvent
  pas encore les locaux generate. Ils les **excluent** plutôt
  que de fusionner des homonymes et produire de faux candidats.

Le schéma des index et graphes reste `v1` : les objets de
signal collectés dans un scope portent des champs **additifs**
`path` et `scope`. Les outils n'ont pas de nouvelle interface
d'exécution d'EDA dans MCP.

## Portée et limites

Cette PR ne traite **pas** encore tous les `GenerateBlockArray`,
les scopes sans nom stable, les variables locales de fonctions,
les tableaux non déroulés, ou la résolution de tous les
événements `Timed` / `ImplicitEvent`. Une arête observée représente
une influence syntaxique potentielle, pas une preuve de comportement.

Les tests de symboles homonymes actifs et inactifs servent à
détecter une **fusion accidentelle de scopes**. On n'ajoute
aucune arête lorsque le préfixe `symbol` ne correspond à aucune
déclaration explicite du même AST.

## Tests

Test hermétique (sans EDA) des scopes, références inconnues,
homonymes, branches inactives et de l'index :

```bash
python -m pytest -q tests/test_generate_scope_symbols.py
```

Test **réel** sur le fichier tiers épinglé, trois spécialisations
`REG_TYPE=0`, `1` et `2` obtenues au moyen d'une petite instance
wrapper générée dans un dossier temporaire :

```bash
source .venv/bin/activate
source "$HOME/.local/share/rtlprep/toolchains/activate.sh"
python -m pytest -q -rs tests/test_generate_scope_real.py
```

Ce test nécessite la présence de
`upstream_unknown/verilog-axis/rtl/axis_register.v` à la révision
Git attendue par la PR #28. Il est marqué « skipped » si
slang ou les sources externes sont absents dans les tests
unitaires généraux ; le workflow externe exige, lui, sa
**réelle exécution**.

Pour régénérer la campagne complète après correctif :

```bash
python scripts/validate_unknown_rtl.py \
  --sources-root upstream_unknown --out reports/unknown-validation
```

Comparer les arêtes et warnings avec les valeurs historiques
de la #28 ; ne pas annoncer une couverture complète parce qu'un
graphe initialement vide comporte désormais des arêtes.

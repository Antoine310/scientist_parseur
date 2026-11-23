# PR #37 — Écritures de champs de structures RTL

## Problème à traiter

La PR #36 supporte les **lectures** de `MemberAccess` dans le graphe et
les expressions. Une écriture telle que `state.low <= data;`, en revanche,
était exclue des cibles de l'index d'expressions et du graphe.

Les champs SystemVerilog peuvent être des membres packed / unpacked,
des éléments de tableaux, des champs imbriqués et des portions d'un
signal dont la largeur dépend du type élaboré. Un décodeur qui connaît
uniquement le **nom** d'un champ ne peut pas déduire à coup sûr les bits
physiques correspondants.

## Modification conservatrice

1. Les cibles `MemberAccess` simples ou imbriquées conservent le
   `target_access` structuré de l'AST élaboré dans `expressions`.
   Le champ `target_write_scope` vaut
   `whole_signal_approximation`. `syntax_supported` exprime uniquement
   une forme syntaxique traitée, **pas** la complétude de l'écriture.
2. Le graphe résout **exclusivement par identité sémantique slang** le
   `NamedValue` de base. La RHS crée une arête `data` vers le signal
   entier, les gardes gardent leurs arêtes `control` et les événements
   explicites conservent leurs arêtes `event`.
3. Un avertissement stable signale
   `Écriture de membre : dépendance au signal entier (champs non localisés)`.
   Aucune arête au bit, couverture de champ, mapping packed ou valeur
   séquentielle de registre n'est affirmée.
4. Les sélections mélangeant `MemberAccess` et `ElementSelect` ou
   `RangeSelect` ne produisent **aucune sélection statique aplatie**.
   L'approximation est explicitement avertie.
5. Les jetons de membres malformés, les bases dont l'adresse slang ne
   correspond à aucun signal, les constantes prises pour cibles et les
   chaînes trop profondes ne sont pas silencieusement acceptées.

Les limites de l'analyse `bit_accesses` restent inchangées :
**affectations continues seulement** et sélections déjà prises en charge.
Les écritures de champs dans `always_ff`, `always_comb` ou `always`
ne sont pas encore mappées au niveau bit.

## Vérification réelle

La fixture RTLPrep
[`tests/fixtures/member_lvalue_pr37.sv`](../tests/fixtures/member_lvalue_pr37.sv)
contient une vraie structure `packed` avec un
`always_ff @(posedge clk or negedge rst_n)` et
`state.low <= d` sous garde `en`. Cette source est élaborée
par **slang v12.1** dans la CI, puis analysée par RTLPrep.
L'intégration vérifie :

- une arête `data` de `d` vers `state` et une arête
  `control` de `en` vers `state` ;
- un `target_access.kind=member_access` avec champ `low` ;
- l'avertissement de granularité ;
- aucune correspondance bit-à-bit inventée par `bit_accesses`.

Les tests synthétiques couvrent les membres imbriqués, les sous-sélections
sans mapping plat, les mauvais identifiants, les noms malformés et les
dépassements de profondeur. Ils sont complémentaires au test réel,
**pas** un oracle exhaustif du langage SystemVerilog.

La même CI élabore à nouveau le vrai
`compressed_decoder` d'`openhwfoundation/cva6`, commit
`742dc82a0c706e0a3bfb98b709fd3ee06d50d12a`, configuration
`cv32a6_imac_sv32`, avec **slang v12.1**. Ce décodeur n'exerce
pas lui-même la nouvelle écriture de membre ; il constitue une
**régression de non-dégradation**, pas une preuve nouvelle pour ce cas.

## Reproduction sous Debian/WSL

```bash
cd ~/projets/scientist_parseur
source .venv/bin/activate
source "$HOME/.local/share/rtlprep/toolchains/activate.sh"

python -m pytest -q -rs \
  tests/test_member_lvalue_pr37.py \
  tests/test_memberaccess_pr36.py \
  tests/test_cva6_compressed_decoder.py
```

Si `upstream_cva6` est absent, le test spécifique au
**checkout CVA6 épinglé** est ignoré localement ; en revanche, la
fixture SystemVerilog de la #37 est dans le dépôt et son test utilise
le slang local installé. Le workflow GitHub vérifie également le vrai
CVA6 en sparse checkout.

## Limites et suites

La résolution d'une écriture de champ au niveau signal est **une
sur-approximation**. Le graphe ne dit pas si l'écriture modifie
uniquement un champ, ni quels autres champs sont conservés en mémoire.
Le module de `register_flow` conserve son périmètre
`always_ff_syntactic_paths_only` : aucune preuve de maintien,
priorité NBA, latence ou transition n'est inférée.

La couverture du design reste `not_measured` et aucune accuracy
n'est revendiquée sans oracle indépendant. L'analyse des
**accès aux bits dans les processus** pourra être une PR séparée,
avec prise en compte explicite des gardes et de la granularité
des écritures.

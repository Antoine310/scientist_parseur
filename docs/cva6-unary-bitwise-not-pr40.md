# PR #40 — Distinguer la provenance d'un bit de sa valeur après `~`

## Situation et empilement

Cette PR est **empilée sur la PR #39**, à partir de
`feat/typed-bitsegments-and-replication-v1`, car #39 n'était pas encore
fusionnée à la création de #40. Ne pas fusionner #40 dans `main`
avant #39 et une revue explicite ; après la fusion de #39, changer
la base de #40 vers `main`.

La PR #39 a mesuré **52 enregistrements** de `bit_accesses` sur le
vrai `compressed_decoder` CVA6 : **51 segments RHS positionnés
syntaxiquement**, et **un `partial`**, de raison
`unsupported_rhs_UnaryOp`.

L'analyse du fichier officiel épinglé et du vrai AST slang v12.1
localise le cas :

```systemverilog
// openhwfoundation/cva6, core/compressed_decoder.sv, ligne 719
~instr_i[15]
```

Il s'agit de l'opérateur `UnaryOp(op=BitwiseNot)` sur un
`ElementSelect` de type `logic`, lui-même de type `logic`.
L'affectation qui contient cette concaténation commence ligne 708.

## Sémantique retenue

Pour une négation bit-à-bit `~expression`, la **position de chaque bit
dans la sortie** correspond à celle de son opérande. En revanche,
sa **valeur n'est pas égale** à celle de son opérande : elle est
inversée (selon la sémantique 4 états de l'opérateur), et RTLPrep
ne calcule pas les valeurs.

Nous représentons donc, dans chaque segment réellement inversé :

```json
{
  "source": "rtlprep_cva6_compressed_decoder.decoder_i.instr_i",
  "selection": {"kind": "bit", "index": 15},
  "rhs_lsb": 7,
  "rhs_msb": 7,
  "value_transform": "bitwise_not"
}
```

**Remarque :** cet extrait expose le port **interne**
`decoder_i.instr_i` (relié à l'entrée du wrapper dans le graphe),
et non directement `rtlprep_cva6_compressed_decoder.instr_i`.
Les offsets RHS de l'exemple sont vérifiés sur le véritable AST
et les tests sur l'artefact épinglé. Le `value_transform` est la distinction
essentielle : ce segment n'est **pas** une copie directe.

L'opération n'est reconnue que si :

1. L'AST est `UnaryOp` avec `op=BitwiseNot`, exactement.
2. Le nœud et son opérande ont chacun un type scalaire ou packed
   unidimensionnel reconnu par `_packed_width`.
3. Les deux largeurs sont **identiques** et correspondent à la
   somme des segments de l'opérande.
4. Les identités de référence, les positions, la profondeur et les
   budgets de segments sont déjà validés.
5. Aucun autre `value_transform` n'est déjà présent dans un
   segment de l'opérande (les compositions et simplifications restent
   hors du périmètre).

Les autres opérations comme `!x` (`LogicalNot`),
`&x` (réduction), `-x` (négation arithmétique), ainsi que les
formes malformées, les types opaques, indices dynamiques et
identités non résolues restent **`partial`**. Un type ou une
valeur `constant` non prouvé ne contourne jamais ce contrôle.

Une négation sur une concaténation est traitée **par segment**,
en conservant l'ordre et les positions d'origine. Les segments
non inversés conservent leur format précédent, sans nouvelle
propriété.

## Mesure sur CVA6 officiel épinglé

Source officielle : `openhwfoundation/cva6`, commit exact
`742dc82a0c706e0a3bfb98b709fd3ee06d50d12a`,
configuration `cv32a6_imac_sv32`, `slang v12.1`,
avec vérification Git du commit et des cinq blobs source.

| `bit_accesses` | #39 | #40 |
| --- | ---: | ---: |
| Affectations inspectées | 93 | **93** |
| Enregistrements observés | 52 | **52** |
| Positionnements syntaxiques sous sémantique déclarée | 51 | **52** |
| `partial` | 1 | **0** |
| Segments avec inversion explicitement signalée | 0 | **1 dans la concaténation ciblée** |

Le graphe de dépendances au niveau signal ne change pas :
**12 nœuds, 13 arêtes, 0 avertissement**. Les cinq traces
`fanin` des sorties remontent à `instr_i` sans troncature
dans les limites du test.

Si la synthèse de couverture indique
`no_reported_limits_within_scopes`, cela signifie uniquement
**qu'aucune limite n'a été signalée dans les index effectivement
exécutés sur ce module**. Ce n'est **pas** une preuve de couverture
intégrale du design ni de correction du décodage :
`design_coverage=not_measured`,
`functional_correctness=not_tested`,
`accuracy=not_measured_without_independent_exhaustive_oracle`.

## Validation indépendante de ce cas précis

La fixture entièrement écrite pour RTLPrep
`tests/fixtures/unary_bit_pr40.sv` est élaborée par le
**vrai slang v12.1**, pas par un parseur simulé.
Elle contient `~instr_i[15]`, `~instr_i[3:0]`,
une concaténation avec un seul bit inversé, ainsi que
`!instr_i[3]` et la réduction `&instr_i[7:4]`
qui doivent rester `partial`.

Les tests hermétiques vérifient :

- La source, la sélection, les positions RHS/LHS et
  `value_transform=bitwise_not` pour chaque segment inversé.
- Le fait qu'un segment non inversé ne reçoive pas le marqueur.
- Le rejet des autres opérateurs unaires, des compositions
  non modélisées, des largeurs changées ou inconnues,
  des adresses sémantiques falsifiées et des indices dynamiques.
- Le maintien d'une couverture du design `not_measured`
  malgré la disparition d'un enregistrement partiel.

## Reproduction Debian / WSL2

```bash
cd ~/projets/scientist_parseur
git status --short
git fetch origin
git switch feat/cva6-unaryop-bit-scope-v1
git pull --ff-only

source .venv/bin/activate
source "$HOME/.local/share/rtlprep/toolchains/activate.sh"

python -m pytest -q -rs \
  tests/test_unary_bit_pr40.py \
  tests/test_typed_segments_pr39.py \
  tests/test_procedural_bitaccess_pr38.py \
  tests/test_bit_accesses.py \
  tests/test_cva6_compressed_decoder.py
```

Le test du vrai CVA6 reste ignoré sur WSL2 en l'absence
du checkout officiel épinglé `upstream_cva6` ; la CI
réalise ce sparse checkout et vérifie les empreintes.

Le dossier utilisateur `docs/agent-reports/` est non suivi :
il ne doit pas être supprimé ni modifié.

## Après #40

Il faut désormais privilégier la **validation par des oracles
indépendants** et un module CVA6 davantage séquentiel avant
d'extrapoler les progrès du décodeur compressé à tout le cœur.
Un compteur de segments « pris en charge » n'est pas une
métrique d'accuracy fonctionnelle.

# PR #39 — Largeurs explicites, constantes sémantiques et réplications dans l'AST slang

## Point de départ : le vrai CVA6

La PR #38 avait étendu `bit_accesses` aux processus combinatoires et
séquentiels. Sur le `compressed_decoder` de `openhwfoundation/cva6`,
commit exact `742dc82a0c706e0a3bfb98b709fd3ee06d50d12a`,
configuration `cv32a6_imac_sv32`, **52 expressions sélectionnées**
étaient désormais visibles mais **toutes partielles** :

- 42 `source_width_unknown` ;
- 9 `unsupported_rhs_Replication` ;
- 1 `unsupported_rhs_Conversion`.

L'examen des **vrais objets de l'AST élaboré par slang v12.1** a
montré notamment des champs `NamedValue.type = logic[6:0]` pour
les opcodes du décodeur et des nœuds
`Replication(count=IntegerLiteral(6), concat=Concatenation(...))`.

## Ce que la #39 peut justifier

Dans `rtlprep.bitaccess` :

1. **Source RTL entière** : lorsque le nom est résolu par l'identité
   sémantique de la déclaration et qu'un type élaboré scalaire
   `logic`/`bit` ou un unique range packed explicite est présent,
   l'analyseur connaît la **largeur du segment RHS**. Il le conserve
   sous `selection.kind=whole` : **aucun offset de bit à l'intérieur
   de la source n'est inféré**.
2. **Constante de package / énumération** : un `NamedValue` dont
   l'adresse **et le nom** correspondent à une déclaration
   `Parameter` ou `EnumValue` dans le même AST, et dont la
   largeur `logic[N:M]`/`bit[N:M]` est explicite, donne un
   segment `constant_reference` sans arête de signal runtime.
   L'identifiant d'adresse slang n'est pas conservé dans la sortie.
3. **Réplication** : `Replication` est reconnue uniquement avec
   un compte `IntegerLiteral` explicite et une vraie
   `Concatenation`; les segments de l'unité sont répétés en ordre,
   avec bornes `MAX_SEGMENTS=32`, `MAX_WIDTH=1024`
   et limite de profondeur. Les indices dynamiques, les comptes
   non littéraux et les débordements restent `partial`.
4. **Conversions** : `Conversion` / `SignedConversion` sont
   transparents seulement si l'AST expose un type packed reconnu
   pour l'expression et son opérande, si leurs largeurs sont égales,
   et si la taille reconstruite des segments correspond exactement.
   Sinon elles restent `partial`. Les transformations arithmétiques,
   unaires non reconnues et X/Z ne sont pas évalués.

### Un choix de sécurité important

Un type affiché par slang comme une **référence à un typedef**, par
exemple `typed_segments_pr39.opcode_t`, n'est **pas** assimilé à
`logic[2:0]` par son nom. La taille du littéral initialisant une
énumération n'est pas nécessairement la taille du type de l'énumération.

La fixture réelle conserve donc **exprès** une affectation
`enum_alias_o = {5'b0, OP_A}` classée `partial` lorsque
la largeur exacte du type alias n'est pas résolue. Une
`localparam logic [2:0]` explicite, en revanche, peut être
positionnée après vérification de son identité.

C'est volontaire : pas de valeur inventée, pas de résolution
de structure packed à partir d'un texte de type ambigu.

## Bilan mesuré : même décodeur CVA6 et même configuration

| Sortie `bit_accesses` | PR #38 | PR #39 |
| --- | ---: | ---: |
| Affectations analysées | 93 | **93** |
| Enregistrements bit sélectionnés | 52 | **52** |
| Enregistrements positionnés syntaxiquement | 0 | **51** |
| Enregistrements `partial` | 52 | **1** |
| Limite restante | largeur / replication / conversion | **`unsupported_rhs_UnaryOp`** |

Le graphe général reste inchangé : **12 nœuds, 13 arêtes, 0
avertissement**, avec les 5 sorties reliées à `instr_i` dans
les traces `fanin` bornées et non tronquées.

Ces résultats signifient qu'on sait désormais **positionner
syntaxiquement de nombreux segments RHS de ce module**. Ils ne
prouvent ni la valeur d'une instruction décodée, ni la couverture
intégrale du décodeur, ni des garanties temporelles :
`design_coverage=not_measured`,
`functional_correctness=not_tested`,
`accuracy=not_measured_without_independent_exhaustive_oracle`.

## Validation supplémentaire indépendante du CVA6

La fixture **propriété de RTLPrep**
`tests/fixtures/typed_segments_pr39.sv` est élaborée par le
**vrai slang v12.1**. Elle contient des sources et paramètres
typés explicitement, des sélections de bits, une réplication
bornée et un alias d'énumération volontairement non résolu.

Les tests hermétiques couvrent aussi les identités de déclarations
falsifiées, les `constant` présents sur un signal runtime, les
types inconnus, les conversions de largeur différente et les
réplications malformées / dépassant les budgets. Les vérifications
du vrai `rxuart` et des trois autres corpus RTL externes
restent activées en CI.

## Reproduction dans WSL2

```bash
cd ~/projets/scientist_parseur
git status --short
git fetch origin
git switch feat/typed-bitsegments-and-replication-v1
git pull --ff-only

source .venv/bin/activate
source "$HOME/.local/share/rtlprep/toolchains/activate.sh"

python -m pytest -q -rs \
  tests/test_typed_segments_pr39.py \
  tests/test_procedural_bitaccess_pr38.py \
  tests/test_bit_accesses.py \
  tests/test_member_lvalue_pr37.py \
  tests/test_cva6_compressed_decoder.py
```

Le test sur le **vrai CVA6** sera ignoré si le checkout
`upstream_cva6` épinglé est encore absent localement. La CI le
récupère en sparse checkout et en vérifie les empreintes Git,
sans recopier les sources tierces dans le dépôt.

Ne pas toucher au dossier utilisateur non suivi
`docs/agent-reports/`.

## Prochaine cible

Examiner le `UnaryOp` restant sur le CVA6 et déterminer s'il
préserve les positions de bit ou transforme les valeurs. Une
opération non positionnelle doit rester `partial` jusqu'à une
justification sémantique indépendante ; le nombre de cas partiels
n'est pas une métrique d'accuracy.

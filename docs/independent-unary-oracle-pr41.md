# PR #41 — Première validation indépendante des positions et inversions de bits

## Pourquoi la PR #41 existe

Après les PR #39 et #40, l'analyseur `bit_accesses` déclare **52 sur
52 segments syntaxiquement positionnés** sur le décodeur compressé
officiel CVA6, dont une inversion `BitwiseNot` explicitement signalée
par `value_transform=bitwise_not`.

Un compteur de segments reconnus et une réussite des tests AST ne
prouvent pas que le RTL effectue réellement les opérations attendues.
Nous ajoutons donc **une seconde méthode, indépendante de l'AST slang
et de la logique de `bitaccess.py`**, pour contrôler une famille
restreinte d'opérations observées dans le décodeur.

## Expérience indépendante, sans réécrire un simulateur

Le circuit RTLPrep `tests/fixtures/unary_bit_pr40.sv` sert de **DUT**
(Design Under Test). La CI utilise **Verilator 5.040** et **cocotb
2.0.1** — les mêmes outils et versions que la suite de simulation déjà
épinglée dans le dépôt.

Le banc `rtlprep/sim_tests/unary_bit_oracle.py` produit les résultats
attendus **directement à partir d'un contrat mathématique
écrit manuellement**, sans importer ni appeler `rtlprep.bitaccess`,
`build_dependency_graph` ou `pyslang`. Il compare les **valeurs
effectivement observées** sur les ports de simulation.

| Sortie | Référence Python, sur `instr` entier de 16 bits |
| --- | --- |
| `bit_o` | 0 si bit 15=1, sinon 1 |
| `mix_o` | octet bas de `instr`, avec uniquement le bit 4 inversé |
| `wide_o` | les quatre bits bas inversés (`xor 0xF`) |
| `logical_o` | `en` et bit 3 égal à 0 |
| `reduction_o` | `en` et bits 7:4 tous à 1 |

Trois tests avec des entrées déterministes :

- **34 stimuli dirigés** : 17 motifs significatifs avec `en=0/1`.
- **1 024 stimuli en balayage** : chacun des 256 octets bas avec
  bit 15=0/1 et `en=0/1` ; les bits intermédiaires varient
  de manière reproductible.
- **256 stimuli pseudo-aléatoires** : graine fixe `0x41CA6`.

**Total : 1 314 stimuli de simulation** pour chacun des deux RTL
testés (avec d'éventuelles répétitions). Ce n'est pas l'ensemble
des 131 072 couples possibles `instr_i` / `en`, ni un oracle
4 états pour `X/Z`.

## Mutation négative : un test qui saurait passer à tort ne suffit pas

Une seconde fixture `tests/fixtures/unary_bit_pr41_mutant.sv` possède
**le même top et les mêmes ports**, mais une faute volontaire
et isolée :

```systemverilog
// RTL correct
bit_o = ~instr_i[15];

// Mutant intentionnellement erroné
bit_o = instr_i[15];
```

L'**exact même oracle cocotb** doit réussir sur le circuit correct
et **échouer sur le mutant**, avec une assertion indiquant le
port `bit_o`. Le workflow ne conclut à une réussite de la PR que si :

1. Le circuit correct donne **3 tests passés / 0 échec / 0 ignoré**.
2. Le mutant provoque un code de sortie non nul attendu,
   un rapport `failed` et **au moins un échec cocotb réel**.
3. Le XML xUnit est présent, contient un `failure`, et le message
   ou les logs montrent **`port=bit_o`** ; le test ne doit pas
   être déclaré valide à cause d'une erreur arbitraire de compilation.
4. Les empreintes source du bon et du mutant sont différentes.
5. Les anciens tests de simulation (compteur et FSM) restent actifs.

Le workflow publie les **rapports JSON, XML et logs** des deux
exécutions, y compris lorsque des étapes échouent.

## Relation avec les segments de RTLPrep

Une suite distincte `tests/test_unary_oracle_pr41.py` utilise
**slang v12.1** sur la même fixture, puis compare les enregistrements
`bit_accesses` à des positions **auditée indépendamment** :

- `bit_o` : entrée `instr_i[15]`, un bit RHS, inversion signalée.
- `mix_o` : `instr_i[7:5]` en RHS 7:5, `instr_i[4]`
  inversé en RHS 4, et `instr_i[3:0]` en RHS 3:0.
- `wide_o` : `instr_i[3:0]` marqué entièrement inversé.
- `logical_o` et `reduction_o` : formes unaires encore
  **`partial`**, sans correspondances de bits inventées.

Ces deux chemins sont complémentaires : **simulation du comportement
réel** d'un côté, **audit des métadonnées statiques** de l'autre.

## Ce qui a vraiment été validé

Les deux opérations d'analyse et de simulation sur la fixture sont
indépendantes de la logique principale de RTLPrep, mais elles portent
sur **un petit module RTLPrep volontairement représentatif**.
La PR #41 **ne simule pas le décodeur compressé complet de CVA6**,
ni toutes les configurations ou les longueurs de séquence.

La CI continue de réélaborer le décodeur **OpenHW CVA6 réel** (commit
`742dc82a0c706e0a3bfb98b709fd3ee06d50d12a`, configuration
`cv32a6_imac_sv32`) avec slang v12.1. Il s'agit d'une **non-régression
statique** : 12 nœuds, 13 arêtes, 0 avertissement, 52 segments
syntaxiquement positionnés, aucun `partial` dans l'index bit de ce
module. Cela ne mesure toujours pas l'exactitude globale.

Ainsi, `design_coverage=not_measured`,
`functional_correctness=not_tested` **pour le CVA6 complet**,
et `accuracy=not_measured_without_independent_exhaustive_oracle`
restent des déclarations appropriées.

## Reproduction sur WSL2

```bash
cd ~/projets/scientist_parseur
git status --short
git fetch origin
git switch test/independent-unary-bit-oracle-pr41
git pull --ff-only

source .venv/bin/activate
source "$HOME/.local/share/rtlprep/toolchains/activate.sh"

python -m pytest -q -rs tests/test_unary_oracle_pr41.py
python -m rtlprep simulate tests/fixtures/unary_bit_pr41_good_design.json \
  --out reports/pr41-unary-good --timeout 180
```

Pour le **contrôle négatif**, la commande ci-dessous doit terminer
avec **code 2**, car la simulation trouve une erreur intentionnelle ;
cette sortie non nulle est **attendue**, contrairement à une erreur
sur le circuit correct :

```bash
python -m rtlprep simulate tests/fixtures/unary_bit_pr41_mutant_design.json \
  --out reports/pr41-unary-mutant --timeout 180
```

La simulation locale exige `cocotb==2.0.1`, `make`, `g++` et
**Verilator 5.036 ou plus récent** ; la CI épingle 5.040.
Si ces outils ne sont pas présents, la simulation n'est pas
considérée comme validée. L'absence de `upstream_cva6`
provoque seulement un skip du **test d'intégration CVA6**, non
des deux simulations RTLPrep.

Ne pas supprimer ni modifier `docs/agent-reports/` (dossier
local non suivi).

## Suite logique

Étendre l'oracle indépendant à une portion **réelle et identifiable**
de l'OpenHW CVA6, avec comparaisons entre le RTL officiel simulé et
les seules relations statiques que RTLPrep prétend connaître. La
validation doit inclure des contrôles négatifs et des informations
de configuration explicites, avant toute affirmation d'exactitude.

# PR #17 — Premier laboratoire de sécurité matérielle avec RTLPrep

> **Objectif :** passer de « RTLPrep construit un graphe de signaux » à
> « RTLPrep aide à **vérifier une propriété de sécurité explicite** ».
> Le circuit est **synthétique, volontairement vulnérable**, et sert
> exclusivement à un exercice contrôlé. **Ce n'est pas une vulnérabilité
> trouvée dans le vrai CV32E40P ni une démonstration qu'un agent IA la
> découvre seul.**

Ce tutoriel est le prolongement de la
[feuille de route](roadmap.md), des
[preuves SBY](preuves-formelles-sby.md),
[tests cocotb](simulation-cocotb-verilator.md)
et des [comparaisons EQY](equivalence-eqy.md).

## 1. Quel scénario de sécurité ?

Imaginons un **registre de configuration protégé** d'une machine
RISC-V simplifiée. La valeur peut être écrite seulement si :

1. le logiciel demande une écriture : `write_i=1` ;
2. le processeur est en **mode machine privilégié** :
   `machine_mode_i=1` ;
3. la politique de verrouillage interdit l'accès quand
   `debug_locked_i=1`.

Le contrat est donc :

```systemverilog
write_accepted_o = write_i && machine_mode_i && !debug_locked_i;
```

La sortie `value_o[7:0]` garde son ancienne valeur quand
la tentative d'écriture n'est pas autorisée. Elle est remise
à zéro par `rst_n=0`, même sans front montant d'horloge.

**Ce n'est pas le modèle exhaustif d'un CSR RISC-V réel** :
dans un SoC, la sécurité dépend aussi du bus, de la protection
mémoire, des modes debug, de l'authentification, des erreurs
de protocole et de l'implémentation physique.

## 2. Le bug introduit délibérément

Trois variantes se trouvent dans
[`examples/security_csr/`](../examples/security_csr/) :

- **`secure_csr.sv`** : contrat correct.
- **`secure_csr_refactored.sv`** : logique réorganisée,
  censée conserver exactement le comportement.
- **`secure_csr_buggy.sv`** : erreur volontaire dans
  le prédicat d'autorisation.

⚠️ **Spoiler — nature du bug :**

```systemverilog
// CORRECT : privilégier les conditions cumulatives.
write_i && machine_mode_i && !debug_locked_i

// VULNÉRABLE : le debug déverrouillé contourne le privilège machine.
write_i && (machine_mode_i || !debug_locked_i)
```

Pour `write_i=1`, `machine_mode_i=0` et
`debug_locked_i=0`, la deuxième formule vaut **1**
alors que le contrat exige **0**.

Ce cas correspond à **une écriture non privilégiée sur un
registre protégé**, dans notre modèle d'exercice.
Il n'est pas nécessaire d'attaquer un appareil réel.

## 3. Pourquoi le graphe de dépendances ne suffit pas

Après compilation par le **vrai slang v12.1** :

```bash
python -m rtlprep deps examples/security_csr/design.json \
  --out reports/security-lab/rtl-gold

python -m rtlprep deps examples/security_csr/buggy_design.json \
  --out reports/security-lab/rtl-buggy
```

La sortie `write_accepted_o` dépend dans **les deux
versions** de `write_i`, `machine_mode_i` et
`debug_locked_i`. `value_o` dépend également de
`wdata_i` et de la condition d'écriture.

Le graphe permet donc de cibler le prédicat d'autorisation
et sa provenance, mais **ne démontre pas à lui seul que
l'opérateur booléen est `&&` plutôt que `||`**.

En particulier, **un même ensemble d'arêtes
`(source, target, kind)` ne signifie pas deux circuits
équivalents**. Cette limite est intéressante pour notre
projet : un agent doit faire suivre ses hypothèses de
tests contre un contrat indépendant.

## 4. Première vérification : simulation cocotb

Installer les outils facultatifs appropriés
(**Verilator 5.040**, **cocotb 2.0.1**, `make`, `g++`) :

```bash
python -m pip install -e '.[dev,simulation]'
python -m rtlprep simulate examples/security_csr/design.json \
  --out reports/security-lab/sim-gold

python -m rtlprep simulate examples/security_csr/buggy_design.json \
  --out reports/security-lab/sim-buggy
```

Le deuxième appel doit **échouer (code 2)**.
Le banc
[`rtlprep/sim_tests/secure_csr.py`](../rtlprep/sim_tests/secure_csr.py)
vérifie le même contrat pour **les deux versions** :

- **tentative non privilégiée pendant le debug déverrouillé** ;
- **écriture valide en mode machine** et refus quand
  le registre est verrouillé ;
- **les 8 combinaisons** des trois signaux de contrôle,
  puis 128 stimuli pseudo-aléatoires **reproductibles** ;
- maintien de la valeur et reset asynchrone.

Le fichier `simulation_results.xml` contient les noms
et verdicts des **véritables tests cocotb**. Un mutant
rejeté n'est pas une simulation « passée » : c'est
un **test négatif ayant réussi à détecter une erreur**.

## 5. Deuxième vérification : propriété formelle SBY

Le banc formel indépendant est
[`rtlprep/formal_specs/secure_csr_properties.sv`](../rtlprep/formal_specs/secure_csr_properties.sv).

Il reprend le contrat dans une variable
`spec_accepted`, construit un **registre de référence**
`spec_value`, puis demande à Yosys/SBY de vérifier :

```systemverilog
assert(write_accepted_o == spec_accepted);
assert(value_o == spec_value);
if (write_i && !machine_mode_i)
    assert(!write_accepted_o);
if (debug_locked_i)
    assert(!write_accepted_o);
```

La propriété de non-élévation de privilège
(`write_i && !machine_mode_i -> !write_accepted_o`)
n'est pas une observation d'une seule simulation :
SBY peut explorer des **valeurs symboliques** d'entrée
et tenter de démontrer l'invariant.

Hypothèse de départ clairement déclarée :

```systemverilog
initial assume(!rst_n);
```

Nous supposons donc **un reset initial**, pas un
état arbitraire déjà chargé. Les autres signaux de
contrôle restent libres de varier au cours de la preuve.

Un témoin `cover(value_o == 8'hA5)` vérifie
qu'un registre peut être écrit légitimement :
la preuve n'est pas obtenue en interdisant
toute activité. **`cover PASS` n'est pas
une preuve de couverture fonctionnelle exhaustive**.

```bash
python -m rtlprep formal examples/security_csr/design.json \
  --out reports/security-lab/formal-gold

python -m rtlprep formal examples/security_csr/buggy_design.json \
  --out reports/security-lab/formal-buggy
```

Sur le circuit correct, nous exigeons
`prove=PASS` **et** `cover=PASS`.
Sur le mutant, nous exigeons `prove=FAIL`
avec un **fichier `trace*.vcd` existant**.
Un verdict `UNKNOWN` n'est **jamais**
transformé en détection de faille.

## 6. Troisième vérification : équivalence EQY

Nous comparons les deux transformations avec le **même
RTL de référence** :

```bash
# Refactorisation correcte : une preuve d'équivalence est attendue.
python -m rtlprep eqy examples/security_csr/design.json \
  --gate examples/security_csr/refactored_design.json \
  --out reports/security-lab/eqy-good

# Mutant : non-équivalence attendue, preuve par trace VCD.
python -m rtlprep eqy examples/security_csr/design.json \
  --gate examples/security_csr/buggy_design.json \
  --out reports/security-lab/eqy-buggy
```

La comparaison avec le mutant doit donner un verdict
global EQY `FAIL`, une partition `FAIL` et une trace.
Le cas de refactorisation doit donner `PASS`
avec des partitions réellement analysées.

**EQY n'est pas un oracle de sécurité :** il montre
une différence entre deux versions, pas si
la « référence » respecte une politique correcte.
C'est pourquoi notre contrat SBY séparé est nécessaire.

## 7. Un rapport d'audit unique, fondé sur les preuves

Après les huit analyses / validations préalables :

```bash
python scripts/check_security_lab.py --root reports/security-lab
```

Le script lit **les fichiers réels** suivants,
sans lancer d'outil ou de modèle :

```text
reports/security-lab/
├── rtl-gold/rtl_dependencies.json
├── rtl-buggy/rtl_dependencies.json
├── sim-gold/simulation.result.json
├── sim-buggy/simulation.result.json
├── formal-gold/formal.result.json
├── formal-buggy/formal.result.json
├── eqy-good/equivalence.result.json
├── eqy-buggy/equivalence.result.json
└── security_lab_report.json
```

La consolidation **échoue** si un des contrats de
succès/échec n'est pas effectivement satisfait :
nombre de tests, violation unprivilégiée,
contre-exemples SBY/EQY, fichiers VCD, cohérence
des nœuds de graphe.

L'attribut JSON `benchmark_real_agent` vaut
expressément **`false`** : aucun agent autonome
n'a encore été évalué.

Les artefacts GitHub Actions contiennent les
rapports, les résultats xUnit et les traces VCD,
sans sauvegarder ni exécuter de données non approuvées.

## 8. Premier exercice à donner à un agent

Dans un environnement **contrôlé**, nous pouvons
demander à un agent disposant du dépôt et
des rapports RTLPrep :

> « Le fichier `examples/security_csr/secure_csr_buggy.sv`
> est suspect. La spécification est :
> `write_accepted = write && machine_mode && !debug_locked`.
> Identifie les conditions d'un éventuel contournement
> de privilège ; donne la ligne de code concernée,
> le comportement attendu/observé et les preuves
> qui confirment ou réfutent ton hypothèse.
> Distingue les arêtes du graphe des assertions
> formelles. Ne modifie rien. »

**Grille de notation proposée :**

| Critère | Attendu |
| --- | --- |
| Contrat | Formule complète correcte |
| Condition d'exploitation | `write=1, machine=0, debug_locked=0` |
| Cause | `||` à la place de `&&` |
| Conséquence | Écriture non privilégiée sur notre modèle |
| Provenance | Fichier / ligne RTL exacts |
| Preuve | Échec cocotb et `FAIL` SBY avec trace |
| Incertitude | Reconnaître que le graphe seul ne suffit pas |
| Généralisation | Ne pas annoncer de vulnérabilité CV32E40P réelle |

Cet exercice reste **non aveugle**, puisque le mutant
est désigné et la spécification fournie. Pour parler
d'un « agent qui découvre une faille », il faudra
ensuite un **jeu de designs tenus secrets pendant
le développement**, et une mesure indépendante
avec un véritable agent connecté.

## 9. Portée, sécurité et prochaines étapes

- **Cette vulnérabilité est artificielle**, placée dans
  une petite IP d'enseignement. Pas de cible industrielle
  ou de reproduction d'une exploitation sur une puce réelle.
- Les outils formels et simulateurs s'exécutent en CI
  sur **les seules fixtures approuvées**. Le serveur
  MCP de la PR #15 reste **lecture seule**.
- La chaîne teste une **propriété de privilège explicite**,
  non la sécurité globale d'un CPU.
- Notre graphe reste **au niveau signal** ;
  il ne comprend pas toute la sémantique booléenne
  ni toutes les constructions de SystemVerilog.
- Les tests de sécurité ne doivent pas être ajoutés
  avec des `assume` qui interdiraient justement
  le scénario de vulnérabilité.
- Les futurs essais devront varier l'IP, la
  classe de bug et la topologie, puis comparer
  des **réponses réelles d'un agent** à des
  réponses de référence tenues à l'écart.

**C'est la bonne façon de transformer RTLPrep
en assistant d'investigation matérielle :
vérifier les hypothèses, conserver les preuves,
et mesurer honnêtement les limites.**

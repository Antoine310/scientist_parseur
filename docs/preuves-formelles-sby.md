# PR #12 — Premières vérifications formelles avec SymbiYosys (SBY)

## 1. Pourquoi faire autre chose que de la simulation ?

RTLPrep peut déjà **simuler** un compteur et une FSM avec Verilator et
cocotb. Les tests vérifient des séquences concrètes : activation, reset,
débordement, transitions. Mais ils ne parcourent pas exhaustivement tous
les scénarios.

**SBY (SymbiYosys)** utilise Yosys et un solveur SMT pour explorer un
modèle mathématique du circuit. Cette PR introduit :

- `prove` : une tentative de preuve par induction, avec base et étape
  inductive ; un résultat `PASS` signifie que **les propriétés
  explicitement énoncées** ont été démontrées sous les hypothèses et
  dans le modèle choisi.
- `cover` : une recherche de **témoin d'atteignabilité** pour éviter
  certaines démonstrations triviales où le circuit ne sortirait jamais
  de reset.
- un contrôle négatif : un compteur volontairement incorrect doit
  produire `FAIL` et une **trace VCD** permettant d'examiner le bug.

Même une preuve formelle `PASS` **ne prouve pas qu'un processeur entier
est correct** : elle prouve *uniquement les assertions vérifiées* sous
les hypothèses et sémantiques de la preuve.

Documentation des outils :
[SBY : assertions, assumptions et cover](https://symbiyosys.readthedocs.io/en/latest/verilog.html),
[format des fichiers .sby](https://symbiyosys.readthedocs.io/en/latest/reference.html).

## 2. Installer les outils et lancer les preuves

La CI utilise une version **datée** d'OSS CAD Suite
(`2026-11-18`) sur Ubuntu 24.04, avec `sby`, `yosys`
et le solveur libre `z3`. Il n'y a pas d'API payante.

Après installation d'une [OSS CAD Suite](https://github.com/YosysHQ/oss-cad-suite-build/releases)
compatible sur Linux/WSL2 :

```bash
sby --version
yosys -V
z3 --version
python -m pip install -e '.[dev]'
python -m rtlprep doctor

# Compteur : preuve et témoin d'atteignabilité
python -m rtlprep formal examples/counter/design.json \
  --out reports/formal-counter --timeout 180

# FSM handshake : états attendus et accès à DONE
python -m rtlprep formal examples/fsm/design.json \
  --out reports/formal-fsm --timeout 180

# Mutant défectueux (fait +2 au lieu de +1) :
# cette commande DOIT sortir avec un statut d'échec.
python -m rtlprep formal examples/counter/buggy_design.json \
  --out reports/formal-buggy --timeout 180
```

Le workflow CI
[`sby-formal.yml`](../.github/workflows/sby-formal.yml)
vérifie que les deux circuits de référence sont prouvés et
qu'un témoin est produit ; il exige un **contre-exemple réel**
sur le compteur mutant.

## 3. Des propriétés séparées du RTL

Les bancs de preuve sont **livrés avec RTLPrep** :

- [`rtlprep/formal_specs/counter_properties.sv`](../rtlprep/formal_specs/counter_properties.sv)
- [`rtlprep/formal_specs/handshake_fsm_properties.sv`](../rtlprep/formal_specs/handshake_fsm_properties.sv)

Ce ne sont pas des tests arbitraires fournis par un utilisateur.
La fonction `formal_verify()` accepte **uniquement**
les top modules de la liste blanche `PROOF_SUITES` et
une source RTL. Les fichiers `.sby` sont générés automatiquement,
sans exécuter de commandes extraites d'un manifeste, d'un log ou d'un
fichier SystemVerilog.

Dans chaque fichier formel, on instancie le DUT et un **modèle
de référence distinct**. Pour le compteur :

```systemverilog
always @(posedge clk or negedge rst_n) begin
    if (!rst_n)
        reference_count <= 8'd0;
    else if (enable)
        reference_count <= reference_count + 8'd1;
end

always @(*) begin
    if (initialized)
        assert(count == reference_count);
end
```

L'égalité avec le modèle de référence couvre l'incrémentation,
le maintien sur `enable=0`, le retour modulo 256 et le reset
dans le modèle. Avec le mutant `count + 2`, l'égalité
peut être violée : la CI doit montrer la trace.

### Pourquoi une hypothèse de reset ?

```systemverilog
initial assume(!rst_n);
```

Sans hypothèse de démarrage, un registre matériel peut
commencer dans un état non initialisé ; on ne peut pas exiger
une égalité entre DUT et modèle à cet instant.

Ici, nous supposons que **`rst_n=0` à l'état initial** ;
le reste du comportement des entrées n'est pas bloqué par
des hypothèses sur `enable`, `start` ou `ack`.
Le drapeau `initialized` évite d'asserter l'égalité avant
l'exécution du reset.

**C'est une hypothèse de preuve documentée**, pas
une découverte du compilateur ni une hypothèse valable
pour tous les circuits physiques réels.

## 4. Pourquoi vérifier l'invariant à chaque pas ?

Les blocs d'état sont cadencés par `posedge clk`, mais
l'induction considère aussi des états abstraits.

Si l'assertion n'est vérifiée **que** lors d'un front
que le solveur peut choisir de ne pas générer, celui-ci
peut fabriquer des séquences sans front où la propriété
n'est pas contrôlée, puis une étape finale impossible
à établir.

D'où la vérification combinatoire, pendant
tous les pas du modèle :

```systemverilog
always @(*)
    if (initialized)
        assert(count == reference_count);
```

Ce renforcement évite qu'une preuve soit déclarée
réussie par manque d'observations. Ce n'est pas une
hypothèse `assume` : l'outil doit démontrer cette
assertion.

## 5. Le mode cover évite une partie des preuves vides

Le fichier du compteur recherche :

```systemverilog
cover(count == 8'd3);
```

C'est un témoin montrant qu'on peut quitter le reset
et incrémenter jusqu'à 3.

La FSM cherche un témoin où `done=1` et vérifie par
assertions que `busy` et `done` correspondent à
l'automate de référence et ne sont pas actifs ensemble.

**Nuance :** un `cover PASS` est un témoin d'atteignabilité,
pas une preuve que toutes les transitions possibles
ont été couvertes.

## 6. Comprendre les résultats de SBY

Le rapport `formal.result.json` contient deux entrées :
`proof` et `cover`. Pour chacune, RTLPrep enregistre
le verdict réel du fichier `status` de SBY, le code
de retour, la durée et le chemin du dossier de travail.

Les statuts principaux :

| Verdict SBY | Interprétation RTLPrep |
|---|---|
| `PASS` en mode `prove` | `passed` pour les assertions définies |
| `PASS` en mode `cover` | `passed` pour le témoin recherché |
| `FAIL` | `failed` ; inspecter les traces |
| `UNKNOWN` | `inconclusive` : preuve non établie, **pas bug démontré** |
| `ERROR` | `error` ; problème de commande ou modèle |
| `TIMEOUT` | `timeout` ; résultat non conclusif |
| Outil absent | `missing_tool` |
| Fichier `status` absent après retour 0 | `failed`, jamais succès supposé |

En particulier, `UNKNOWN` peut signifier que la **base
de l'induction passe, mais que l'étape inductive n'est pas
suffisamment forte**. Il ne faut pas transformer ce cas
en `PASS` ni en « un bug a été trouvé ».

Les statuts SBY peuvent apparaître sous la forme
`PASS 0 0`, `UNKNOWN 4 0` : le parseur extrait
le **premier champ** du fichier `status`.

## 7. Contre-exemple et contrôle négatif

La CI exécute le
[`counter_buggy.sv`](../examples/counter/counter_buggy.sv)
de la PR #11 avec les **mêmes propriétés**, qui
exigent `+1` sous `enable=1`. Le mutant fait `+2`.

Résultat attendu :

- `formal.result.json` : `status=failed` ;
- `proof.sby_status=FAIL` ;
- une trace `engine_0/trace.vcd` (ou autre fichier `trace*.vcd`)
  conservée dans le dossier de travail ;
- code CLI **2**, pour interdire un faux « vert ».

Les fichiers VCD peuvent être ouverts avec un visualiseur
comme GTKWave pour examiner les entrées et les états au
moment de la violation. Les traces sont des **données
de diagnostic**, pas des instructions à exécuter.

## 8. Ce qui reste hors du périmètre

- La preuve porte uniquement sur les deux **petits designs
  autorisés** et les assertions décrites ci-dessus.
- Il n'y a **pas** encore d'exploration formelle exhaustive
  de l'ALU ou du CPU RISC-V.
- Les propriétés reposent sur une hypothèse d'initialisation ;
  elles ne démontrent pas une tolérance aux resets physiques,
  aux métastabilités ou aux effets analogiques.
- Pas d'analyse CDC, timing, sécurité matérielle globale
  ou équivalence EQY dans ce premier jalon.
- Le modèle mathématique dépend de l'interprétation RTL par
  Yosys/SMTBMC ; Verilator/cocotb reste une vérification
  **complémentaire**, indépendante.
- Les outils formels sont exécutés sur des circuits approuvés
  avec timeout ; il ne s'agit pas encore d'une **sandbox**
  complète pour RTL hostile.

**Étape suivante :** intégrer une vérification d'équivalence
avec EQY sur une paire de modules simples, puis
travailler sur des propriétés représentatives du
CV32E40P et un rapport de couverture commun aux
simulations, graphes et preuves.

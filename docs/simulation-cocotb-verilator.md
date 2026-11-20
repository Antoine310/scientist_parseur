# PR #11 — Simulation comportementale avec Verilator et cocotb

> **Phase D, premier jalon vérifié en CI.** RTLPrep peut maintenant
> exécuter **de vrais tests fonctionnels**, pas uniquement produire
> un AST ou un graphe de dépendances. Cela ne remplace **pas**
> une preuve formelle, la couverture exhaustive ou une analyse CDC.

## 1. Pourquoi ajouter une simulation ?

Le graphe de la phase C dit : « `enable` peut influencer `count` ».
Cela ne permet **pas encore** de conclure que le compteur ajoute exactement
1 quand `enable=1`, ni qu'un reset asynchrone fonctionne.

Nous apportons deux outils complémentaires :

- **Verilator**, compilateur de simulation SystemVerilog open source,
  qui transforme notre circuit en modèle exécutable.
- **cocotb**, bibliothèque Python exécutant des tests *dans le
  simulateur*, via l'interface VPI. Les tests vérifient les sorties
  réelles du design (DUT, *Design Under Test*).

Le RTL n'est pas analysé avec des expressions régulières et
nous ne réimplémentons pas un simulateur HDL.

## 2. Installation et versions validées

Pour le développement sur Linux / WSL2 :

```bash
python -m pip install -e '.[dev,simulation]'
verilator --version
python -c 'import cocotb; print(cocotb.__version__)'
python -m rtlprep doctor
```

La CI utilise :

- **Ubuntu 24.04**, Python **3.11** ;
- **Verilator 5.040**, installé sous forme de binaire précompilé ;
- **cocotb 2.0.1**, version figée dans `pyproject.toml`.

⚠️ Compatibilité importante : cocotb 2.0 demande Verilator **5.036
ou plus récent**. Le Verilator livré dans Ubuntu 24.04 via
`apt install verilator` est **5.020** : il ne répond pas au minimum.
Nous utilisons donc un installateur GitHub Actions
`veryl-lang/setup-verilator` avec `version: '5.040'`.
Les **guillemets** sont nécessaires : en YAML, `5.040` sans guillemets
serait converti en `5.04`.

La dépendance `cocotb` est facultative pour les autres fonctions :
`rtlprep index`, `rtlprep deps` et les tests unitaires classiques
restent utilisables sans simulateur.

Documentation d'origine :

- [cocotb 2.0 — Python Runner](https://docs.cocotb.org/en/v2.0.1/runner.html) ;
- [cocotb 2.0 — Simulateurs pris en charge](https://docs.cocotb.org/en/v2.0.0/simulator_support.html) ;
- [Verilator](https://verilator.org/guide/latest/install.html).

## 3. Essayer le compteur

Le circuit d'entraînement existant
[`examples/counter/counter.sv`](../examples/counter/counter.sv)
contient un registre de 8 bits :

```systemverilog
always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n)
        count <= 8'd0;
    else if (enable)
        count <= count + 8'd1;
end
```

Le comportement attendu est :

- `rst_n=0` : `count=0`, même hors front montant ;
- front montant et `enable=1` : `count = (count+1) mod 256` ;
- front montant et `enable=0` : conservation de `count`.

Pour exécuter les **trois tests cocotb** :

```bash
python -m rtlprep simulate examples/counter/design.json \
    --out reports/sim-counter --timeout 180
```

L'outil produit :

```text
reports/sim-counter/
├── simulation.result.json      # Statut / compteurs / versions
├── simulation_results.xml      # Rapport xUnit cocotb
├── simulation.stdout.log       # Compilation et simulation
├── simulation.stderr.log       # Diagnostics
├── simulation.config.json      # Arguments effectifs
└── simulation_build/           # Binaire de simulation (non versionné)
```

Les tests s'appellent :

1. **`test_enable_and_hold`** — compte uniquement quand `enable` vaut 1.
2. **`test_wraparound`** — vérifie plus de 256 incréments, et le
   retour à zéro du registre de 8 bits.
3. **`test_async_reset_and_deterministic_stimuli`** — 128 stimuli
   pseudo-aléatoires, avec graine fixe `0xC0FFEE`, puis vérification
   du reset asynchrone pendant un niveau haut de l'horloge.

**Important :** la graine fixe rend l'expérience reproductible, mais
128 stimuli aléatoires ne couvrent pas tous les scénarios possibles.

## 4. Tester une machine à états (FSM)

Le second circuit d'entraînement est
[`examples/fsm/handshake_fsm.sv`](../examples/fsm/handshake_fsm.sv).

Il suit trois états :

```text
  start=1        ack=1
IDLE ─────► BUSY ─────► DONE
  ▲                         │
  └─────────────────────────┘
           cycle suivant
```

Sorties :

- `busy=1` uniquement en état `BUSY` ;
- `done=1` uniquement en état `DONE` ;
- `start` pendant `BUSY` et `ack` pendant `IDLE` sont ignorés.

Pour lancer ses **deux tests cocotb** :

```bash
python -m rtlprep simulate examples/fsm/design.json \
    --out reports/sim-fsm --timeout 180
```

Les tests vérifient un scénario de transitions orienté et
128 combinaisons `start`/`ack` déterministes. Un **modèle de
référence Python séparé** calcule l'état attendu à chaque cycle,
puis compare les sorties du simulateur.

## 5. Comment le code fonctionne

### 5.1 `rtlprep.simulation.simulate()`

La CLI charge le manifeste habituel (`top`, `sources`,
`include_dirs`, `defines`) et appelle `simulate()`.

Cette fonction :

1. élimine les **anciens rapports** `simulation_results.xml`
   et `simulation.result.json`, pour éviter un faux succès ;
2. vérifie la présence de `verilator`, `make`, `g++` et `cocotb` ;
3. refuse les top modules **sans banc de test approuvé** ;
4. enregistre l'empreinte des sources, les arguments et versions d'outils ;
5. lance un **processus enfant** avec un timeout ;
6. lit le rapport **xUnit XML produit par les vrais tests** et
   recalcule le statut final.

### 5.2 `rtlprep.sim_worker`

Le worker fait appel au **Python Runner officiel** :

```python
from cocotb_tools.runner import get_runner

runner = get_runner("verilator")
runner.build(
    sources=[...],
    hdl_toplevel="counter",
    timescale=("1ns", "1ps"),
    build_args=["--timing", "-Wno-fatal"],
    ...
)
runner.test(
    test_module="rtlprep.sim_tests.counter",
    hdl_toplevel="counter",
    results_xml=".../simulation_results.xml",
    ...
)
```

Le code réel utilise le nom de top chargé et les sources **du manifeste**.

`rtlprep/sim_tests/` contient les **seuls bancs cocotb autorisés**
dans cette première version. Le manifeste ne peut **pas** demander
l'import d'un module Python arbitraire sous prétexte de tester son RTL.
C'est volontaire : un futur outil piloté par Codex ne doit jamais
exécuter aveuglément des instructions trouvées dans un design externe.

### 5.3 L'importance du XML

Le retour de `runner.test()` ne doit **pas** être interprété
comme une réussite sans examiner les tests : certains simulateurs
peuvent terminer avec un code de retour normal tout en enregistrant
des assertions échouées.

C'est pourquoi `parse_cocotb_results()` lit les `testcase`
et leurs éléments `failure`, `error` ou `skipped`.
Notre politique :

| Situation | Statut RTLPrep |
| --- | --- |
| Simulateur présent, tous les tests réussis | `passed` |
| Au moins une assertion échoue | `failed` |
| Test sauté sans échec | `inconclusive` |
| Verilator ou cocotb absent | `missing_tool` |
| Temps maximal dépassé | `timeout` |
| Retour 0 mais XML absent ou vide | `failed` |
| Top sans banc de test approuvé | `failed` |

La commande CLI sort avec le code `0` seulement pour `passed`,
et `2` dans les autres cas.

## 6. Un circuit volontairement défectueux !

Le projet possède aussi
[`examples/counter/counter_buggy.sv`](../examples/counter/counter_buggy.sv)
avec une erreur **introduite à dessein** :

```systemverilog
else if (enable)
    count <= count + 8'd2; // BUG : attendu +1
```

On exécute **exactement le même banc cocotb**, mais avec ce circuit :

```bash
python -m rtlprep simulate examples/counter/buggy_design.json \
    --out reports/sim-buggy --timeout 180
```

Cette commande doit **échouer** et sortir avec le code `2`.
Cela signifie que le détecteur de comportement incorrect fonctionne.

Le workflow GitHub Actions `.github/workflows/cocotb-simulation.yml`
vérifie deux conditions séparées :

- le circuit de référence passe **tous** les tests ;
- le circuit mutant échoue sur **au moins un** test, et le
  `simulation.result.json` / `simulation_results.xml`
  conserve réellement cet échec.

Un résultat `failed` sur ce mutant est une **réussite du contrôle
négatif**, mais pas un succès de la simulation du circuit défectueux.

## 7. Périmètre et limites

- Les tests portent sur **deux petits designs autorisés** ;
  l'ALU du CV32E40P n'a pas encore de testbench cocotb validé.
- La simulation vérifie des **scénarios**, pas toutes les entrées ni
  tous les instants possibles.
- Le backend initial est **Verilator seulement**.
- La liste blanche de testbenches est volontairement **restreinte**.
  Pour un design tiers, nous devrons ajouter un banc revu et une
  véritable politique de sandbox avant toute exécution.
- Le timeout limite le temps du processus enfant, mais
  **l'isolation mémoire/CPU et réseau** dépend encore du runner CI :
  ce n'est pas une sandbox matérielle sécurisée complète.
- La vérification formelle **SBY/EQY**, le coverage et les
  propriétés de sécurité restent à développer en phase D.

**Étape recommandée ensuite :** ajouter une propriété formelle
pour le compteur et une FSM, puis relier les résultats au graphe
de dépendances, sans jamais assimiler « simulation passée » à
« circuit prouvé correct ».

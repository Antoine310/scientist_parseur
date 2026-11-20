# PR #13 — Vérification d'équivalence RTL avec Yosys EQY

Ce chapitre explique comment RTLPrep compare **deux implémentations d'un
même circuit** sans se contenter de quelques simulations et sans faire appel
à un LLM payant. Les expériences sont réalisées avec **YosysHQ EQY,
SymbiYosys (SBY), Yosys et Z3**, tous open source.

> **Portée :** démontrer l'équivalence logique des sorties observables et
> des états correspondants, dans le modèle de Yosys/EQY, pour les circuits
> explicitement autorisés. Ce n'est **pas** une preuve de sécurité matérielle,
> de respect du timing, de propriétés analogiques ou de correction d'un CPU.

## 1 — Pourquoi EQY après SBY ?

La PR #12 ajoutait une vérification formelle avec assertions :
« le compteur vaut-il bien `n + 1` après une impulsion `enable` ? ».

EQY répond à une question différente :

> « La **nouvelle implémentation** a-t-elle le **même comportement**
> que la version de référence, pour les entrées et séquences du modèle ? »

Cette comparaison est utile après une refactorisation de RTL, une
optimisation de logique, ou avant de remplacer un sous-module existant.

EQY appelle les deux versions :
- **Gold** : conception de référence, connue et approuvée ;
- **Gate** : implémentation candidate que l'on souhaite comparer.

Le nom *gate* ne signifie pas nécessairement « netlist de portes » :
EQY peut comparer **deux fichiers RTL**.

## 2 — Préparation de l'environnement

Notre CI utilise une version **datée** de l'OSS CAD Suite (`2026-11-18`)
pour garder ensemble des versions compatibles de `eqy`, `sby`,
`yosys` et `z3`.

```bash
eqy --version
sby --version
yosys -V
z3 --version
python -m pip install -e '.[dev]'
```

Les outils formels sont optionnels : sans eux, RTLPrep répond
`missing_tool`, et ne déclare pas une preuve imaginaire.

La [documentation de référence de EQY](https://yosyshq.readthedocs.io/projects/eqy/en/latest/config.html)
explique le format `.eqy`. Le
[format des dossiers de résultat](https://yosyshq.readthedocs.io/projects/eqy/en/latest/outdir.html)
décrit les marqueurs `PASS` et `FAIL`, les partitions et les stratégies.

## 3 — Deux variantes qui doivent être équivalentes

### 3.1 Compteur : addition dans ou hors du `always_ff`

Dans le circuit de référence
[`counter.sv`](../examples/counter/counter.sv) :

```systemverilog
always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n)
        count <= 8'd0;
    else if (enable)
        count <= count + 8'd1;
end
```

Dans la version candidate
[`counter_refactored.sv`](../examples/counter/counter_refactored.sv) :

```systemverilog
logic [7:0] incremented;
assign incremented = count + 8'd1;

always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n)
        count <= 8'd0;
    else if (enable)
        count <= incremented;
end
```

Cette modification **déplace le calcul** dans un assign combinatoire.
Le circuit reste censé conserver la même sortie `count` sur les mêmes
transitions d'horloge et de reset. C'est **EQY qui doit le démontrer**.

```bash
python -m rtlprep eqy examples/counter/design.json \
    --gate examples/counter/refactored_design.json \
    --out reports/eqy-counter
```

### 3.2 FSM : remplacer un `case` par un `if/else`

Le circuit d'entraînement
[`handshake_fsm.sv`](../examples/fsm/handshake_fsm.sv)
possède trois états : `IDLE`, `BUSY`, `DONE`.

La variante
[`handshake_fsm_refactored.sv`](../examples/fsm/handshake_fsm_refactored.sv)
utilise des tests `if/else` pour calculer l'état suivant au lieu
d'un `case`.

```bash
python -m rtlprep eqy examples/fsm/design.json \
    --gate examples/fsm/refactored_design.json \
    --out reports/eqy-fsm
```

L'objectif est de vérifier que les transitions et les sorties
`busy` / `done` restent équivalentes dans le modèle retenu.

## 4 — Une variante volontairement fausse

Le fichier
[`counter_buggy.sv`](../examples/counter/counter_buggy.sv)
contient une erreur introduite pour les tests : il ajoute
`2` au lieu de `1`.

```bash
python -m rtlprep eqy examples/counter/design.json \
    --gate examples/counter/buggy_design.json \
    --out reports/eqy-buggy
```

La CI exige que la vérification déclare une **différence réelle**.
Le résultat doit fournir les informations sur la partition qui
échoue, ainsi qu'une trace VCD permettant de reproduire
la différence.

**C'est un contrôle négatif** : s'il passe à tort, le
vérificateur n'est pas fiable.

## 5 — Le fichier de configuration EQY généré

`rtlprep/equivalence.py` crée un `equivalence.eqy`
reproductible. Sa structure est :

```ini
[gold]
read_verilog -formal -sv "/chemin/vers/counter.sv"
prep -top counter

[gate]
read_verilog -formal -sv "/chemin/vers/counter_refactored.sv"
prep -top counter

[strategy induction]
use sby
engine smtbmc z3
depth 12
```

Les chemins montrés ci-dessus sont **illustratifs**.
Le programme génère les chemins absolus depuis les manifestes,
puis vérifie leur provenance et les échappements nécessaires.

### À quoi sert chaque section ?

- `[gold]` : compiler l'implémentation de référence.
- `[gate]` : compiler le candidat sous le **même top**.
- `prep -top` : élaborer le module considéré.
- `[strategy induction]` : utiliser SBY pour démontrer
  l'équivalence des **partitions créées automatiquement par EQY**.
- `smtbmc z3` : confier la recherche SMT au solveur Z3.
- `depth 12` : profondeur de recherche employée dans la stratégie
  d'induction ; ce n'est **pas** une garantie que les
  équivalences non démontrées au-delà de 12 cycles sont vraies.

EQY rapproche les signaux et partitions correspondants,
puis essaie de prouver leur égalité. Une réussite exige
une preuve effective des partitions, pas un simple `yosys` sans erreur.

## 6 — Que signifie un verdict EQY ?

Le dossier de travail contient les fichiers définis par EQY :

```text
reports/eqy-counter/
├── equivalence.eqy
├── equivalence.result.json
├── equivalence.stdout.log
├── equivalence.stderr.log
└── eqy_work/
    ├── PASS               # ou FAIL
    ├── logfile.txt
    ├── partition.list
    ├── matched.ids
    ├── gold.il
    ├── gate.il
    └── strategies/...
```

Notre logique de classification :

| Évidence réelle | Statut RTLPrep |
| --- | --- |
| Marqueur `PASS` + processus réussi + partition non vide | `passed`, `equivalent=true` |
| Marqueur `FAIL` + partition `FAIL` + trace VCD | `failed`, `equivalent=false` |
| EQY n'arrive pas à démontrer toutes les partitions sans contre-exemple concluant | `inconclusive`, `equivalent=null` |
| Configuration / compilation défectueuse | `error` ou `failed` avec diagnostic |
| Outil absent | `missing_tool` |
| Délai dépassé | `timeout` |
| Marqueur absent, contradictoire ou zéro partition | Jamais un faux `passed` |

Une différence logique **démontrée** n'est pas interchangeable
avec un `UNKNOWN`. Nous voulons conserver cette distinction
comme dans notre précédent moteur SBY.

Les traces `trace*.vcd` sont des **données de diagnostic**
consultables dans GTKWave, pas du code à exécuter.

## 7 — La liste blanche est volontaire

Dans ce MVP, la commande accepte seulement :

- `counter.sv` comme référence, avec
  `counter_refactored.sv` ou `counter_buggy.sv` comme candidats ;
- `handshake_fsm.sv` comme référence,
  avec `handshake_fsm_refactored.sv` comme candidat.

Les chemins sont comparés **au chemin réel résolu**, pas seulement
au nom du fichier. Les manifestes ne peuvent pas choisir
des scripts `.eqy` ou des commandes Yosys à exécuter.

Cette restriction évite de présenter l'exécution
de SystemVerilog non fiable comme sûre dans le runner CI.
L'ajout de RTL tiers nécessitera une sandbox plus robuste,
une autorisation et de nouveaux bancs de vérification.

## 8 — Tests et limites

L'ensemble des tests Python
[`tests/test_equivalence.py`](../tests/test_equivalence.py)
vérifie, sans dépendre d'EDA installé : la configuration,
les paires approuvées, les fichiers interdits, les anciens
rapports effacés, les marqueurs contradictoires,
`PASS` non vide, `FAIL` avec trace et `UNKNOWN` non conclusif.

Le workflow
[`.github/workflows/eqy-equivalence.yml`](../.github/workflows/eqy-equivalence.yml)
installe la suite officielle, exécute **les preuves réelles**
et sauvegarde les rapports/logs/traces pendant 14 jours.

**Ce que ce jalon ne démontre pas :**

- l'équivalence d'un processeur RISC-V complet ;
- la validité des exigences fonctionnelles initiales (deux circuits
  peuvent être équivalents et **également faux**) ;
- le timing, les performances, la puissance, le risque de
  métastabilité, les attaques matérielles ou la sûreté physique ;
- l'équivalence pour n'importe quel pair RTL et tout
  SystemVerilog, sans adaptation ni support des outils.

**Étape recommandée ensuite :** étendre la validation à une
unité RISC-V contrôlée, en définissant des contrats d'interface
et des propriétés mesurables avant d'ajouter un agent MCP/Codex.

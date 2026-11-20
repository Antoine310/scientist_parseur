# PR #16 — Benchmark reproductible RTLPrep : graphe et contexte pour un agent

**Phase G, première expérience mesurée avec slang v12.1** · 20 novembre 2026

Cette étape ne cherche pas à démontrer que Codex répond mieux sans
avoir interrogé **un vrai modèle**. Elle mesure d'abord ce que notre
code est capable de prouver **indépendamment du LLM** :

1. le graphe contient-il **35 relations positives attendues**, et évite-t-il
   **16 relations négatives** sur de petits circuits soigneusement annotés ?
2. à combien d'octets de **contexte technique** correspondent différentes
   façons de préparer une question sur le même circuit ?
3. combien de temps prend l'exécution **réelle** de slang + index + graphe ?
4. que donne cette chaîne sur une **véritable ALU RISC-V CV32E40P**
   dont les fichiers et les versions sont épinglés ?

> **Important : ce n'est ni une évaluation de précision des réponses
> Codex/ChatGPT, ni un benchmark des tokens d'un modèle, ni une estimation
> fiable du coût ou de la latence d'une API LLM.** Les étiquettes sont
> volontairement limitées ; le graphe reste conservateur et approximatif
> au niveau des signaux.

## 1. Les trois stratégies comparées

La feuille de route prévoyait de comparer trois stratégies sur
**les mêmes questions** :

| Nom | Données présentées à un agent | Ce que cela mesure ici |
| --- | --- | --- |
| **A — brut** | Question + fichiers SystemVerilog complets du design | Volume d'une requête où on fournit le RTL sans analyse |
| **B — index seul** | Question + instance ciblée + déclarations et ports correspondants | Volume du contexte structurel sans graphe |
| **C — hybride** | Même index ciblé + `fanin` borné + avertissements + extrait RTL limité | Volume d'une preuve structurale accompagnée du code pertinent |

Notre script `rtlprep/benchmark.py::context_sizes()` construit trois
**charges utiles JSON** pour **une même question et un même signal**.
Il mesure `len(json UTF-8)` et, séparément, le nombre très approximatif
de mots séparés par des espaces dans le JSON.

**Ce que nous ne faisons pas :** envoyer ces charges utiles à un modèle
et interpréter son texte comme une réponse correcte. La comparaison
est une **mesure de préparation du contexte**, pas un classement
d'exactitude ou d'intelligence.

### Ce que veut dire « hybride »

Pour un signal comme `dependency_top.out`, l'index précise
le module, l'instance, les déclarations et les ports. Le graphe
ajoute un chemin potentiel :

```text
dependency_top.a
   └── dependency_top.child.a
          └── dependency_top.child.and_result
                 └── dependency_top.child.y
                        └── dependency_top.interm
                               └── dependency_top.out
```

La chaîne montre un **chemin de dépendances potentielles au niveau
des signaux**, pas la preuve d'une propagation en simulation.
La stratégie C joint un court extrait de source seulement lorsque
**slang fournit une provenance de fichier/ligne valable**.

Si aucune provenance n'est disponible, l'indicateur
`source_excerpt_available` est `false` : aucun numéro de
ligne ou extrait n'est inventé.

## 2. Jeu de référence étiqueté (petits designs)

Les étiquettes lisibles sont conservées dans
[`benchmarks/rtl_questions_v1.json`](../benchmarks/rtl_questions_v1.json).

| Circuit | Points intéressants | Limites |
| --- | --- | --- |
| **counter** | Reset, horloge, maintien et incrémentation | 8 bits, circuit simple |
| **hierarchy** | Deux instances `leaf`, entrées et sorties de ports | Pas de logique complexe |
| **dependencies** | Arêtes `data`, `control`, `event`, `port_input`, `port_output` | Hiérarchie courte |
| **advanced** | `case`, concaténations, sélection de bit, `generate` | Approximation signal entier |

Le jeu contient :

- **35 arêtes attendues (positives)** de la forme
  `[source, target, kind]` ;
- **16 arêtes volontairement absentes (négatives)** ;
- **7 questions** avec des signaux qui doivent être accessibles dans
  le `fanin`.

Les annotations sont issues d'une **lecture manuelle des petits fichiers
RTL et des contrats existants**. Ce jeu n'est pas un oracle exhaustif
et n'est **pas indépendant de notre développement** : les catégories
viennent en partie des tests d'intégration historiques.
Ce n'est donc pas un jeu de validation aveugle.

### Comment les chiffres sont calculés

Pour chaque triplet étiqueté, on cherche une arête exacte
`(source, target, kind)` dans le graphe réel généré par slang :

- **TP** : arête positive présente ;
- **FN** : arête positive manquante ;
- **FP** : arête négative pourtant présente ;
- **TN** : arête négative correctement absente.

Les ratios `precision_on_labels`, `recall_on_labels`,
`specificity_on_labels` concernent **uniquement ces
51 triplets**.

**Une arête non étiquetée n'est ni un faux positif ni une preuve
supplémentaire.** Le JSON indique combien d'arêtes restent hors
de cette annotation et conserve séparément les avertissements.

## 3. Résultat observé sur un premier run GitHub Actions

L'exécution du benchmark avec le **vrai slang 12.1** a produit :

| Mesure sur les exemples étiquetés | Résultat |
| --- | ---: |
| Positifs attendus / retrouvés | **35 / 35** |
| Négatifs attendus / correctement absents | **16 / 16** |
| FN (positifs manquants) | **0** |
| FP (négatifs présents à tort) | **0** |
| Précision / rappel sur ce jeu étiqueté | **100 % / 100 %** |
| Questions avec chemins attendus présents | **7 / 7** |

**Attention : 100 % sur 51 cas choisis n'est pas « RTLPrep est fiable
à 100 % », ni une mesure de précision sur toute l'ALU RISC-V.**
Un seul calcul non pris en charge (`Call`, par exemple) pourrait
produire d'autres résultats hors de ces cas étiquetés.

### Mesure des trois contextes

Le premier run, toutes les questions réunies (y compris
les deux questions exploratoires sur l'ALU), a obtenu :

| Contexte | Taille JSON UTF-8 |
| --- | ---: |
| A — RTL brut | **161 461 octets** |
| B — index seul | **15 965 octets** |
| C — hybride | **50 462 octets** |

`C/A = 0,3125`, soit un contexte hybride d'environ **31,25 %**
de la taille du contexte brut **dans cette expérience particulière**.

Il serait incorrect d'en déduire « 68,75 % de tokens économisés »
ou « Codex 3 fois plus rapide » : **aucun tokenizer de modèle,
aucun coût d'API et aucune réponse de modèle n'ont été mesurés**.

Ce ratio global est **fortement influencé par la taille de l'ALU**.
Le rapport JSON inclut également les volumes **par circuit** :
sur un tout petit fichier, le JSON hybride peut parfaitement être
**plus volumineux que le RTL brut** à cause des métadonnées !
Nous conservons ces cas au lieu de les masquer.

## 4. Mesure de temps et vraie ALU CV32E40P

Chaque circuit est élaboré et analysé **trois fois**, dans
trois dossiers distincts, via le vrai
`dependency_design()`, qui exécute slang puis sérialise index et graphe.
Les temps sont mesurés avec `time.perf_counter()`, et le script
publie les trois durées, le minimum, le maximum et la médiane.

À titre de photographie d'un run GitHub Actions Ubuntu 24.04 :

| Top | Médiane de la chaîne slang + index + graphe |
| --- | ---: |
| `counter` | environ **4 ms** |
| `hierarchy_top` | environ **5 ms** |
| `dependency_top` | environ **6 ms** |
| `advanced_logic` | environ **4 ms** |
| `cv32e40p_alu` | environ **183 ms** |

Ces durées **ne sont pas des garanties de performance**.
Elles varient selon la machine, les caches et l'activité
du runner. Elles ne comprennent ni l'attente dans
GitHub Actions ni le temps d'un échange avec un LLM.

### Sources officielles du CPU

Le script utilise notre précédent
[`scripts/run_cv32e40p_alu.py`](../scripts/run_cv32e40p_alu.py)
pour récupérer, vérifier et préparer le manifeste des
vraies sources **OpenHW CV32E40P** :

- dépôt : `openhwfoundation/cv32e40p` ;
- commit : `b353438ff469c030c89f6804f3b24a2852880e8b` ;
- package `cv32e40p_pkg.sv`, ALU et ses trois sous-modules ;
- empreintes Git blob vérifiées avant l'analyse ;
- version du compilateur : **slang v12.1**.

Le benchmark conserve les **empreintes SHA-256 des fichiers**,
la version du compilateur, l'environnement Python et les
comptes observés.

Résultat du premier run ALU :

| Mesure ALU | Résultat |
| --- | ---: |
| Modules / instances | **4 / 4** |
| Signaux / nœuds | **149 / 149** |
| Arêtes orientées | **319** |
| Avertissements | **11** |

L'ALU est **non étiquetée exhaustivement** dans ce benchmark.
Deux questions exploratoires concernent `result_o` et
`comparison_result_o`. Le graphe peut être
tronqué par la limite de **100 arêtes par parcours**,
comme dans notre serveur MCP : le rapport doit
signaler explicitement `trace_truncated`.

**Un test CPU réussi ici ne prouve ni l'absence d'arêtes fausses,
ni la conformité fonctionnelle de l'ALU.**

## 5. Comment reproduire la mesure

### Cas simples uniquement

Installer slang v12.1 et RTLPrep dans l'environnement :

```bash
python -m pip install -e '.[dev]'
slang --version

python scripts/run_rtl_benchmark.py \
  --out reports/rtl-benchmark \
  --repeat 3 \
  --timeout 180
```

### Ajouter le vrai processeur RISC-V

```bash
git clone https://github.com/openhwfoundation/cv32e40p.git upstream_cv32e40p
git -C upstream_cv32e40p checkout b353438ff469c030c89f6804f3b24a2852880e8b

python scripts/run_cv32e40p_alu.py \
  --source-root upstream_cv32e40p \
  --out reports/benchmark-cpu-prep

python scripts/run_rtl_benchmark.py \
  --out reports/rtl-benchmark \
  --repeat 3 \
  --cpu-manifest reports/benchmark-cpu-prep/cv32e40p_alu_design.json
```

Ces étapes sont également exécutées dans
[`.github/workflows/rtl-benchmark.yml`](../.github/workflows/rtl-benchmark.yml).

La compilation **échoue explicitement** si slang est absent
ou si un statut n'est pas `passed`. Le script refuse aussi
des graphes différents entre les répétitions.

Les résultats se trouvent dans :

```text
reports/rtl-benchmark/
├── benchmark_report.json                  # Synthèse A/B/C + métriques
├── counter/benchmark.case.json
├── hierarchy/benchmark.case.json
├── dependencies/benchmark.case.json
├── advanced/benchmark.case.json
└── cv32e40p_alu/benchmark.case.json
```

Les dossiers `run-01/`, `run-02/` et `run-03/`
de chaque cas contiennent les **véritables artefacts slang**.
La CI publie la synthèse, les rapports détaillés et
des diagnostics (conservation : **14 jours**).

## 6. Pourquoi ce benchmark est utile pour ChatGPT web

Tu utilises surtout **ChatGPT sur navigateur** : nous pouvons
donc déjà exploiter **GitHub comme source de vérité**.
Le workflow GitHub Actions exécute les mesures, et la
conversation sert à examiner les rapports enregistrés.

Pas besoin d'ajouter tout de suite un serveur MCP distant :
notre premier MCP local reste disponible pour Codex,
mais la mesure scientifique **ne dépend d'aucun agent**.

## 7. Ce qu'il faudra tester pour évaluer réellement un agent

Un **second jalon** pourra vérifier si le contexte structuré
améliore *réellement* des réponses d'un modèle :

1. Constituer un **jeu de questions tenu à l'écart du
   développement**, avec réponses et sources indépendantes.
2. Poser **exactement les mêmes questions** au **même modèle**
   et aux **mêmes paramètres** en A, B et C.
3. Noter la réponse selon une grille stable : fait correct,
   source exacte, incertitude correctement reconnue,
   erreur, hallucination, omission.
4. Mesurer le **vrai tokenizer du modèle**, les appels
   d'outils, la latence et le coût facturé (si applicable).
5. Répéter les essais, publier les intervalles
   et **signaler les coûts** au lieu de les inventer.
6. Séparer la comparaison des textes d'agent de
   la qualité du graphe et des propriétés formelles.

Aucun de ces résultats **LLM** n'est présent dans la PR #16.
Le projet peut continuer à fonctionner sans API LLM payante.

**Notre règle demeure : mesurer d'abord, complexifier ensuite.**

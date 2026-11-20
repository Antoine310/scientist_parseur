# Feuille de route — RTLPrep vers un assistant d'analyse RTL pour HOST 2027

> **Version du plan : 19 novembre 2026.**
> Ce document est un plan de développement, pas une liste de fonctions déjà disponibles.
> Objectif : utiliser **les meilleurs outils open source existants** et écrire seulement
> notre couche d'indexation, d'orchestration et d'interrogation. **Pas d'API LLM payante
> obligatoire** et pas de réécriture d'un compilateur SystemVerilog.

## 0. Situation actuelle : v0.1

**Déjà présent dans `main` :**

- CLI Python : `doctor`, `analyze`, `lint`, `synth`, `all`.
- Manifestes `design.json` et rapports JSON / logs.
- Invocation de l'exécutable **slang** puis extraction sommaire d'instances/ports
  avec `summarize_ast` (pas encore un graphe de dépendances).
- Invocation de **Verilator** (lint) et **Yosys** (synthèse).
- Un compteur SystemVerilog d'exemple, des tests unitaires Python et GitHub Actions.
- Une [documentation pédagogique en français](README.md).

**À ne pas confondre avec du déjà-fait :** l'appel direct à `pyslang`, les requêtes
`fan-in` / `fan-out`, la simulation cocotb, les preuves SBY/EQY, un serveur MCP
et un agent LLM autonome **n'existent pas encore**.

## Principes techniques

1. **Miser sur les compilateurs existants.** `slang` / `pyslang` pour la structure et
   l'élaboration ; Verilator et cocotb pour les tests ; Yosys, SBY, EQY et éventuellement
   OpenROAD pour les analyses spécialisées.
2. **Garder toujours accès au RTL original.** Un JSON résumé peut perdre une condition,
   un paramètre, la portée d'une expression ou la provenance du signal.
3. **Séparer les responsabilités.** Analyseur → index stable → outils de requête →
   contrôles EDA → interface agent (optionnelle).
4. **Ne jamais inventer un résultat.** Distinguer outil absent, erreur, timeout,
   test réussi, test échoué, preuve démontrée et preuve inconclusive.
5. **Isoler les designs tiers.** Exécuter compilateurs et simulations dans un
   conteneur/runner non privilégié, avec limite de durée, ressources, accès réseau
   contrôlé et répertoires de travail séparés.
6. **Documenter en même temps que le code.** Une PR fonctionnelle doit mettre à jour
   le cours correspondant et ses tests.
7. **Éviter la dépendance à un LLM.** Tous les outils doivent fonctionner depuis une
   CLI Python, même sans Codex ni API.

---

## Phase A — Stabiliser le socle (v0.2)

**Point de progression (novembre 2026) :** les tests d'intégration
avec slang v12.1 sont désormais lancés sur GitHub Actions.
L'exemple multi-instances a montré l'importance de gérer le cache
d'instances ; la solution provisoire est `--disable-instance-caching`.
Voir [docs/slang-environnement.md](slang-environnement.md).
La phase A reste **partiellement achevée** tant que les packages, includes,
paramètres, versions d'outils et provenance source ne sont pas couverts.

**Priorité : bloquante.** Avant d'ajouter de l'IA, il faut être certain que l'AST
extrait correspond vraiment aux designs traités.

**Travaux :**

- Établir un environnement EDA reproductible (documentation Linux/WSL2,
  versions de slang, Verilator et Yosys ; script d'installation ou conteneur).
- Ajouter des tests d'intégration exécutant **le vrai slang** sur le compteur et
  sur au moins un design à plusieurs modules, avec `skip` clair si absent.
- Valider les options de la CLI slang utilisées dans `runner.analyze` et le
  format JSON réellement exporté. Adapter `analysis.py` à ces sorties.
- Vérifier l'analyse des fichiers multi-sources, des `include`, des packages
  simples et des paramètres de base.
- Enrichir `doctor` : outils, chemins, versions, aide exploitable si manquants.
- Écrire les versions des outils et les paramètres effectifs dans les rapports ;
  améliorer `fingerprint` pour couvrir les entrées réellement pertinentes.

**Livrable :** `rtlprep analyze` affiche un inventaire d'instances/ports fiable et
traçable sur deux exemples réels, avec références au code source.

**Critères d'acceptation :**
- Le nombre d'instances est vérifié contre la hiérarchie connue des exemples.
- Aucune liste vide silencieuse si le schéma AST est inattendu.
- `pytest` passe et la CI distingue tests unitaires et tests EDA.
- Documentation des versions testées et des limites restantes.

---

## Phase B — Index structurel et navigation (v0.3)

**Priorité : très haute.** Cette étape donne au futur LLM de la bonne information
plutôt qu'un énorme fichier de RTL brut.

**Travaux :**

- Étudier deux backends : sortie JSON de `slang` actuelle et bindings Python
  `pyslang`. Choisir selon la couverture et les tests ; ne pas tout réécrire.
- Définir un **schéma d'index interne** versionné (JSON), indépendant du backend :
  modules, instances, chemins hiérarchiques, ports, signaux, types, largeurs,
  paramètres résolus et emplacements fichier/ligne.
- Écrire `list_modules()`, `get_module_summary()`, `get_instance_tree()`,
  `get_signal_info()`, `get_source_context()`.
- Gérer les modules paramétrés et les instances multiples d'un même module.
- Ajouter une commande `rtlprep index ...` et des sorties structurées pouvant
  être consommées ultérieurement par Codex/MCP.

**Livrable :** naviguer depuis une instance de CPU jusqu'à son fichier RTL exact.

**Critères d'acceptation :**
- Une requête renvoie une provenance fiable, et non une réponse inventée.
- Plusieurs instances d'un même module restent distinguées par leur chemin.
- Le résultat est déterministe avec les mêmes sources, paramètres et outils.
- Tests unitaires + tests d'intégration sur un petit projet multi-modules.

---

### Phase B — premier jalon implémenté

Le nouveau module `rtlprep/index.py` produit un index JSON
`schema_version: 1` des **modules, instances, ports et déclarations
`Variable/Net`**, avec leur provenance quand slang la fournit.
Les requêtes `modules`, `tree`, `module`, `instance`, `signal`
et les extraits de fichier sont disponibles depuis la CLI.

Voir [docs/index-rtl.md](index-rtl.md). Ce n'est **pas** encore
un graphe de dépendances, et les spécialisations paramétrées, interfaces
et scopes complexes nécessitent encore des travaux.

## Phase C — Graphe de dépendances (v0.4)

**Priorité : très haute.** C'est la fonctionnalité différenciante de RTLPrep.

**Travaux :**

- Construire un graphe typé avec des arêtes **lecture de donnée**, **écriture**,
  **condition de contrôle**, **horloge/reset** et **connexion de port**.
- Relever les expressions et leurs symboles, en respectant la portée et les
  références résolues par le compilateur ; distinguer combinatoire et séquentiel.
- Exposer `get_signal_fanin()`, `get_signal_fanout()`,
  `get_register_writers()`, `trace_signal()`.
- Attacher à chaque arête une preuve de provenance (source/ligne, expression).
- Prévoir des protections contre les cycles, les énormes graphes et les traversées
  non bornées : profondeur, nombre de nœuds et pagination.
- Tester indépendamment les macros, les sélections de bits, les `generate`,
  les expressions de port et les registres temporisés.

**Livrable :** répondre à « Qu'est-ce qui peut modifier `stall` ? » et fournir les
chemins RTL concernés.

**Critères d'acceptation :**
- Pour un lot de circuits tests, les dépendances attendues sont comparées à une
  vérité de référence rédigée à la main.
- Aucun lien de dépendance purement supposé par un LLM.
- Mesure des omissions, faux positifs et temps de requête.

---

## Phase D — Validation matérielle automatisée (v0.5)

**Priorité : haute.** Les réponses de l'index doivent ensuite être confrontées
aux outils EDA et aux spécifications.

**Travaux :**

- Ajouter de vrais testbenches **cocotb + Verilator** sur des circuits d'entraînement
  autorisés (compteur, petite FSM, ALU, puis module RISC-V).
- Intégrer **SBY** pour des propriétés explicites ; **EQY** lorsque l'équivalence
  est adaptée à la question étudiée.
- Enrichir les rapports Yosys ; garder le **nombre de cellules** séparé des mesures
  de surface physique. OpenROAD ne vient que si nécessaire.
- Uniformiser les statuts : `passed`, `failed`, `missing_tool`, `timeout`,
  `inconclusive`, avec traces et contre-exemples préservés.
- Exécuter les outils dans un environnement isolé ; budgets CPU/mémoire/temps ;
  ignorer toute commande provenant des logs ou du RTL.
- Éviter de relancer les analyses inchangées grâce à un cache basé sur une
  empreinte complète (sources, dépendances, paramètres, versions d'outils).

**Livrable :** une seule commande génère un rapport de compilation, simulation,
propriétés vérifiées et synthèse sur le compteur et une FSM.

**Critères d'acceptation :**
- Les échecs intentionnels des tests sont correctement rapportés.
- Une simulation réussie n'est jamais présentée comme une preuve complète.
- Chaque expérience est reproductible avec versions et fichiers enregistrés.

---

## Phase E — Banc d'essai CPU et compatibilité HOST (v0.6)

**Priorité : haute après A–D.**

**Travaux :**

- Passer à des sous-modules de **CV32E40P** ; n'essayer CVA6 qu'une fois
  les petites hiérarchies fiables.
- Construire des adaptateurs de manifests/filelists pour les outils déjà présents
  dans les dépôts sources, sans recopier le code tiers dans notre dépôt.
- Mettre en place un petit catalogue de circuits d'entraînement (IP, FSM,
  ALU, sous-système avec bus), avec tests et spécifications publiques.
- Prévoir un import du design d'entraînement et du validateur annoncés par
  GhostGate 2027 **lors de leur publication effective** : interfaces et règles
  de l'édition à revérifier, sans supposer que le CV32E40P reviendra.
- Réaliser des expériences **contrôlées** d'injection de faute pour tester la
  qualité des diagnostics et de la validation, uniquement sur des bancs d'essai
  autorisés.

**Livrable :** analyse reproductible d'au moins un module réel CV32E40P,
sans réglage codé en dur pour un seul processeur.

**Critères d'acceptation :**
- Même CLI pour le compteur, une IP et un module RISC-V.
- Échecs explicites si une configuration d'élaboration n'est pas supportée.
- Les tests sont traçables et les dépendances externes identifiées.

---

## Phase F — Codex, conversation et MCP (v0.7)

**Priorité : après un socle de validation fiable. Budget API : 0 € possible.**

**Travaux :**

- Conserver GitHub comme source de vérité, `AGENTS.md` et les tests CI.
- Créer des API Python internes stables pour les outils en **lecture** et validation.
- Ajouter facultativement un petit **serveur MCP** avec liste blanche des commandes,
  paramètres validés, timeouts, chemins autorisés et logs d'audit.
- Évaluer le flux Codex + dépôt GitHub avant d'ajouter un orchestrateur LLM autonome.
- Préparer une interface fournisseur LLM échangeable et **désactivée par défaut**.
  L'abonnement ChatGPT/Codex ne doit pas être confondu avec une API programmable
  générale gratuite.

**Livrable :** depuis Codex ou un client MCP configuré, lire le résumé d'un
module, retrouver une dépendance et demander une validation EDA.

**Critères d'acceptation :**
- Tous les résultats restent utilisables via la CLI, sans accès à un modèle.
- Le modèle ne peut pas lancer une commande arbitraire.
- Les résultats d'outils sont associés aux sources réellement testées.

---

## Phase G — Benchmark et optimisation finale (v0.8)

**Priorité : après E/F. Ne pas choisir une architecture multi-agents avant de mesurer.**

Comparer trois stratégies sur le **même ensemble de tâches** et au moins
quelques circuits de complexités différentes :

| Stratégie | Contexte fourni |
| --- | --- |
| A — brut | Extraits RTL non enrichis |
| B — index seul | Informations structurées sans accès au code exact |
| C — hybride | Index + code RTL original à la demande |

**Mesures :**

- Exactitude des réponses (modules, ports, registres, dépendances, provenance).
- Couverture des questions et taux de réponses « inconnu » justifiées.
- Taux de réussite des tests et propriétés **définies explicitement**.
- Nombre de tokens, coûts éventuels, temps total et appels d'outils.
- Régressions lors du changement d'architecture cible.

**Décision :** n'ajouter un deuxième agent, une base vectorielle ou des modèles
plus coûteux que si un benchmark reproduit un gain mesuré.

---

## Ordre des prochaines pull requests

| Ordre | Titre proposé | Pourquoi maintenant |
| --- | --- | --- |
| 1 | `test: real slang AST integration` | Corriger d'abord le risque de faux résumé |
| 2 | `feat: versioned RTL index + source locations` | Fournir des requêtes fiables |
| 3 | `feat: signal data/control dependency graph` | Cœur scientifique du projet |
| 4 | `feat: cocotb simulation harness` | Vérifier réellement les hypothèses |
| 5 | `feat: SBY/EQY report adapters` | Compléter les diagnostics |
| 6 | `feat: CV32E40P integration fixture` | Sortir des jouets |
| 7 | `feat: read-only MCP service` | Relier les outils à Codex/ChatGPT |
| 8 | `bench: raw vs indexed vs hybrid` | Optimiser sur des chiffres |

Chaque PR : **code + tests + documentation + résultats d'exécution et limites**.
Aucune fusion automatique dans `main`.

## Priorités et dépenses

- **Maintenant :** A puis B, entièrement sans API LLM. La priorité absolue est
  de vérifier le format réel des AST et de fiabiliser l'index.
- **Ensuite :** C puis D. La valeur de l'outil vient des dépendances fiables
  et de la validation par de vrais outils.
- **Plus tard :** E puis F. Le dépôt et Codex suffisent au développement avant
  une intégration LLM autonome.
- **Pour le concours :** G et les adaptations au matériel officiel, une fois
  publié. Les cibles exactes et les exigences devront être confirmées.

### Première tâche concrète à donner à Codex

> Sur une nouvelle branche, implémente un test d'intégration de `rtlprep analyze`
> avec le vrai exécutable `slang` sur `examples/counter/counter.sv` et un second
> circuit multi-modules. Détecte clairement le cas où slang est absent, vérifie
> le schéma de l'AST généré et empêche un résumé faussement vide de passer.
> N'ajoute aucun LLM ni service payant. Mets à jour le chapitre pédagogique
> du parseur, lance tous les tests disponibles et ouvre une pull request.

**Point d'arrêt recommandé :** ne pas démarrer les algorithmes de graphe avant
d'avoir validé le traitement d'au moins deux AST réels.

# RTLPrep — Registre vivant des limites, optimisations et validations

**Version : 1.3 — 25 novembre 2026 (validation locale #68 et chantier #69)**  
**Dépôt :** [Antoine310/scientist_parseur](https://github.com/Antoine310/scientist_parseur)  
**Dernière PR fusionnée confirmée : #67** (`614be44c02c86b0d4a9f10a6883aa8bbe9c8fcdf`). 37/37 CI sur le head testé.
**PR en cours : #68** (validation locale réussie, CI à revérifier) et #69 (empilée sur #68, validation à effectuer).

## 1. Mode d'emploi — à transmettre à chaque nouvelle conversation

Ce document complète la feuille de route et les rapports de validation ; il ne les remplace pas. Il conserve **les dettes par PR d'origine réelle**, même lorsqu'une autre PR les corrige plus tard. Ne jamais renuméroter les identifiants historiques. La PR documentaire est distincte de la #65 ; les numéros de développement proposés après son intégration restent indicatifs.

- `[ ]` ouvert ; `[~]` partiellement résolu ; `[?]` à mesurer ou auditer ; `[x]` clôturé avec preuve.
- **P0** : exactitude, omission dangereuse, budget ou reproductibilité bloquant l'évaluation. **P1** : amélioration prioritaire du moteur / validation. **P2** : extension, performance ou ergonomie. **P3** : objectif ultérieur.
- À chaque PR : lire ce registre avant de choisir le périmètre ; rattacher les corrections aux identifiants existants ; enregistrer les nouveaux problèmes, même mineurs ; conserver les mesures avant/après, le commit et les tests ; ne clôturer une ligne qu'avec un critère satisfait et une référence vérifiable.
- Une ligne partiellement traitée reste ouverte ; préciser son sous-périmètre corrigé. Les travaux différés ne disparaissent pas lorsqu'une PR est fusionnée.
- Conserver les anciens rapports et les labels gelés. Ajouter de nouvelles annotations distinctes avant de mesurer le moteur. Ne jamais ajuster un oracle pour masquer une régression.
- Ne pas fusionner sans accord explicite, validation locale pertinente et CI verte sur le **head exact**. Ne pas modifier `main` directement, le RTL officiel, les modifications locales de l'utilisateur ou effacer `docs/agent-reports/`.
- Ce fichier versionné (`docs/rtlprep-backlog.md`) est la référence de reprise. Le consulter dans `main` au début de chaque chantier et le mettre à jour dans chaque PR concernée (même si aucune dette n'est clôturée). Le fichier n'est pas mis à jour automatiquement entre les conversations. Maintenir les IDs historiques, les rapports et les critères de clôture ; ne pas dupliquer une dette sous un nouvel ID lorsqu'un lien suffit.

**Contrat scientifique :** compilation ≠ analyse complète ; dépendance syntaxique ≠ influence fonctionnelle ; position de bit ≠ égalité de valeur ; simulation échantillonnée ≠ preuve ; aucune troncature ≠ support exhaustif. Une précision de 100 % sur des labels ne mesure pas les relations non annotées. Les compteurs de plusieurs analyseurs se recoupent : ne pas les additionner en un total de défauts.

## 2. État de référence — ne pas perdre ces chiffres

### ALU officielle CV32E40P

Même commit RTL `b353438ff469c030c89f6804f3b24a2852880e8b`. Métriques du graphe positionnel historique, pas une couverture de tout le design.

| PR | Affectations recensées | Supportées | Partielles | Arêtes bit à bit | Taux supporté |
|---|---:|---:|---:|---:|---:|
| #56 | 479 | 68 | 411 | 255 | 14,2 % |
| #57 | 479 | 222 | 257 | 445 | 46,3 % |
| #60 | 479 | 222 | 257 | 445 | 46,3 % |
| #61–62 | 479 | 254 | 225 | 477 | 53,0 % |

Décomposition exacte des **225** cas à la #62 :

| Cause | Nombre | Origine du compteur |
|---|---:|---|
| `dynamic_or_unknown_index` | 63 | bit_accesses |
| `unsupported_rhs_BinaryOp` | 50 | bit_accesses |
| `conversion_width_unproven_or_changed` | 39 | bit_accesses |
| `target_rhs_width_mismatch` | 36 | bit_accesses |
| `unsupported_rhs_ConditionalOp` | 35 | bit_accesses |
| `target_rhs_width_mismatch` | 1 | bit_dependency_graph seul |
| `unproven_packed_layout` | 1 | bit_dependency_graph seul |
| **Total** | **225** | 223 + 2 |

#62 ALU : expressions 612 recensées / 51 partielles ; constructions complexes 1 188 / 56 appels partiels ; fonctions directes 33/33 partielles (32 cibles non supportées, 1 identité locale non résolue) ; tableaux 94 / 33 supportés / 61 partiels (31 indices dynamiques/non prouvés, 30 chaînes de sélection non supportées) ; intercycle 8 / 7 supportés / 1 partiel ; 5 avertissements signal ; liste de constats de couverture tronquée. Ces chiffres ne sont pas nécessairement les mêmes après la correction signal de #64. Ne pas extrapoler les métriques ALU au cœur.

### Cœur complet — première mesure #65

Configuration entière officielle : `COREV_PULP=0`, `COREV_CLUSTER=0`, `FPU=0`, `ZFINX=0`, latences FPU nulles, `NUM_MHPMCOUNTERS=1`, fichier de registres FF, clock gate comportemental officiel. Pas de wrapper substituant le cœur. Pas de simulation de programmes à ce stade.

| Mesure | Résultat local |
|---|---:|
| Tests Python | 812/812, aucun skip |
| Modules distincts / instances | 23 / 24 |
| Nœuds / arêtes signal / avertissements | 1 597 / 3 566 / 15 |
| Labels directs TP / TN / FP / FN | 39 / 8 / 0 / 0 |
| Sondes intermodules observées | 7/7 |
| Analyseurs tronqués | `expressions`, `complex_constructs` |
| Temps pipeline total (1 échantillon) | 2,122 s |
| Temps slang / construction graphe | 0,202 s / 0,858 s |
| Pic RSS Python / slang, séparément | 181 564 / 209 504 Kio |
| AST / index / graphe | 43 903 215 / 748 935 / 16 550 504 octets |

Rapport local : `reports/pr65/run-z8ycwvw9/core.result.json`. **Le résumé transmis ne contient pas les compteurs bit à bit détaillés du cœur.** Les extraire du rapport, ne pas les inventer.

## 3. Registre des dettes par PR d'origine

### PR #1–#16 — Audit historique complété

- [~] **PR01-16-AUDIT-01 · P2** — Les 16 descriptions GitHub sont maintenant relues ; les dettes ci-dessous en reprennent les limites. Un audit exhaustif du code et des tests à chaque ancien head reste distinct. Clôture : vérifier les cas ouverts sur la version courante, rattacher preuves et éventuels nouveaux défauts, ne pas traiter les anciennes descriptions comme état actuel automatique.

### PR #1 — Initialisation RTLPrep

- [?] **PR01-BASE-01 · P2** — Revoir le parcours initial analyse → validation → Codex et les instructions de l'agent au regard du moteur actuel. La description établit le périmètre initial, pas une liste de bugs. Clôture : guide de reprise testé sur un environnement frais.

### PR #2 — Guide pédagogique

- [ ] **PR02-DOC-01 · P2** — Actualiser le guide AST/index/graphe pour les dix analyseurs et les différents niveaux de preuve. Clôture : exemples vérifiés, schémas et limites cohérents avec #65 et les évolutions.

### PR #3 — Feuille de route HOST 2027

- [~] **PR03-PLAN-01 · P2** — Roadmap d'origine réorganisée dans la section 4 ; conserver les objectifs différés et les critères d'acceptation, sans assimiler un objectif à une PR réelle. Clôture : revue régulière et traçabilité des objectifs FUT-*.

### PR #4 — Fiabilisation AST slang

- [?] **PR04-AST-01 · P1** — Rejouer erreurs de compilateur, AST malformé, absence de top et échec sans artefact périmé sur le chemin whole-core actuel. C'est une vérification proposée, pas une régression reproduite. Clôture : tests fail-closed et diagnostic source.

### PR #5 — CI vrai slang v12.1

- [~] **PR05-CI-01 · P2** — Maintenir le test réel slang et comparer local/CI ; consolider les installations seulement sans perdre les validations historiques. Voir PR62-CI-01 et PR26-ENV-01.

### PR #6 — Index RTL et requêtes CLI

- [~] **PR06-INDEX-01 · P1** — Les connexions de ports et generate complexes étaient initialement limités ; plusieurs avancées depuis #7/#29. Vérifier les variantes paramétrées regroupées sous un nom de module, scopes imbriqués, résolution par instance et provenance de déclaration. Clôture : tests d'identités distinctes et requêtes par instance ; aucun alias déduit du seul nom.

### PR #7 — Graphe signal typé

- [ ] **PR07-PORT-01 · P1** — Ports InOut hors périmètre initial ; auditer aujourd'hui InOut/ref/interfaces/modports et connexions complexes. Ne pas supposer une direction ni inventer une arête. Clôture : modèle explicite de lecture/écriture, fixtures réelles, refus documenté des cas ambigus.
- [ ] **PR07-TRACE-01 · P1** — Bornes fan-in/fan-out : distinguer limite de profondeur, plafond d'arêtes, cycles et absence réelle d'arête ; une trace bornée ne prouve pas l'indépendance. Clôture : diagnostics et tests aux seuils (voir PR52-HIER-01).

### PR #8 — Case, concaténations et generate

- [~] **PR08-SV-01 · P1** — Casez/casex, generate imbriqués, références hiérarchiques et appels restent à vérifier au-delà du périmètre historique. Clôture : inventaire des constructions actives, tests real slang, exclusions explicites. Voir PR20-PROC-01, PR29-GEN-01, PR58-FUNC-01.

### PR #9 — Décodeur compressé CV32E40P

- [~] **PR09-DEC-01 · P1** — Premier test réel, pas validation de toute l'ISA ; constantes de package améliorées #10. Élargir les labels bit et les oracles d'encodage sur le décodeur officiel CV32E40P (distinct de CVA6). Clôture : cas valides/illégaux, familles et limites documentées.

### PR #10 — Constantes/enum et ALU officielle

- [~] **PR10-ALU-01 · P1** — Call, bit, generate et temporalité signalés dans la description ; #57/#61/#64 corrigent une partie seulement. Clôture : baseline ALU par catégorie, constantes sans fausses arêtes runtime, traitement lié à PR61-BIT-01 et PR58-FUNC-01.

### PR #11 — Simulation compteur/FSM

- [ ] **PR11-SIM-01 · P1** — Étendre les oracles indépendants et les contrôles négatifs des petites IP aux scénarios CPU. Pas de couverture exhaustive à partir d'échantillons. Clôture : tests gold/mutants, distinction échec de compilation/assertion, traces et critères reproductibles. Voir PR65-SIM-01.

### PR #12 — SBY compteur/FSM

- [ ] **PR12-FORMAL-01 · P1** — Propriétés RISC-V complexes encore à traiter ; préserver liste blanche des bancs et sources, pas d'exécution arbitraire de fichier SBY ou de RTL non fiable. Clôture : prove/cover/BMC, hypothèses, contre-exemples et statut inconclusive explicite.

### PR #13 — EQY sur petites IP

- [ ] **PR13-EQY-01 · P1** — Élargir les cas d'équivalence et non-équivalence ; deux circuits équivalents peuvent partager un défaut. Clôture : référence indépendante lorsque pertinente, modèle et partitions, distinction PASS/FAIL/inconclusive, ni timing ni CDC inférés.

### PR #14 — EQY popcount officiel

- [ ] **PR14-EQY-01 · P1** — Les 31 partitions EQY historiques ne sont pas 31 preuves de conformité à une spécification. Étendre à des blocs réels sélectionnés avec pins et transformations vérifiées. Clôture : équivalence et mutation contrôlée, preuves distinctes de la correction fonctionnelle, sources autorisées.

### PR #15 — MCP v2 lecture seule

- [ ] **PR15-MCP-01 · P1** — Snapshot chargé au démarrage, régénération explicite, chemins sélectionnés par l'opérateur. Pas d'exécution EDA arbitraire ni de sandbox du RTL hostile. Clôture : renouvellement contrôlé, validation de fraîcheur, tests de limites et d'accès ; voir PR18-MCP-01/02.

### PR #16 — Benchmark A/B/C

- [ ] **PR16-BENCH-01 · P1** — 51 labels sur petits circuits, 7 questions, mesure UTF-8 et mots approximatifs ; aucun LLM interrogé. Le contexte hybride était plus lourd que RTL brut sur les petits exemples et la trace cpu_result tronquée à 100 arêtes. Clôture : benchmark CPU avec corpus gelé plus large, vrais tokens/latence/coût et réponses agent contrôlées, comparaison à contexte égal, abstention et erreurs (FUT-AGENT-01).

### PR #17 — Laboratoire CSR / premières propriétés

- [ ] **PR17-FORMAL-01 · P1** — Étendre les propriétés d'autorisation, verrouillage, reset, état interdit et non-interférence à des blocs réels autorisés. Un graphe identique peut masquer des comportements différents. Clôture : propriétés précisément définies, hypothèses, preuve/contre-exemple, mutants détectés par assertion et non par compilation.

### PR #18 — Codex et MCP

- [ ] **PR18-MCP-01 · P1** — Exposer les nouveaux analyseurs #51–65, coordonnées de tableaux, limites, provenance et diagnostics de chemins dans les outils MCP ; auditer ce qui est déjà accessible. Clôture : tests stdio réels sur un snapshot CPU, réponses bornées, pas d'inférence non démontrée.
- [ ] **PR18-MCP-02 · P1** — Traçabilité, pagination, taille des réponses, version des schémas et cohérence du snapshot ; pas de commandes libres issues du RTL ou de sorties d'outils. Clôture : tests négatifs et contrôle d'accès lecture seule ; éventuels outils d'exécution sur liste blanche et autorisation explicite.

### PR #19 — Expressions

- [~] **PR19-EXPR-01 · P0** — Arithmétique, opérateurs, appels et profondeur ; #62 ALU 51/612 expressions partielles (raison générique `partial_record`). #65 troncature. Clôture : raisons détaillées par construction/instance, oracles positifs/négatifs, rapport sans troncature non expliquée. Voir PR65-LIMIT-01.

### PR #20 — Analyse procédurale

- [ ] **PR20-PROC-01 · P1** — Inventaire et traitement des blocs, conditions complexes, `casez/casex`, boucles et formes procédurales non reconnues ; vérifier les exclusions silencieuses. Clôture : fixtures real slang, tests de branches et cas rejetés explicitement ; ne pas généraliser le support de `case` normal.

### PR #21 — Écritures et NBA

- [~] **PR21-NBA-01 · P1** — Dernière NBA locale traitée dans le périmètre actuel ; priorités entre processus, écritures partielles/chevauchantes, blocking/NBA mixtes, hold et ordre de simulation restent à caractériser. Clôture : oracles de transitions, mutants d'ordre et preuves ciblées. Voir #47/#51.

### PR #22 — Accès aux bits

- [~] **PR22-BIT-01 · P1** — Sémantique générale bit à bit non achevée. Voir #34, #39, #40, #54, #57 et #61 pour les extensions et compteurs. Clôture : chaque construction recensée classée avec une représentation justifiée ou une abstention explicite.

### PR #23 — Couverture et métriques

- [ ] **PR23-COV-01 · P0** — Dénominateurs distincts, omissions non recensées, signaux sans arêtes, exclusions et troncatures de constats. `design_coverage=not_measured` demeure. Clôture : inventaire indépendant de l'AST pertinent par instance/construct, compteurs réconciliés et limites visibles. Voir #56/#62/#65.

### PR #24 — Candidats séquentiels / reset

- [~] **PR24-SEQ-01 · P1** — Ne pas assimiler événement à cycle ni candidat à transition garantie ; reset asynchrone/synchrone, enables, chemins incomplets, initialisation, latches et multi-horloges à étendre. Clôture : modèles et hypothèses testés par simulation/formel. Voir #48/#51/#52.

### PR #25 — Evidence et preuves

- [ ] **PR25-EVID-01 · P1** — Renforcer association exacte relation/propriété/hypothèses/source/paramètres et versions des outils ; gérer preuves obsolètes et contre-exemples. Clôture : tests de mauvais fingerprint, mauvaise propriété, statut `unknown` et preuves liées au bon périmètre.

### PR #26 — Toolchains

- [~] **PR26-ENV-01 · P2** — Reproductibilité Linux et versions épinglées ; local Verilator 5.055 dev, CI 5.040. Vérifier compatibilité Python 3.11/3.12, erreurs d'installation et dépendances. Clôture : matrice documentée et tests de versions sans supposer des résultats identiques.

### PR #27 — Import de filelists

- [ ] **PR27-IMPORT-01 · P1** — Audit des filelists imbriquées, packages, includes, defines, paramètres, chemins et variantes de compilation, notamment CVA6/OpenTitan. Clôture : manifest reproductible, résolution exacte des sources et tests d'options malformées ; pas de commandes arbitraires.

### PR #28 — RTL externes simples

- [ ] **PR28-RTL-01 · P2** — Réévaluer `axis_register`, `priority_encoder`, `rxuart` sur le moteur actuel : métriques et annotations indépendantes, pas seulement zéro avertissement. Clôture : rapport comparatif, oracles et cas inconnus conservés.

### PR #29 / #30 — Generate et identité des symboles

- [~] **PR29-GEN-01 · P1** — Generate imbriqués, indices, noms d'instances/scopes, branches inactives et collisions ; vérifier cas paramétrés différents, sans rapprochement par nom seul. Clôture : fixtures multi-instances et annotations de non-confusion. #30 intégration historique ; pas de dette distincte connue sans audit.

### PR #31 — Événements

- [ ] **PR31-EVENT-01 · P1** — Sensibilités et fronts explicites ne suffisent pas à une analyse CDC ou d'horloge/reset ; modèles clock gating et événements complexes. Clôture : tests et diagnostics séparés pour horloges, resets, événements inconnus. Voir #52/#65.

### PR #32 — Concaténations en cible

- [~] **PR32-LVALUE-01 · P1** — Mapping cible concaténée conservateur, notamment segments non scalaires et conversions ; aucune approximation all-to-all présentée comme position exacte. Clôture : oracle sur concaténations mixtes et cas ambigus rejetés.

### PR #33 — Initial et sélections

- [ ] **PR33-INIT-01 · P2** — Initialisations plus complexes, interaction reset/initial, sélection non littérale ; distinguer initialisation de dépendance d'exécution. Clôture : fixtures et conditions d'abstention vérifiables.

### PR #34 — Expressions structurées / segments de bits

- [~] **PR34-SEG-01 · P1** — Support partiel des sélections/concaténations/réplications et conversions ; voir #39/#54/#61. Clôture : segments exacts avec bornes, ordre et transformations, sans extension implicite devinée.

### PR #35 — Premier décodeur CVA6

- [ ] **PR35-CVA6-01 · P2** — Reprendre l'évaluation de CVA6 épinglé `742dc82a0c706e0a3bfb98b709fd3ee06d50d12a`, config historique `cv32a6_imac_sv32` ; élargir à une sous-hiérarchie puis au cœur, avec dépendances/configuration cohérentes. Ne pas confondre avec le succès CV32E40P.

### PR #36 — MemberAccess

- [~] **PR36-TYPE-01 · P1** — Champs de structures au niveau signal : offsets packed/struct/union/typedef encore à résoudre explicitement. Clôture : identité de type et layout élaboré vérifiés, oracles de champs, rejets des alias ambigus.

### PR #37 — Cibles de champs

- [~] **PR37-LVALUE-01 · P1** — Écriture dans un champ, champ imbriqué, tranches et écritures concurrentes ; ne pas assimiler écriture d'un membre à écriture de tous les bits. Clôture : tests de conservation des autres champs et relations exactes.

### PR #38 — Accès procéduraux aux bits

- [~] **PR38-PBIT-01 · P1** — Étendre couverture des cibles et sources procédurales, conditions, boucles et écritures partielles. Clôture : comptage des affectations éligibles/exclues, scénarios blocking/NBA distincts. Voir #59/#60/#61.

### PR #39 — Largeurs élaborées et réplications

- [~] **PR39-WIDTH-01 · P1** — 51/52 accès CVA6 positionnés après #39 ; #40 résout le dernier UnaryOp dans ce corpus. Types alias/enum non résolus, conversions changeant de largeur, réplication non littérale et layout complexe restent hors du support général. Clôture : largeur démontrée, oracles extension signe/zéro/troncature, limites des types explicites. Voir PR61-BIT-02.

### PR #40 — Inversion bitwise

- [~] **PR40-UNARY-01 · P1** — 52/52 enregistrements syntaxiquement positionnés sur le décodeur CVA6 sélectionné, pas toutes les affectations du module. Compositions, `LogicalNot`, réductions, négation arithmétique : représenter les dépendances sans confondre transformation et copie. Clôture : oracles sur toutes familles retenues, mutants et abstentions justifiées.

### PR #41 — Oracle indépendant / mutant

- [ ] **PR41-ORACLE-01 · P1** — Étendre tests indépendants et mutants à chaque nouvelle sémantique bit à bit ; conserver cas gold, mutant et motif d'échec. Clôture : tests réellement exécutés, mutant compilé, assertion pertinente ; ne pas faire passer un échec outil pour une détection.

### PR #42 — CVA6 C.J

Périmètre documenté : 2 048 cas exhaustifs sur les 11 bits variables avec demi-mot haut nul ; pas sur les entrées 32 bits, ni X/Z.

- [~] **PR42-CJ-01 · P2** — Oracle C.J sur cas testés ; bit du mutant fixé par l'encodage. #43 élargit vers C.LI, mais il faut conserver et approfondir tests d'immédiats variables et contrôles de validité. Clôture : corpus ISA indépendant couvrant familles retenues et limites déclarées.

### PR #43 — CVA6 C.LI

Périmètre documenté : 2 048 demi-mots bas avec mot haut nul, plus 256 essais du haut ; modèle deux états.

- [ ] **PR43-COMP-01 · P2** — Élargir encore les encodages compressés et variantes, notamment limites immédiats, instructions réservées/illégales et sorties contrôle. Clôture : références ISA indépendantes, résultats par famille.

### PR #44 — Plusieurs familles compressées

Familles documentées : C.ADDI/C.NOP, C.ADDI4SPN, C.LW, C.SW ; 8 192 motifs bas + 1 024 échantillons hauts et quatre mutants. Ni exhaustivité ISA ni preuve formelle.

- [ ] **PR44-ISA-01 · P2** — Mesurer quelles familles/encodages restent non testés ; étendre la campagne et les mutants, sans revendiquer exhaustivité de l'ISA. Clôture : catalogue versionné avec dénominateur et exclusions.

### PR #45 — Lien statique/comportemental

Association simulation par famille, pas preuve par lane ; exposition MCP reportée dans la description.

- [ ] **PR45-EVID-01 · P1** — Généraliser association entre positions, simulation et preuve, par relation et par configuration ; cas où l'influence syntaxique ne se manifeste pas. Clôture : rapport exploitable par MCP et tests empêchant toute promotion automatique en preuve.

### PR #46 — RAS réel CVA6

Profondeur deux, RV32, modèle de pile indépendant ; les extensions de preuve/mutants sont traitées par #47–48 sur leur périmètre seulement.

- [ ] **PR46-RAS-01 · P2** — Étendre scénarios de pile de retours : limites, wrap, flush/reset, push/pop et configurations. Clôture : oracles indépendants et propriétés adaptées aux cas documentés, pas un modèle temporel général.

### PR #47 — Priorité d'écritures et mutants

- [~] **PR47-NBA-01 · P1** — Fixture NBA et RAS gold/mutants validés ; écritures partielles chevauchantes, processus multiples, ordre blocking et cas mixtes restant à traiter. Clôture : tests ciblés + propriétés quand possibles. Voir PR21-NBA-01.

### PR #48 — Reset / RAS formel

- [~] **PR48-FORMAL-01 · P1** — Preuves/cover ciblées et mutant contre-exemple validés, pas propriétés globales du CPU. Étendre couverture des hypothèses, induction, vivacité, clocks, vacuité et configurations. Clôture : rapport propriété par propriété avec résultats et contre-exemples.
- [x] **PR48-ENV-01** — Skips dus aux fixtures résolus par #50 dans la suite locale (528 réussis, 0 skip à #50). Ne pas confondre avec preuve sur tous les designs.

### Issue #49 — Installateur des fixtures (ce numéro n'est pas une PR)

- [x] **PR49-AUDIT-01** — Vérifié via l'API GitHub : [issue #49](https://github.com/Antoine310/scientist_parseur/issues/49), fermée, « Hors série — installateur reproductible des checkouts RTL externes ». Travail réalisé par la PR #50 ; l'intercycle réel est #51. ID historique conservé, aucune PR #49 inventée. Les extensions restantes relèvent de PR50-PIN-01.

### PR #50 — Fixtures externes épinglées

- [~] **PR50-PIN-01 · P1** — Installateur de 4 repos / 15 fichiers verrouillés ; #63–65 ajoutent pins locaux et snapshots sans toucher au checkout. Consolider inventaires si utile, vérifier dépendances includes, clones partiels et révisions. Clôture : provenance complète, vérification avant/après, aucun écrasement ou fetch silencieux.

### PR #51 — Dépendances intercycles locales

- [ ] **PR51-TIME-01 · P1** — Un événement local candidat, `guaranteed_cycles=None` ; ALU #62 7/8 supportés, 1 `unsupported_path`. Étendre enable/hold, reset, écritures partielles, chemins conditionnels et temporalité au cœur. Clôture : transitions vérifiées, contre-exemples, latences seulement si démontrées.

### PR #52 — Chemins hiérarchiques et frontières événementielles

- [ ] **PR52-HIER-01 · P1** — Traces bornées (16 hops / 128 chemins / 4 événements dans le périmètre historique) ; alias direct scalaire seulement. Clock gating, plusieurs horloges, CDC, latences et ports bit à bit restent à traiter. Clôture : chemins exacts, frontières explicites, simulation/formel lorsque pertinent ; pas de latence garantie devinée.

### PR #53 — Inventaire des constructions complexes

- [ ] **PR53-CPLX-01 · P0** — Inventaire des appels/sélections/boucles, pas leur sémantique. ALU #62 56 appels partiels ; cœur #65 troncature. Détailler par instance et type, distinguer inventaire syntaxique et résolutions #58–60. Clôture : comptage indépendant, raisons d'omission et budgets vérifiés.

### PR #54 — Graphe positionnel bit à bit

- [~] **PR54-BIT-01 · P1** — Graphe local d'affectation, positions exactes seulement ; pas propagation transitive bit à bit, connexions de ports, influence fonctionnelle ni comportement multi-écritures général. Clôture : graphes séparant position, dépendances potentielles, conditions et temps ; oracle sur hiérarchie.
- [ ] **PR54-BUDGET-01 · P1** — Limites 16 384 arêtes, largeur 1 024 ; détecter explosion arêtes pour opérateurs et tableaux sans dégrader silencieusement les positions. Clôture : représentation compacte ou troncature justifiée, tests aux bornes.

### PR #55 — Performances

- [ ] **PR55-PERF-01 · P2** — Benchmark synthétique 8/64/256/520 et ALU ; #65 cœur mesuré une fois. Répéter dans workers frais, rapport min/médiane/max, matériel et version ; mesurer requêtes fanin/fanout, MCP et gros JSON. Clôture : mesures reproductibles et comparables, sans confondre pics RSS séparés et mémoire simultanée.
- [ ] **PR55-PERF-02 · P2** — Profilage avant optimisation (construction graphe, sérialisation, lecture AST) ; envisager cache par fingerprint, index ciblé, compression/streaming, pagination si mesures le justifient. Clôture : gain mesuré, résultats sémantiques inchangés, pas de cache obsolète.

### PR #56 — Annotations scientifiques gelées

- [ ] **PR56-EVAL-01 · P0** — Corpus sélectionné par l'assistant, pas indépendant humain/aveugle ni représentatif. ALU gelé 65 positifs bit / 65 négatifs / 1 inconnu ; #57 TP65, FP/FN0 sur ce périmètre. Étendre labels de bits aux autres unités, cas difficiles, négatifs et inconnus ; validation par références indépendantes, éventuel reviewer externe. Clôture : précision/rappel/F1 avec dénominateurs, omissions, doublons et non-annotés, aucun extrapolation abusive.
- [ ] **PR56-EVAL-02 · P1** — Comparer graphe syntaxique, dépendances potentielles, influence fonctionnelle via simulation ciblée/miter formel. Clôture : catégories évaluées séparément et exemples de surapproximation (p. ex. `a ^ a`).

### PR #57 — Indices constants élaborés

- [~] **PR57-IDX-01 · P1** — 154 affectations ALU supplémentaires supportées. Evaluation bornée localparams et opérations simples ; paramètres d'instance étendus #61. Indices négatifs, ascendants, expressions constantes plus riches, casts, indexed part-selects, types alias restent à auditer. Clôture : valeurs et identités vérifiées par elaboration, rejet dynamique et cas aux bornes.

### PR #58 — Fonctions locales simples

- [ ] **PR58-FUNC-01 · P1** — Uniquement fonctions automatiques locales à retour unique et appels directs en continu ; globales, branches, nested calls, récursion, side effects, arguments par référence, procédural et bit mapping non couverts. ALU #62 33/33 lignes partielles. #64 traite `$signed/$unsigned` uniquement dans le lecteur signal, pas la totalité du rapport fonctions. Clôture : analyser classes successives et déclarer les exclusions, oracle d'arguments inutilisés et effets de bord.

### PR #59 — Boucles statiques

- [ ] **PR59-LOOP-01 · P1** — For/repeat littéraux simples, une écriture blocking, AlwaysComb, au plus 64 itérations ; fixture 3 supportées/2 partielles (19 positions). Étendre décréments, pas, bornes paramétrées, corps multiples, boucles imbriquées et procédurales, `foreach` ; rejeter les boucles non bornées. Clôture : oracle par itération et tests de budget sans déroulement excessif.

### PR #60 — Tableaux packed/unpacked

- [ ] **PR60-ARRAY-01 · P1** — Copies à coordonnées fixes en continu ; #62 ALU 61/94 partielles (31 indice dynamique/non prouvé, 30 chaîne non supportée). Traiter tableaux dynamiques au sens sélection à indice runtime, slices multidimensionnelles, types signés/alias et accès procéduraux ; register file CPU prioritaire. Clôture : coordonnées et dépendances conditionnelles/indices explicitement annotées, simulations et mutants, budgets.
- [ ] **PR60-ARRAY-02 · P1** — Unifier représentation des coordonnées packed/unpacked et bit graph sans double comptage ; conserver la distinction entre arêtes source et constantes cibles. Clôture : schéma compatible/versionné, références exactes et tests de migrations.

### PR #61 — Raffinement bit à bit (ALU)

- [x] **PR61-BIT-00** — 32 positions du diviseur retrouvées ; 160 positions constantes LUT validées dans le graphe tableau distinct ; 479/254/225/477 dans le graphe bit historique. #61 fusionnée, 720 tests, 32 CI. Ne pas ajouter 160 arêtes fictives.
- [ ] **PR61-BIT-01 · P0** — **225 affectations ALU partielles** : inventaire détaillé et baisse mesurée par famille ; conserver baseline 479 et labels #56. Clôture : chaque cas résolu ou caractérisé explicitement, preuve de non-régression ; ne pas exiger 100 % de copies directes.
- [ ] **PR61-BIT-02 · P1** — 39 conversions de largeur et 37 incompatibilités de largeur : extensions zéro/signe, troncatures, tailles contextuelles, constantes et types. Clôture : cas positifs/négatifs SV, oracle bit par bit, simulations et valeurs limites ; traiter conversion et mismatch sans double comptage.
- [ ] **PR61-BIT-03 · P1** — 50 opérateurs binaires : classifier bitwise AND/OR/XOR/XNOR, arithmétique, comparaisons, décalages ; commencer par bitwise, distinguer retenues/carries et dépendances potentielles. Clôture : oracles indépendants, pas de correspondance 1→1 sur addition/multiplication ; compression des grandes relations si nécessaire.
- [ ] **PR61-BIT-04 · P1** — 35 expressions conditionnelles : ternaires/mux, garde et dépendances conditionnelles, branches constantes, priorité et signal de sélection. Clôture : modèles de garde vérifiés, oracles et tests avec choix des branches ; aucune affirmation de faisabilité globale.
- [ ] **PR61-BIT-05 · P1** — 63 indices dynamiques/inconnus : sélecteurs, bornes, indices invalides, dépendances données/contrôle, four-state et tableaux de registres. Clôture : représentation conservatrice par conditions/ensembles de coordonnées, limites explicites et tests d'indices hors bornes. Lien PR60-ARRAY-01.
- [ ] **PR61-BIT-06 · P1** — 1 layout packed non prouvé : retrouver déclaration/type élaboré exact, direction et coordonnées. Clôture : test sur la source réelle et fixture qui rejette layout ambigu.

### PR #62 — Budgets globaux et diagnostics

- [ ] **PR62-LIMIT-01 · P0** — Distinguer le plafond réellement atteint (nombre de lignes, scan, profondeur, exclusions) ; #65 expressions/constructions complexes tronquées. Limites actuelles : AST 256 Mio / 3 M valeurs, graphe 5 M valeurs, profondeur 128 ; plafonds locaux restent. Clôture : diagnostic exact, budgets configurables bornés et tests aux seuils, propagation des troncatures.
- [ ] **PR62-LIMIT-02 · P1** — Gates d'admission/publication ≠ quotas mémoire/CPU/disque. Décodage et graphe alloués avant certaines gates, worker #55 à auditer pour lecture AST bornée et échec propre. Clôture : chemins d'entrée cohérents, limites de processus si nécessaires, tests d'échec/artefacts non périmés. Ne pas augmenter toutes les limites aveuglément.
- [ ] **PR62-COV-01 · P1** — Liste de findings de couverture tronquée sur ALU, raisons génériques et exclusions sans lignes. Clôture : total avant cap, détails paginés/par instance, état global honnête et audit des flags imbriqués. Voir PR23-COV-01.
- [ ] **PR62-CI-01 · P2** — Saturation GitHub (33+ workflows ; doubles événements push/PR et commits successifs). Annulation des runs obsolètes introduite seulement sur certains nouveaux workflows. Clôture : audit de déclencheurs, concurrency par ref, réutilisation d'installations et consolidation sans retirer de validations ; comparaison de durée et matrice avant/après, conserver tests de sécurité/formel.

### PR #63 — Évaluation multi-unités

- [ ] **PR63-MULTI-01 · P1** — 6/6 unités, 54 labels signal bien classés (37 TP,17 TN), 494 nœuds / 1 245 arêtes / 11 avertissements en analyses séparées. Bit à bit annoté seulement ALU ; autres unités à annoter. Clôture : tableau de métriques bit/expressions/seq/arrays par unité, corpus de référence ; aucune extrapolation de ces totaux au graphe intégré.
- [ ] **PR63-CONFIG-01 · P2** — Décoder standalone `COREV_PULP=1` vs controller `COREV_PULP=0` et RF wrapper explicite ; comparer aux variantes intégrées de #65 et réévaluer après #64 (cast). Clôture : configurations et fingerprints comparables, divergences expliquées.

### PR #64 — EX-stage réel

- [x] **PR64-CAST-00** — Correction signal des builtins `$signed/$unsigned` de même largeur/type intégral vérifié ; chemins multiplicateur 3/5 → 5/5 ; 792 tests, 44 labels corrects, 384 scénarios, 774 ns, 35 CI, fusion confirmée.
- [ ] **PR64-CAST-01 · P1** — Les casts restent à traiter dans les autres analyseurs (expressions, bit, fonctions), notamment changements de largeur et signe ; les arêtes ajoutées au signal ne prouvent pas position ou influence. Clôture : oracles spécialisés et non-régression #56/#61/#64.
- [ ] **PR64-EX-01 · P1** — Simulation limitée aux 64 triplets / 384 scénarios (XOR, égalité, MAC, priorités mux, LSU/jump/ready). Étendre MULH/division multi-cycle, signed/unsigned, stall, reset, EX/WB et handshakes ; cas réels d'instructions, pas seulement enables superposés artificiellement. Clôture : séquences temporelles vérifiées avec oracle indépendant.
- [ ] **PR64-LINT-01 · P2** — Avertissements Verilator `WIDTHTRUNC`, `WIDTHEXPAND`, `CASEINCOMPLETE`, `UNOPTFLAT` dans le RTL officiel ; analyser lesquels sont attendus ou significatifs, sans modifier le RTL ni affirmer une boucle réelle sur la base d'un warning. Clôture : inventaire par source et configuration, justification/tests pertinents.

### PR #65 — Cœur CV32E40P complet

- [x] **PR65-MERGE-01** — 812 tests locaux, 36/36 CI, fusion autorisée et effective : `55298e78f43037af439809dda4e0af2e0f01f3af`.
- [~] **PR65-LIMIT-01 · P0** — #67 confirme les deux plafonds de 2 000 lignes (1 803 déclenchements expressions, 1 arrêt constructions complexes à 38 102 visites). #68 propose 4 096 lignes par défaut, configuration bornée à 8 192 ; autres limites inchangées. Clôture : mesure avant/après, absence de troncature résiduelle pour cette configuration, non-régression et compteurs réconciliés.
- [~] **PR65-BIT-01 · P0** — #67 : 1 199 affectations bit, 467 supportées, 732 partielles, 2 842 arêtes, toutes attribuées aux instances. Inventaire par instance et motif produit. Reste : identités stables entre runs, audit des exclusions et caractérisation/correction des familles partielles. Clôture : baseline archivée, classification justifiée, pas de confusion avec le dénominateur AST.
- [~] **PR65-WARN-01 · P1** — #67 inventorie les 15 avertissements signal par motif et instance ; localisation absente lorsque non fournie. Reste : analyser chaque motif et ajouter des tests pour chaque correction ; avertissements résiduels justifiés.
- [~] **PR65-COV-01 · P0** — #67 fournit les lignes partielles des dix analyseurs et un recensement syntaxique indépendant (3 811 occurrences AST). Reste : comptabiliser les exclusions/omissions de manière justifiée, notamment décodeur et boucles. Clôture : dénominateurs explicites, raisons et non-additivité.
- [ ] **PR65-PATH-01 · P1** — 47 annotations signal toutes correctes et 7 chemins observés, sélection étroite. Ajouter cas conditionnels, chemins négatifs (absence justifiée), tests intercycles, clock gating et frontières. Clôture : corpus gelé élargi avant exécution et vérification indépendante ; pas de claim de faisabilité ou CDC.
- [ ] **PR65-SIM-01 · P1** — Première simulation du vrai cœur, avec mémoire instruction/données et programmes RISC-V de référence, reset/boot, ALU, branchements, load/store, stalls et interruptions sélectionnés. Clôture : traces architecturales comparées à oracle ISA indépendant, tests négatifs, configuration/limites enregistrées.
- [ ] **PR65-CONFIG-01 · P2** — Une seule config du CPU ; pas FPU, PULP/cluster, HW-loop, PMP ou SoC ; clock gate modèle de simulation. Clôture : variantes choisies et dépendances officielles vérifiées, rapports séparés, pas d'affirmation ASIC/FPGA à partir du modèle.
- [ ] **PR65-PERF-01 · P2** — Mesurer au moins 3 répétitions du cœur sur même machine/configuration, RSS/temps par phase, taille des résultats après déplafonnement et vitesse des requêtes. Clôture : min/médiane/max, versions et impact des corrections documentés. Lien PR55-PERF-01.

### PR #66 — Registre permanent

- [x] **PR66-DOC-01** — Registre et README intégrés, 35/35 CI, fusion `128d959790df7ee48b94e03c61cab3ef7ee0396e`. Actualisation à chaque chantier.

### PR #67 — Inventaire de référence (fusionnée)

Source : [résultats locaux consignés sur la PR](https://github.com/Antoine310/scientist_parseur/pull/67#issuecomment-7163298534), `reports/pr67/run-2aqsrksy/diagnostics.result.json` et `diagnostics.summary.md`. CI 37/37 sur `b6cca3df6ee44b158dca2f065f8692f5df9e272c`. Fusion `614be44c02c86b0d4a9f10a6883aa8bbe9c8fcdf`. Les totaux pytest locaux ne figuraient pas dans le dernier extrait transmis.

| Mesure | ALU hiérarchique | Cœur |
|---|---:|---:|
| Occurrences AST | 612 | 3 811 |
| Bit : affectations / supportées / partielles | 479 / 254 / 225 | 1 199 / 467 / 732 |
| Arêtes bit | 477 | 2 842 |
| Nœuds / arêtes signal / warnings | 149 / 328 / 3 | 1 597 / 3 566 / 15 |
| Troncatures globales | 0 | 2 |

| Motif bit partiel | ALU | Cœur |
|---|---:|---:|
| Opérateurs binaires | 50 | 175 |
| Incompatibilité de largeur | 37 | 165 |
| Conversion de largeur | 39 | 145 |
| Conditionnelles | 35 | 138 |
| Indices dynamiques/inconnus | 63 | 70 |
| Positions AST non validées | 0 | 23 |
| Littéraux non dimensionnés | 0 | 9 |
| Contexte procédural non supporté | 0 | 4 |
| Layout packed non prouvé | 1 | 2 |
| Largeur source inconnue | 0 | 1 |

Principales concentrations : CSR 274, register file 162, ff_one 96, ALU racine 93, multiplicateur 32, popcnt 31. Les 225 lignes ALU sont incluses dans les 732 du cœur, pas additionnées. Les taux 53,0 % / 38,9 % ne valent que pour les lignes bit recensées.

Autres lignes partielles cœur : expressions 213/2 000, register_flow 81/130, complex_constructs 51/2 000, functions 34/34, arrays 127/221, sequential 81/130, intercycle 88/130. Pas de lignes static_loop_expansion ; pas une preuve d'absence de boucles. Aucune ligne bit non attribuée. Signal 39 TP / 8 TN / 0 FP / 0 FN, 7/7 chemins. Pipeline 2,217 s, RSS Python/slang 183 732 / 207 484 Kio (pics séparés).

- [x] **PR67-BASE-01** — Inventaire des dix analyseurs et rapprochement bit par instance, causes réelles des deux plafonds. Rapport réussi et CI verte.
- [ ] **PR67-CENSUS-01 · P0** — Dénominateurs syntaxe et lignes bit distincts : décodeur 1 200 occurrences AST pour 28 lignes bit ; investiguer les critères d'éligibilité, modules sans ligne et boucles non recensées. Identifiants de lignes actuellement locaux à l'artefact. Clôture : rapprochement explicite des sites par catégorie et identités stables, sans soustraire arbitrairement les compteurs.
- [ ] **PR67-WARN-01 · P1** — Huit approximations de sélection au signal entier, un StructuredAssignmentPattern, une écriture de membre, un Call, un case Inside, une expression Inside, un ValueRange, une cible non structurée. Relier aux dettes #7/#8/#20/#36/#37/#58 ; tests sur chaque correction. Clôture : provenance et motif de chaque avertissement résiduel.

### PR #68 — Politique bornée de lignes (validation locale réussie)

- [~] **PR68-ROW-01 · P0** — Plafonds expressions et complex_constructs : défaut proposé 4 096, API configurable 1..8 192 ; les anciens 2 000 sont reproduits sur le même AST. Validation locale #68 : 23 tests ciblés, 856 au total, 0 skip. Expressions 2 000→3 803 (303 partielles), constructions complexes 2 000→2 738 (92 partielles), 2→0 analyseurs tronqués. Même AST, anciens enregistrements conservés, autres graphes identiques. Clôture après CI et fusion. Si un plafond de parcours devient visible, le conserver explicitement et le traiter séparément.
- [~] **PR68-AST-01 · P1** — Worker #55 utilise désormais read_ast borné avant construction de l'index. Chemin exercé avec succès lors du benchmark #68. CI/fusion restent à confirmer. Cela ne constitue pas un quota mémoire/CPU/disque ni une validation de toutes les entrées. Voir PR62-LIMIT-02.

Mesures locales #68 : [preuve sur la PR](https://github.com/Antoine310/scientist_parseur/pull/68#issuecomment-7163588621), `reports/pr68/run-rcktxfgu/row_budgets.result.json`. Pipeline complet 2,587 s ; même AST hors slang 1,681→1,952 s ; graphe 17 085 519→21 634 749 octets ; RSS workers 235 036 Kio dans les deux essais (un échantillon, pas une preuve d'égalité des besoins mémoire). ALU 479/254/225/477, cœur 1199/467/732/2842 inchangés ; 15 warnings.

- [ ] **PR68-MARGIN-01 · P1** — 49 187/50 000 visites complexes (813 de marge), expressions 3 803/4 096 ; vérifier les plafonds sur variantes et CVA6. Ne pas augmenter sans mesure ; distinguer budget de parcours et cap de publication. Clôture : rapport de marge et stratégie bornée éprouvée sur designs plus grands.

### PR #69 — Conversions bit à bit (en cours)

- [~] **PR69-WIDTH-01 · P1** — Première famille : conversions intégrales explicites, extensions signe/zéro non ambiguës et troncature MSB, uniquement sur lignes positionnelles déjà éligibles. Types/layouts et positions doivent être prouvés ; préserver toutes les anciennes arêtes supportées. Comparaison même AST avec ancien mode, fixture de 256 vecteurs. Tests et mesures en attente.
- [ ] **PR69-WIDTH-02 · P1** — Reste : conversions à signedness ambiguë (slang v12.1 ne sérialise pas ConversionKind), changements d'état 2/4, types alias, mismatch sans conversion explicitement démontrée, littéraux non dimensionnés et appels système au niveau bit. Recenser ce qui reste après #69 avant de choisir un complément. Ne pas supposer les 320 cas résolus. Liens PR61-BIT-02, PR39-WIDTH-01, PR64-CAST-01.
- [ ] **PR69-EVAL-01 · P1** — Comparaison ancienne/nouvelle sur ALU et core, mesurer par instance et raison ; conserver oracle #56, labels #65, dénominateurs et anciens résultats. Clôture : rapport réel, tests et CI, analyse des nouveaux cas supportés. Aucune preuve générale d'influence.

## 4. Feuille de route révisée — propositions de découpage, non engagements de numéros

Le document est introduit par une PR exclusivement documentaire, envisagée #66. Les travaux moteur partent **après fusion effective de #65 et de cette documentation**. Les numéros suivants sont prévisionnels, les IDs de dettes restent permanents.

**Ordre de priorité : mesurer → rendre les omissions visibles → corriger → vérifier par oracle → intégrer.** Ne pas attendre la fin de toutes les améliorations avant d'ajouter des tests scientifiques : chaque correction possède son propre oracle et sa non-régression. Ne pas viser artificiellement 100 % d'arêtes positionnelles ; viser une classification honnête de toutes les affectations recensées.

| PR proposée | Périmètre | Dettes principales | Gate de validation |
|---|---|---|---|
| #66 | Registre versionné, audit historique et roadmap | PR01-16-AUDIT-01, PR49-AUDIT-01, PR03-PLAN-01 | Aucun changement moteur ; historique et IDs conservés |
| #67 | Baseline détaillée des 24 instances, ALU, warnings, exclusions et causes de troncature | PR65-BIT-01/WARN-01/COV-01/LIMIT-01, PR61-BIT-01, PR23-COV-01 | Rapports avant correction, comptes réconciliés, causes de plafonds mesurées et non supposées |
| #68 | Budgets ciblés expressions/constructions complexes ; diagnostics d'omissions | PR19-EXPR-01, PR53-CPLX-01, PR62-LIMIT-01/02/COV-01, PR04-AST-01 | Seuils configurables bornés, tests aux limites ; comparaison temps/RSS, AST borné aussi dans worker #55 |
| #69 | Largeurs, extensions zéro/signe, troncature et casts | PR61-BIT-02, PR39-WIDTH-01, PR64-CAST-01, PR34-SEG-01 | Oracles exacts + simulation/mutants ; avant/après ALU et core |
| #70 | Opérateurs bitwise, réductions et transformations unaires | PR61-BIT-03 (logique), PR40-UNARY-01 | Représentation distincte des transformations, oracles et cas inconnus |
| #71 | Expressions conditionnelles, mux et gardes | PR61-BIT-04, PR20-PROC-01, PR08-SV-01 | Gardes explicites, branches et priorités ; pas de faisabilité inférée |
| #72 | Layouts packed, typedef/struct/union et concaténations LHS | PR61-BIT-06, PR36-TYPE-01, PR37-LVALUE-01, PR32-LVALUE-01 | Coordonnées exactes, non-confusion champs/valeurs et rejets ambigus |
| #73 | Indices dynamiques, indexed part-selects, tableaux / register file | PR61-BIT-05, PR60-ARRAY-01/02, PR57-IDX-01 | Conditions/ensembles de positions, tests aux bornes et registre x0 ; pas de fausses arêtes |
| #74 | Addition/soustraction, retenues, comparaison, shifts et multiplication (à découper) | PR61-BIT-03 (arithmétique), PR54-BUDGET-01 | Modèles justifiés de dépendances potentielles, bornes, oracle indépendant et représentations compactes |
| #75 | Fonctions et appels | PR58-FUNC-01, PR10-ALU-01 | Identités, branches, actuals, effets de bord et appels non supportés explicités |
| #76 | Boucles et constructions procédurales complexes | PR59-LOOP-01, PR38-PBIT-01, PR20-PROC-01, PR29-GEN-01, PR33-INIT-01 | Bornes, exécution locale et cibles ; aucune expansion non bornée |
| #77 | Connexions bit à bit entre modules, index, InOut et traces | PR54-BIT-01, PR06-INDEX-01, PR07-PORT-01/TRACE-01, PR22-BIT-01 | Positions intermodules, limites de parcours, directions vérifiées ; oracle hiérarchique |
| #78 | Transitions séquentielles et écritures concurrentes | PR21-NBA-01, PR24-SEQ-01, PR47-NBA-01, PR51-TIME-01 | Priorité/hold/reset, blocking vs NBA, tests et propriétés ciblées |
| #79 | Intercycles hiérarchiques, événements et clock gating | PR31-EVENT-01, PR52-HIER-01, PR65-PATH-01 | Frontières d'événements et latences sous hypothèses explicites ; aucun CDC non prouvé |
| #80 | Réévaluation scientifique ALU, six unités et core + références externes | PR56-EVAL-01/02, PR63-MULTI-01, PR09-DEC-01, PR28-RTL-01, PR41-ORACLE-01, PR45-EVID-01 | Corpus gelé élargi, labels difficiles/negatifs/inconnus, scores par canal et avertissements résiduels |
| #81 | Répétitions performance et optimisation mesurée | PR55-PERF-01/02, PR65-PERF-01, PR62-CI-01, PR05-CI-01 | Min/médiane/max, CPU/RSS, requêtes, cache et CI sans perte de validation |
| #82 | Simulation du vrai CPU avec programmes RISC-V | PR65-SIM-01, PR64-EX-01, PR11-SIM-01, PR64-LINT-01 | Oracle ISA indépendant, mémoire et handshakes, traces architecturales et tests négatifs |
| #83 | Propriétés formelles et équivalence ciblées | PR17-FORMAL-01, PR12-FORMAL-01, PR13-EQY-01, PR14-EQY-01, PR48-FORMAL-01, PR25-EVID-01, FUT-FORMAL-01 | Hypothèses, preuves, contre-exemples, mutants et liaison exacte aux sources |
| #84 | MCP complet lecture seule et provenance | PR15-MCP-01, PR18-MCP-01/02, PR25-EVID-01, FUT-MCP-01, PR02-DOC-01, PR01-BASE-01 | Tests stdio réels, fraîcheur, pagination, budget et erreurs contrôlées |
| #85 | Variantes CV32E40P et import/reproductibilité | PR65-CONFIG-01, PR63-CONFIG-01, PR27-IMPORT-01, PR50-PIN-01, PR26-ENV-01 | Configurations indépendantes, pins et manifests vérifiés |
| #86+ | CVA6 (sous-hiérarchie puis cœur), IP OpenTitan et campagne de validation | PR35-CVA6-01, PR42-CJ-01, PR43-COMP-01, PR44-ISA-01, PR46-RAS-01, FUT-CVA6-01, FUT-OT-01 | Corpus autorisé, sources épinglées, mêmes métriques, oracles indépendants, exclusions |
| Après ces jalons | Benchmark agent et démonstration GhostGate | PR16-BENCH-01, FUT-AGENT-01, FUT-DEMO-01 | Comparaison A/B/C contrôlée, résultats reproductibles et limites explicites |

**Règle transversale :** PR61-BIT-01 et PR65-BIT-01 restent ouverts jusqu'à la classification justifiée de chaque famille, pas simplement jusqu'à #74. Les PR peuvent être scindées ou réordonnées selon la baseline #67 ; les tâches déjà ouvertes ne sont pas effacées. PR01-16-AUDIT-01 reste un audit de code/tests distinct des descriptions. PR03-PLAN-01 est révisé à chaque jalon. Les chiffres 225 ALU et 61 tableaux sont historiques #62 : recalculer avant chaque correction sur un même RTL/configuration. Les optimisations de CI peuvent être avancées dès qu'un blocage apparaît, sans retirer un test.

## 5. Objectifs différés de la feuille de route initiale (numéros historiques proposés ≠ PR réelles)

| ID | Travail ouvert | Critère de réussite |
|---|---|---|
| FUT-CVA6-01 | Sous-hiérarchie CPU CVA6 puis cœur complet, autre configuration reproductible | Manifest et sources épinglés, métriques, annotations et validations ciblées |
| FUT-OT-01 | Première IP OpenTitan autonome et autorisée | Elaborer, indexer, annoter, tests positifs/négatifs ; dépendances et paramètres documentés |
| FUT-FORMAL-01 | Catalogue de propriétés matérielles de sécurité (CSR, verrouillage, non-interférence, équivalence) | SBY/Yosys/Z3/EQY, hypothèses, contre-exemples, mutants, portée exacte |
| FUT-MCP-01 | Investigation agent : source → écriture → gardes → chemins → evidence | MCP lecture seule, traces sourcées et limites, tests stdio et requêtes bornées |
| FUT-AGENT-01 | Benchmark agent contrôlé A=RTL brut, B=index, C=hybride RTLPrep | Questions/références gelées, mêmes conditions, exactitude, abstention, contexte, latence/coût, répétitions ; aucune affirmation de gain avant mesure |
| FUT-DEMO-01 | Démonstration GhostGate / HOST 2027, outil restant généraliste | Scénarios autorisés, résultats reproductibles, limites et validation scientifique ; ne pas présumer règlement/acceptation du concours |

## 6. Commandes de reprise immédiate (#65 → baseline de diagnostic)

À exécuter depuis la racine du dépôt, environnement activé. Lecture uniquement ; ne supprime aucun rapport. Ce script affiche les diagnostics détaillés disponibles dans le rapport #65, pas encore une ventilation par instance (à produire dans la prochaine PR moteur à partir du graphe).

```bash
python - <<'PY'
import json
from pathlib import Path
p = Path('reports/pr65/run-z8ycwvw9/core.result.json')
r = json.loads(p.read_text())
print('Rapport :', p, 'statut :', r['status'])
for name, a in r['analysis_limits']['analyzers'].items():
    print(name, json.dumps(a, ensure_ascii=False))
g = json.loads((p.parent/'static/rtl_dependencies.json').read_text())
print('Bit accesses :', g['bit_accesses']['counts'])
print('Bit graph :', g['bit_dependency_graph']['counts'])
print('Avertissements :', json.dumps(g['warnings'], ensure_ascii=False, indent=2))
PY
```

## 7. Modèle de mise à jour après chaque PR

```text
PR #XX — titre — état (brouillon / local validé / CI validée / fusionnée)
Head / commit de fusion : ...
Dettes traitées : IDs ...
Mesures avant / après (même source et configuration) : ...
Tests : ... ; CI : ... ; rapports : ...
Dettes clôturées + preuve : ...
Dettes partiellement corrigées + reste : ...
Nouvelles dettes (ID, priorité, motif, fichier, critère de clôture) : ...
Décisions et limitations : ...
Prochaine action : ...
```

### Sources de cette version

- Contexte de reprise du 24/11/2026 (`Texte collé(20261124-103538).txt`) et feuille de route après #42 (`Texte collé (2)(1).txt`) : objectifs et historique ancien. La numérotation proposée a évolué, les PR réelles prévalent.
- Logs locaux #55–62, notamment `reports/pr62/run-*/analysis_budgets.result.json` (copie fournie `Texte collé(20261125-093753).txt`) ; #63 `reports/pr63/run-hmavjqd5/multi_unit.result.json` ; #64 `reports/pr64/run-e23jsimh/ex_stage.result.json` ; #65 `reports/pr65/run-z8ycwvw9/core.result.json` (résumé terminal fourni).
- GitHub : descriptions des PR #1–48 et #50–65 relues (64 PR), issue #49 identifiée et fermée. Sources : https://github.com/Antoine310/scientist_parseur/pull/NUMERO (remplacer NUMERO par le numéro réel) et https://github.com/Antoine310/scientist_parseur/issues/49. Les descriptions historiques peuvent être antérieures aux corrections : elles renseignent le périmètre et les limites déclarées, non la validation actuelle. Audit des descriptions, pas audit exhaustif du code, des commentaires, des logs CI ou de chaque ancien commit. #65–67 : fusions effectives confirmées, voir en-tête et sections par PR.
- Les tâches, priorités et critères de clôture sont des propositions d'ingénierie, pas des défauts tous reproduits ni des preuves déjà réalisées. Les éléments non vérifiés sont volontairement marqués comme audit/mesure à effectuer.

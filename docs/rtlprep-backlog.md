# RTLPrep — Registre vivant des limites, optimisations et validations

**Version : 1.54 — 28 novembre 2026 (fusion #119, chantier #120)**  
**Dépôt :** [Antoine310/scientist_parseur](https://github.com/Antoine310/scientist_parseur)  
**Dernière PR fusionnée confirmée : #119** (181c05485bed0a06adc384c9c72696d5a64b7a0a). CI PR/main50/50 ; 2138 locaux, SHA non imprimé.
**PR en cours : #120**, composition décodeurs CSR, validation à effectuer. [Feuille de route](roadmap-after-pr95.md).

## 1. Mode d'emploi — à transmettre à chaque nouvelle conversation

Ce document complète la feuille de route et les rapports de validation ; il ne les remplace pas. Il conserve **les dettes par PR d'origine réelle**, même lorsqu'une autre PR les corrige plus tard. Ne jamais renuméroter les identifiants historiques. La PR documentaire est distincte de la #65 ; les numéros de développement proposés après son intégration restent indicatifs.

- `[ ]` ouvert ; `[~]` partiellement résolu ; `[?]` à mesurer ou auditer ; `[x]` clôturé avec preuve.
- **P0** : exactitude, omission dangereuse, budget ou reproductibilité bloquant l'évaluation. **P1** : amélioration prioritaire du moteur / validation. **P2** : extension, performance ou ergonomie. **P3** : objectif ultérieur.
- À chaque PR : lire ce registre avant de choisir le périmètre ; rattacher les corrections aux identifiants existants ; enregistrer les nouveaux problèmes, même mineurs ; conserver les mesures avant/après, le commit et les tests ; ne clôturer une ligne qu'avec un critère satisfait et une référence vérifiable.
- Une ligne partiellement traitée reste ouverte ; préciser son sous-périmètre corrigé. Les travaux différés ne disparaissent pas lorsqu'une PR est fusionnée.
- Conserver les anciens rapports et les labels gelés. Ajouter de nouvelles annotations distinctes avant de mesurer le moteur. Ne jamais ajuster un oracle pour masquer une régression.
- Ne pas fusionner sans accord explicite, validation locale pertinente et CI verte sur le **head exact**. Ne pas modifier `main` directement, le RTL officiel, les modifications locales de l'utilisateur ou effacer `docs/agent-reports/`.
- Ce fichier versionné (`docs/rtlprep-backlog.md`) est la référence de reprise. Le consulter dans `main` au début de chaque chantier et le mettre à jour dans chaque PR concernée (même si aucune dette n'est clôturée). Le fichier n'est pas mis à jour automatiquement entre les conversations. Maintenir les IDs historiques, les rapports et les critères de clôture ; ne pas dupliquer une dette sous un nouvel ID lorsqu'un lien suffit.

**Mesures CI obligatoires à chaque PR** : enregistrer tous les heads/tentatives, y compris intermédiaires, échecs, annulations et relances ; SHA, run ID/lien, événement, compteurs de jobs, horodatages UTC création→fin, gate Python, fenêtre spécialisée, verdict final, job le plus long et somme des durées des jobs. Distinguer temps mural, exécution cumulée et attente ; pas de minutes facturées déduites. Noter séparément la CI post-fusion, le cycle CI global de la PR et les mesures locales ; compléter les runs encore actifs au chantier suivant. Historique dans [ci-history.md](ci-history.md), sans écraser les anciennes données.

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
- [x] **PR65-LIMIT-01** — #67 identifie les deux plafonds de 2 000 lignes ; #68 valide leur résolution sur la configuration entière officielle. Même AST : 3 803 expressions et 2 738 constructions complexes, 0/10 analyseurs tronqués, anciens enregistrements et autres graphes conservés. 856 tests locaux, 38/38 CI et fusion effective. Limites sur d'autres configurations : PR68-MARGIN-01 et PR62-LIMIT-02 restent ouvertes.
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

### PR #68 — Politique bornée de lignes (fusionnée)

- [x] **PR68-ROW-01** — Plafonds expressions et complex_constructs : défaut proposé 4 096, API configurable 1..8 192 ; les anciens 2 000 sont reproduits sur le même AST. Validation locale #68 : 23 tests ciblés, 856 au total, 0 skip. Expressions 2 000→3 803 (303 partielles), constructions complexes 2 000→2 738 (92 partielles), 2→0 analyseurs tronqués. Même AST, anciens enregistrements conservés, autres graphes identiques. 38/38 CI et fusion effective `069b5ef9117b3a318943d213f6efa25371fe1c83`. Les limites sur des designs plus grands restent suivies par PR68-MARGIN-01.
- [x] **PR68-AST-01** — Worker #55 utilise désormais read_ast borné avant construction de l'index. Chemin exercé avec succès lors du benchmark #68. 38/38 CI et fusion confirmées. Cela ne constitue pas un quota mémoire/CPU/disque ni une validation de toutes les entrées. Voir PR62-LIMIT-02.

Mesures locales #68 : [preuve sur la PR](https://github.com/Antoine310/scientist_parseur/pull/68#issuecomment-7163588621), `reports/pr68/run-rcktxfgu/row_budgets.result.json`. Pipeline complet 2,587 s ; même AST hors slang 1,681→1,952 s ; graphe 17 085 519→21 634 749 octets ; RSS workers 235 036 Kio dans les deux essais (un échantillon, pas une preuve d'égalité des besoins mémoire). ALU 479/254/225/477, cœur 1199/467/732/2842 inchangés ; 15 warnings.

- [ ] **PR68-MARGIN-01 · P1** — 49 187/50 000 visites complexes (813 de marge), expressions 3 803/4 096 ; vérifier les plafonds sur variantes et CVA6. Ne pas augmenter sans mesure ; distinguer budget de parcours et cap de publication. Clôture : rapport de marge et stratégie bornée éprouvée sur designs plus grands.

### PR #69 — Conversions bit à bit (fusionnée)

- [x] **PR69-WIDTH-01** — Première famille : conversions intégrales explicites, extensions signe/zéro non ambiguës et troncature MSB, uniquement sur lignes positionnelles déjà éligibles. Types/layouts et positions doivent être prouvés ; préserver toutes les anciennes arêtes supportées. Comparaison même AST avec ancien mode, fixture de 256 vecteurs. Validation : 24 tests ciblés, 880 au total, 256 vecteurs de simulation et 768 vérifications, 39/39 CI. Cœur : 61 lignes supplémentaires, aucune arête dynamique ajoutée ; ALU inchangée. Fusion `bbc41fc1e5776e65ce081a6487f281b08d5552c6`. Les autres familles restent ouvertes.
- [ ] **PR69-WIDTH-02 · P1** — Reste : conversions à signedness ambiguë (slang v12.1 ne sérialise pas ConversionKind), changements d'état 2/4, types alias, mismatch sans conversion explicitement démontrée, littéraux non dimensionnés et appels système au niveau bit. Recenser ce qui reste après #69 avant de choisir un complément. Ne pas supposer les 320 cas résolus. Liens PR61-BIT-02, PR39-WIDTH-01, PR64-CAST-01.
- [x] **PR69-EVAL-01** — Comparaison ancienne/nouvelle sur ALU et core, mesurer par instance et raison ; conserver oracle #56, labels #65, dénominateurs et anciens résultats. Rapport réel et tests/CI réussis. La première exécution #70 confirme les 61 lignes dans cs_registers_i : truncate_msb, 61 positions constantes et 0 arête dynamique. Aucune preuve générale d'influence.

Mesures locales #69 : [preuve sur la PR](https://github.com/Antoine310/scientist_parseur/pull/69#issuecomment-7164000438), `reports/pr69/run-kwyljldh/bit_width.result.json`. ALU 479/254/225/477 inchangés ; cœur 1 199/467/732/2 842 → 1 199/528/671/2 842 ; 61 récupérations de l'ancien motif conversion_width_unproven_or_changed, zéro arête dynamique supplémentaire. #70 confirme : cs_registers_i, 61 positions constantes, mode truncate_msb. 24 instances, 1 597 nœuds, 3 566 arêtes signal, 15 warnings, 47/47 relations annotées, 7/7 chemins, 0 analyseur tronqué. Pipeline 2,578 s (un échantillon). Résidus : BinaryOp 175, mismatch 165, ConditionalOp 138, conversion largeur 55, état 29, indice dynamique 70, positions AST 23, littéraux non dimensionnés 9, contexte procédural 4, layout 2, largeur source 1. Total 671, dont 259 liés aux largeurs/conversions/littéraux.

### PR #70 — Largeurs/littéraux, deuxième partie (fusionnée)

- [x] **PR70-WIDTH-01** — Réessayer les seules lignes en échec de largeur/littéral : largeur de littéral élaborée, changements d'état sur constantes sans source dynamique, adaptation d'affectation lorsque types, positions et largeur déclarée concordent, source intégrale explicite. Conserver les anciennes lignes supportées à l'identique ; garder les conversions dynamiques 2/4 états et signes ambigus partielles. Validation dans ce périmètre : 37 tests ciblés, 917 au total, 40/40 CI, oracle CSR passé, trois positions constantes récupérées. Les autres familles restent ouvertes.
- [x] **PR70-EVAL-01** — Ventiler les récupérations #69 et #70 par instance, motif, mode, nouvelles arêtes dynamiques et positions constantes. Rapport réel : #69 61 et #70 3 lignes CSR, respectivement 61 et 3 positions constantes ; zéro nouvelle arête dynamique. Pas de preuve de valeur X/Z.
- [ ] **PR70-WIDTH-02 · P1** — Réexaminer les écarts restants, notamment sélections de tableaux non aplaties, casts avec signe ambigu, conversions dynamiques 2/4 états, champs packed. Ne pas déduire une largeur de la seule taille de destination. Lien PR69-WIDTH-02 et PR61-BIT-02. Clôture : justification par famille ou correction avec oracle.

- [x] **PR70-REG-01** — Première validation #70 : 31 tests ciblés réussis, 910/911 suite complète, simulation 256 vecteurs réussie, zéro récupération officielle ; CI 37/40. Régression PR40 value_transform (redimensionnement implicite d'une ligne RHS seule), correction exigeant type Assignment concordant et préservant inversion. Normalisation des sélecteurs procéduraux par identité lexicale en seconde tentative, oracle ciblé sur mcountinhibit_q[0,2,3] (reset des compteurs implémentés, ligne 1529). Révision f19bdcd : 37/37 et 917/917 réussis, 40/40 CI, oracle mcountinhibit_q[0,2,3] passé ; fusion effective. Garder le test historique PR40 intact.
- [ ] **PR70-ARRAY-01 · P1** — Audit des artefacts CI #70, run 45629165734, artefact 15030894309, head 6ef5d6a : 246/259 lignes historiquement classées largeur/littéral impliquent une sélection multidimensionnelle (165 mismatch, 29 état, 9 littéraux, 43 conversions). Rapprochement groupé par instance/fichier/ligne/cible, toutes les expressions candidates du groupe avec sélection multidimensionnelle ; pas d'identité AST unique. Ces motifs se recoupent avec fonctions/opérateurs. Prioriser la représentation exacte des coordonnées packed et les tableaux procéduraux (PR60-ARRAY-01/02, PR61-BIT-06, PR65-BIT-01) avant de promettre leur résolution. Garder des canaux distincts et mesurer les constantes et arêtes dynamiques sans double comptage.

Résultats locaux #70 : [preuve sur la PR](https://github.com/Antoine310/scientist_parseur/pull/70#issuecomment-7165614181), `reports/pr70/run-vp2rns1y/bit_width_literals.result.json`. ALU 479/254/225/477 inchangée ; cœur 1199/528/671/2842 → 1199/531/668/2842. Trois lignes supplémentaires de cs_registers_i, motif conversion_width_unproven_or_changed, modes truncate_msb et scoped_procedural_selectors, oracle reset [0,2,3]. 256 vecteurs et 1 024 vérifications, 512 ns, WIDTHTRUNC attendu dans fixture. 1597 nœuds, 3566 arêtes signal, 15 warnings, 47/47 annotations, 7/7 chemins, aucun analyseur tronqué, pipeline 2,635 s (un échantillon). Résidus plats : BinaryOp 175, mismatch 165, ConditionalOp 138, indices dynamiques 70, conversions largeur 52, état 29, positions AST 23, littéraux 9, contexte 4, layout 2, largeur inconnue 1 ; total 668.

### PR #71 — Coordonnées packed fixes (fusionnée)

- [x] **PR71-COORD-01** — Étendre le canal array_dependencies pour les lignes continues déjà partielles et les écritures procédurales déjà recensées, avec types élaborés et identité des déclarations, sélecteurs lexicaux fixes, copie directe ou chaîne littérale. Pas de faux indices plats ; conserver métadonnées d'événement/garde sans déduire priorité. Validé : 24 tests ciblés, 941 tests locaux, oracle register file 95/95, 41/41 CI et fusion.
- [x] **PR71-EVAL-01** — Rapporter les nouveaux liens exacts vers les IDs locaux du graphe plat, distinguer lignes partielles couvertes par coordonnées, arêtes dynamiques et positions constantes. Les anciens résultats du canal tableaux (p. ex. 29 constantes mhpmcounter_q ligne 1462 et LUT ALU) ne sont pas des gains nouveaux. Ne pas additionner 531 et tous les résultats du canal tableaux. Validé : 151 liens uniques vers des lignes plates partielles, 2 464 arêtes et 1 784 positions constantes nouvelles ; anciens résultats non liés exclus du total combiné.
- [ ] **PR71-COORD-02 · P1** — Restent hors périmètre : agrégats entiers, unpacked procédural, champs/alias signés ou non résolus, conversions dynamiques, concaténations, mux, indices runtime, boucles et écritures concurrentes. Le graphe plat conserve 668 lignes partielles comme baseline ; les gains de coordonnées sont mesurés à part. Liens PR70-ARRAY-01, PR60-ARRAY-01/02, PR54-BIT-01 et PR65-BIT-01.

Résultats #71 : [preuve sur la PR](https://github.com/Antoine310/scientist_parseur/pull/71#issuecomment-7166450660), `reports/pr71/run-kdivpxj5/packed_coordinates.result.json`. Graphe plat cœur 1199/531/668/2842 inchangé ; tableaux 221/94/127/5 → 378/245/133/2469 (captured/supported/partial/edges). 151 nouvelles lignes liées : register file 95, ALU 28, CSR 17, ID 6, EX 3, controller 2. 2464 arêtes, 1784 positions constantes ; oracle register file 1984/1056. ALU seule tableaux 94/33/61/5 → 130/61/69/21, 28 nouveaux liens, 16 arêtes, 40 constantes. Ne pas additionner ALU et cœur. Extension cœur 123 partielles (88 unsupported_selection_chain, 35 dynamic_or_unproven_index), ALU 69 (38/31). Minimum combiné 682/1199, 517 sans support plat ni nouveau lien PR71 ; ne pas présumer du recouvrement ancien. 24 instances, 1597 nœuds, 3566 arêtes signal, 15 warnings, 47/47 annotations, 7/7 chemins, aucune troncature, pipeline 2,684 s (un échantillon), simulation 256 vecteurs + reset 1028 ns, 941 tests, 41/41 CI. PR70-ARRAY-01 et PR71-COORD-02 restent ouvertes.

### PR #72 — Candidats d'influence bitwise (fusionnée)

- [x] **PR72-LOGIC-01** — Canal séparé bitwise_dependencies pour les lignes déjà recensées et plates partielles : BinaryAnd/Or/Xor/Xnor, BitwiseNot et réductions And/Or/Xor/Nand/Nor/Xnor ; feuilles à coordonnées fixes, concaténation et réplication bornées, conversions de largeur égale (changement d'état uniquement pour opérande sans source dynamique). Union des feuilles par bit ou réduction ; aucune assertion d'influence effective ou de copie. Garder gardes/événements/NBA, pas de priorité. Cas opaques et budgets explicitement partiels. Clôture : oracle indépendant, anciens graphes inchangés, tests et CI.
- [x] **PR72-EVAL-01** — Comparaison même AST avec désactivation du nouveau canal, exactes baselines #71 ; oracle ALU ligne 889, 2 candidats, simulation fixture 256 vecteurs/1792 vérifications, 48 candidats. Dédupliquer par ordinal avec les liens PR71 avant total combiné, distinguer les relations de l'influence fonctionnelle (masquage, annulation, contrôle non prouvés). Résultats réels : 24 nouveaux liens et 375 candidats, 977 tests locaux et 42/42 CI ; fusion confirmée. Résumé compact conservé.
- [ ] **PR72-SEM-02 · P1** — Reste : opérateurs logiques booléens, comparaisons, arithmétique, extensions dynamiques, alias/agrégats, indices runtime, mux, influence conditionnelle et masquage/cancellation. Examiner aussi les sélecteurs avec Power (ff_one) avant d'étendre l'évaluateur lexical, sans faire confiance aux tags constant seuls. Liens PR61-BIT-03, PR40-UNARY-01, PR57-IDX-01, PR71-COORD-02. Le dénominateur 1199 exclut toujours des affectations AST (PR67-CENSUS-01).

Résultats #72 : [preuve](https://github.com/Antoine310/scientist_parseur/pull/72#issuecomment-7167555039), head 6e3ab2f, 977 tests locaux, 42/42 CI, 256 vecteurs/1792 checks, 48 candidats fixture, oracle ALU passé. Correctif PR62 : comparer le registre des noms, pas un nombre fixé ; quatre tests ajoutés. Cœur bitwise 66/24/42/375 ; ALU 43/8/35/74. 24 nouvelles lignes uniques (8 ALU,16 mult), 375 candidats, 0 recouvrement PR71 ; minimum combiné 706/1199, reste 493 sans support lié. Résidus bitwise : 33 indices, 5 ConditionalOp, 2 Equality, 1 LogicalOr, 1 LogicalAnd. Graphes plat/tableaux inchangés, 47/47 annotations, 7/7 chemins, zéro troncature, pipeline 2,882 s (un échantillon). PR72-LOGIC-01/EVAL-01 clôturées après fusion `ed0c8e19b6d9888aea7e1d792475bf698fc50836` le 26 novembre.

### PR #73 — Mux et provenance des branches (fusionnée)

- [x] **PR73-MUX-01** — Canal mux_dependencies : ConditionalOp racine, branches imbriquées, sélecteurs intégraux et comparaisons/logiques simples, feuilles fixes et bitwise. Candidats données par branche, contrôle par décision, chemins syntaxiques ; X/Z peuvent fusionner les bras. Positions constantes par branche, aucune preuve de valeur, faisabilité ou priorité. Limites atomiques.
- [x] **PR73-EVAL-01** — Comparaison même AST, déduplication PR71/72, oracle ALU ligne 961 (64 données, 32 contrôle), fixture 5 affectations, 64 candidats, 8 constantes locales, 1024 vecteurs/5120 checks ; 43/43 CI et fusion confirmées, summary.json compact ; oracle ALU passé.
- [ ] **PR73-SEM-02 · P1** — Mux sous opérateurs, alias/enum non prouvés, indices runtime, pattern, largeur variable et gardes procédurales/priorités restent ouverts. Pas de preuve de sensibilité ni de couverture du RTL.

Résultats #73 vérifiés dans l'artefact CI 15042130934, run 45652297684, head 2e00299, `run-y0kpzw0s/summary.json` : status passed, fixture 5 affectations, 6 décisions, 11 branches, 36 candidats données/28 contrôle, 8 constantes par branche, 1024 vecteurs/5120 vérifications. Graphes précédents inchangés. Cœur mux 165/39/126/2030 (captured/supported/partial/edges) ; 1184 données, 846 contrôle, 28 constantes de branche ; 39 nouveaux liens sans recouvrement (ALU 27, div 1, mult 8, controller 1, LSU 1, CSR 1). Minimum combiné 745/1199, 454 sans support lié. ALU seule mux 66/28/38/1421, 864 données/557 contrôle, 26 constantes de branche, minimum 318/479. Ne pas additionner ALU et cœur. Résidus mux cœur : 64 conversion largeur/état, 37 index dynamique/non prouvé, 18 layout, 5 type intégral, 1 Call, 1 Equality. Oracle ALU 961 passé dans les deux contextes, zéro troncature. 43/43 CI sur le head exact et fusion 93c71b8. Utilisateur confirme validation locale après changement de PC ; décompte local final non transmis. Les erreurs de collecte de tests externes (75) et fixtures manquantes étaient des problèmes d'environnement ; #74 fixe testpaths et conserve contrôle de fixtures.

### PR #74 — Indices dynamiques et coordonnées candidates (fusionnée)

- [x] **PR74-IDX-01** — Nouveau canal dynamic_dependencies, affectations plates partielles déjà recensées : lecture/écriture directe avec un seul ElementSelect runtime, dimensions packed/unpacked explicites, sélections fixes restantes et validation de chaque type. Ensemble numérique dans les bornes et la largeur non signée prouvée ; alternatif par valeur, candidats données/contrôle et constantes locales. Aucun aplatissement, aucune preuve de faisabilité ou de comportement hors bornes/X/Z. Caps atomiques. Oracle FIFO ligne 77 : 2 mots de 32 bits, 64 données/64 contrôle. Validé : oracle FIFO passé, 1040 tests locaux, 44/44 CI, fusion confirmée.
- [x] **PR74-EVAL-01** — Comparaison même AST avec désactivation #74, anciennes sorties exactes, identités locales uniques et déduplication PR71/72/73. Fixture 5 affectations, 20 alternatives, 52 données/136 contrôle, 16 positions constantes, 1024 vecteurs/5120 checks. Summary compact ; détail conservé. Mesures réelles : un nouveau lien, 64 données/64 contrôle, zéro recouvrement et troncature.
- [ ] **PR74-IDX-02 · P1** — Restent : indices enum/alias (CSR lignes 549,583,1405), signés, multiples, part-select indexé, opérateurs/mux contenant sélections dynamiques, sélecteurs constants non prouvés (Power/ff_one), agrégats et structs/unions, gardes effectives et comportement OOB/X/Z. Prioriser types et composition après mesure ; PR70-ARRAY-01/PR71-COORD-02/PR72-SEM-02/PR73-SEM-02 restent ouvertes.
- [x] **PR74-ENV-01** — Configuration Pytest testpaths=tests pour ne pas collecter upstream_unknown/verilog-axis et ses dépendances externes sur un autre PC ; ne pas supprimer les dépôts, utiliser fixtures officielles épinglées. Suite locale et CI validées ; fusion confirmée.

Résultats #74 : [preuve](https://github.com/Antoine310/scientist_parseur/pull/74#issuecomment-7186932309), head 80de093f4f0a222d5a394fc2991b188699eb71f9 ; artefact CI 15099683751, run 45782588756. 30 ciblés/1040 suite, fixture 5 lignes/20 alternatives/52 données/136 contrôle/16 constantes, 1024 vecteurs/5120 checks, 2048 ns. Cœur dynamique 70/1/69/128 (captured/supported/partial/edges), ALU 63/0/63/0. Un nouveau lien FIFO, 64 candidats données et 64 contrôle, aucune constante nouvelle, oracle ligne 77 passé, pas de recouvrement. Minimum combiné 746/1199, 453 sans support lié ; ALU 318/479. 69 résidus cœur : 63 unproven_selector_type, 3 unproven_declared_layout, 3 unproven_packed_layout. 47/47 annotations signal, 7/7 chemins, zéro troncature sur 13, pipeline 2,729 s (un échantillon). 44/44 CI sur head exact, fusion 59d210f. PR74-IDX-02 et dettes générales ouvertes.

### PR #75 — Sélecteurs constants élaborés : preuve Power (fusionnée)

Audit de l'artefact #74 : les 63 résidus ALU unproven_selector_type sont tous dans ff_one_i, lignes 57 (1), 63 (15), 64 (15), 73 (16), 74 (16). Les expressions de destination utilisent Power et des paramètres/genvars lexicaux, pas de véritable index runtime. Les 63 destinations sont évaluables dans l'audit indépendant avec l'identité et la portée exactes ; la production des relations complètes reste à valider. Ne pas inférer les valeurs d'un tag constant seul.

- [x] **PR75-IDX-01** — Extension opt-in de evaluate pour Power : base positive, exposant non négatif <=10, type du résultat et de la base identique, valeurs <=1024 et aucun débordement intermédiaire ; preuve lexicale, validation de tout tag constant présent. Canal selector_recovery limité aux résidus PR74 unproven_selector_type, réécriture privée des sélecteurs nouvellement prouvés, preuve par chemin AST et type, aucun addr persisté. Réutilisation expand bitwise/mux et coordonnées fixes, ancienne sortie exacte. Budgets et rejet atomiques.
- [x] **PR75-EVAL-01** — Oracle indépendant ff_one LEN=32 : 63 lignes (1 constante, 31 OR, 31 mux), 62 candidats bitwise, 310 données et 155 contrôle mux, une position constante, 527 arêtes au total ; vérifier exactement les indices parent/enfants et branches sur ALU et cœur. Résultat mesuré 809/1199 et 381/479 sans doublon. Fixture 5 affectations, 28 candidats, 1 constante, 1024 vecteurs/3072 checks. Résumé compact ; mêmes AST et graphes précédents inchangés. Validation locale et CI complètes, fusion confirmée.
- [ ] **PR75-TYPE-01 · P1** — Reporter explicitement les alias/enum, structs/unions, concaténations LHS à un chantier dédié après #75 ; aucune résolution par nom seul ni layout déduit sans identité sémantique. Garder les six autres résidus PR74 ouverts, ainsi que les indices multiples/signés/runtime sous opérateurs et les gardes effectives. PR36-TYPE-01, PR37-LVALUE-01, PR32-LVALUE-01, PR74-IDX-02.

Résultats #75 : [preuve locale](https://github.com/Antoine310/scientist_parseur/pull/75#issuecomment-7187352073), head c5c3129f1843765ca48d671de69dd6a622a9d810 ; artefact CI 15101889262, run 45787214945, `run-hb2q_lsp/summary.json`. 34 ciblés (0,07 s), 1074 suite (3,41 s), fixture 5 lignes/28 candidats/1 constante, 1024 vecteurs/3072 checks, simulation 2048 ns. Cœur et ALU selector_recovery 63/63/0/527, 63 nouveaux liens uniques, 31 OR (62), 31 mux (310 données/155 contrôle), 1 position constante ; oracle ff_one LEN=32 passé, aucun recouvrement. Minimum combiné cœur 809/1199 (67,47 %), 390 sans support lié ; ALU 381/479, 98 sans support lié. Anciens graphes exacts, 47/47 annotations signal, 7/7 chemins, zéro troncature sur 14. Pipeline 2,8071338 s, graph build 1,1932325 s, RSS Python 238752 KiB, slang 205196 KiB, AST 47778002 octets, graphe 24863676 octets (un échantillon). 45/45 CI sur head exact, fusion c6e4cc0. PR75-IDX-01/EVAL-01 clôturées. PR75-TYPE-01, six autres résidus PR74 et dettes générales ouvertes.

### PR #76 — Résolution des types de package (fusionnée)

Audit de l'artefact #75 : les six autres résidus PR74 sont trois lectures de debug_fsm_cs (controller lignes 1544–1546, enum debug_state_e et paramètres HAVERESET_INDEX/RUNNING_INDEX/HALTED_INDEX) et trois sélections CSR (lignes 549,583,1405, enum csr_num_e, csr_addr_i[4:0]). TypeAlias.target contient un token adresse + nom qualifié ou un layout explicite ; EnumType.baseType donne le type de base. Les structs apparaissent sous une autre représentation textuelle et ne sont pas résolus par cette PR.

- [~] **PR76-TYPE-01 · P1** — Inventaire borné des packages directs, unicité des identités, résolution exacte des chaînes TypeAlias/EnumType vers layouts logic/bit non signés ; accord type de l'expression/déclaration indexée, identité du signal ; paramètres locaux de package vérifiés par adresse/nom/type et valeur, sans tag constant seul. Réécriture privée des copies et sélections directes, délégation PR74 pour indices numériques runtime. Nouveau canal typed_layout limité aux six résidus de layout, candidats fixes ou alternatifs, aucune preuve de faisabilité des valeurs d'enum. Aucun addr ajouté aux preuves. Anciennes sorties inchangées, budgets atomiques.
- [x] **PR76-EVAL-01** — Oracle indépendant à partir des six lignes officielles : trois bits debug (0/1/2), trois accès CSR à 32 alternatives de 32 bits, 3072 candidats données, 15360 contrôle, 3 fixes (18435 total). Résultat mesuré 815/1199 et 381/479 ; ne pas confondre arêtes conditionnelles et dépendances fonctionnelles. Fixture 3 lignes/97 candidats, 1024 vecteurs/3072 checks ; comparaison même AST, déduplication PR71–75, summary.json. Validation locale 1106/1106, 46/46 CI et fusion confirmées.
- [ ] **PR76-STRUCT-01 · P1** — Structures/unions packed, types locaux/anonymes/signés, concaténations LHS, accès membres et conversions nécessitent preuve distincte ; garder ouverts PR36-TYPE-01, PR37-LVALUE-01, PR32-LVALUE-01 et PR75-TYPE-01 (partiellement traité seulement). Ne pas déduire le layout d'un nom non qualifié ou d'un champ sans identité. Proposer le prochain chantier moteur après #77 CI : structures et concat LHS avant arithmétique.

Résultats #76 : [preuve locale](https://github.com/Antoine310/scientist_parseur/pull/76#issuecomment-7188181211), head f0a52453528faa8b1567206329e4447bae940ceb, `reports/pr76/run-x6s1nkn8/summary.json` status passed. 32/32 ciblés (0,06 s), 1106/1106 suite (3,46 s) ; fixture 3 lignes/97 candidats (1 fixe,32 données,64 contrôle), 1024 vecteurs/3072 checks, simulation 1/1 à 2048 ns. Core typed_layout 6/6/0/18435 (3 fixes debug,3 accès CSR : 3072 données,15360 contrôle), 6 liens uniques, zéro recouvrement ; oracle type passé. Minimum combiné 815/1199, 384 sans support lié ; ALU 381/479 inchangée. Anciens graphes exacts, 24 instances, 1597 signaux, 3566 arêtes, 15 warnings, 39 TP/8 TN/0 FP/FN, 7/7 chemins, 0/15 troncature. Pipeline 3,212731 s, graph build 1,370971 s, RSS Python/slang 284848/229804 Kio (pics séparés), AST 47778002 octets, graphe 33322406 octets (mesures ponctuelles). 46/46 CI PR, fusion fa5a797 le 26/11. Candidats syntaxiques, pas preuve fonctionnelle. PR76-TYPE-01 reste partielle au-delà du périmètre prouvé ; PR76-STRUCT-01 et PR75-TYPE-01 restent ouvertes.

- [x] **PR76-REG-01** — Deux correctifs avant validation : SyntaxError ligne 235 typed_layout.py (56 erreurs de collecte, corrigé be3b3a0), argument types manquant dans build_typed_layout → expand (19 échecs CI, corrigé f0a5245). Aucun changement des oracles ; nouveau head 1106/1106 et 46/46, fusion effective. Sources : [commentaire 1](https://github.com/Antoine310/scientist_parseur/pull/76#issuecomment-7188096119), [commentaire 2](https://github.com/Antoine310/scientist_parseur/pull/76#issuecomment-7188108110).

### PR #77 — Orchestration CI (fusionnée)

- [~] **PR77-ORCH-01 · P2** — Baseline mesurée sur head #76 : 46 PR + 39 push = 85 runs success, 1068 s fenêtre PR (17 min 48 s, attente incluse). Proposition : un orchestrateur, gate Python, annulation PR obsolète, 45 workflows spécialisés inchangés dans jobs, verdict final exigeant 46 succès. Voir [audit et matrice](ci-pr77.md). Résultat : 47/47 jobs (46 suites historiques + verdict) dans un seul run PR en 227 s contre 1068 s sur #76. Un seul échantillon avant/après, attente incluse. Reste : contrôle annulation/échec, noms checks requis, mesures répétées et CI post-fusion. PR62-CI-01 et PR05-CI-01 restent ouvertes (mutualisation/cache non validés). Aucun test historique retiré, aucun changement moteur.
- [ ] **PR77-CAP-01 · P2** — 45 appels réutilisables à #77, 46 proposés à #78, sur limite GitHub de 50. Prévoir regroupement par familles / recette commune, sans perte de jobs ni oracles. Clôture : capacité d'extension et mesure avant/après, pas de cache non vérifié.
- [ ] **PR77-LOCAL-01 · P3** — Agent de validation sur PC Linux différé par décision utilisateur ; réévaluer après plusieurs PR CI optimisées. Si nécessaire, opérations prédéfinies, environnement isolé, autorisation explicite, rapport par SHA via GitHub, aucun accès root/commande arbitraire/API OpenAI payante ni contournement des quotas. Aucun merge automatique.

Résultats #77 : [run 45799218988](https://github.com/Antoine310/scientist_parseur/actions/runs/45799218988), head 331a39c, 47/47 succès. 10:12:56–10:16:43 UTC, 227 s, baisse observée 78,7 % par rapport à #76 (1068 s). 1 déclenchement PR au lieu de 85 PR+push. Fusion 4f894c0 autorisée et effective. CI push main 45799854470 encore queued au contrôle de reprise ; ne pas déclarer réussite. Les installations/caches et l'annulation en conditions réelles ne sont pas validés.

### PR #78 — Agrégats : inventaire et concaténations directes (fusionnée)

- [~] **PR78-CONCAT-01 · P1** — Rapport expérimental séparé des graphes historiques : census syntaxique actif, concat LHS continue uniquement, NamedValue de type logic/bit scalaire ou vecteur non signé déclaré et identité sémantique exacte, largeur/état égaux, ordre LSB, cibles distinctes, aucun fallback par nom. Rejet atomique des conversions, sélections, agrégats, NBA et concat imbriquées. Oracle fixture indépendant réussi : 8 candidats, 256 vecteurs/1280 checks, 16 ciblés et 1125/1125 suite, 48/48 CI PR et main. Aucun gain officiel : 0 concat LHS dans ALU/cœur recensés. Reste les autres formes de concat.
- [ ] **PR78-CENSUS-01 · P1** — Inventorier MemberAccess LHS/RHS et concat LHS du vrai ALU et cœur, types observés et provenance ; dénominateur AST distinct de 1199, catégories recouvrantes. Clôture : rapports réconciliés et audit des identités/offsets avant extension struct/union. PR76-STRUCT-01, PR36-TYPE-01, PR37-LVALUE-01, PR32-LVALUE-01 et PR75-TYPE-01 restent ouvertes. Aucun layout de membre déduit du texte ou du nom ; aucune modification du graphe historique.

Résultats #78 : [preuve locale](https://github.com/Antoine310/scientist_parseur/pull/78#issuecomment-7189306539), head a6c6975, `reports/pr78/run-jrsfby5s/summary.json` passed. Fixture 6 occurrences, 5 sites, 1 supporté/4 partiels/8 candidats ; simulation 1/1 à 512 ns. ALU 612 occurrences/0 site, cœur 3811 occurrences/30 sites, 20 LHS/12 RHS (2 communs), 0 concat LHS, 30 partiels member_layout_not_proven. Graphe plat ALU 479/254/225/477, cœur 1199/531/668/2842 ; 24 instances, 1597 nœuds, 3566 arêtes, 15 warnings, 39 TP/8 TN, 7/7 chemins, aucune troncature. Pipeline 3,21334 s, graph build 1,37843 s, RSS Python/slang 284304/232136 Kio (pics séparés), AST 47778002, graphe 33322406 octets (un échantillon). 48/48 CI PR et main ; fusion 945c19d. Durées dans ci-history.md.

### PR #79 — Structures packed de package (fusionnée)

Audit artefact #78 15106804167, run 45800487135 : les 30 sites sont dans cs_registers_i, types Status_t/Dcsr_t/Pmp_t. TypeAlias.target exporte l'ordre des champs sans adresses de déclaration de champs ; les MemberAccess portent un token adresse/nom. L'identité exacte du typedef, le nom de champ unique et l'accord du type d'expression sont exigés ; cohérence des tokens observés, sans prétendre à une preuve indépendante de leur liaison aux déclarations. Layouts locaux Pmp_t et multidimensionnels, unions, conversions, sélections, opérateurs, constantes enum non signal, gardes et NBA hors périmètre.

- [~] **PR79-MEMBER-01 · P1** — Rapport distinct : candidats positionnels de copies directes continues/AlwaysComb avec membre simple de struct packed unsigned de package, layout homogène et borné, enum de package explicite via #76 ; rejet atomique des cas non prouvés. Oracle fixture 4 sites/16 candidats et simulation 256/768 ; oracle officiel attendu 7 sites/10 candidats (1055,1059,1068,1076,1128–1130). Mesures à effectuer, ne pas additionner au dénominateur historique.
- [ ] **PR79-IDENT-01 · P1** — Vérifier l'export détaillé de slang ou autre preuve indépendante d'identité de champ, puis étendre aux structures locales/multidimensionnelles, unions et composition. PR76-STRUCT-01, PR78-CENSUS-01, PR36-TYPE-01, PR37-LVALUE-01 et PR75-TYPE-01 restent ouverts.

CI #79 vérifiée : [run 45803933566](https://github.com/Antoine310/scientist_parseur/actions/runs/45803933566), head cc5c677, 49/49, 208 s, 1 tentative. Rapport local 1140/1140 et oracle 7/30, confirmé également par les 1156/1156 et l'oracle #80 sur descendant exact inchangé pour le code #79. Fusion 292fb83. Limites restantes ouvertes.

### PR #80 — Écritures de champs scalaires (fusionnée)

- [~] **PR80-WRITE-01 · P1** — Rapport expérimental distinct, écritures directes de champs logic scalaires de package, sélection constante littérale d'un bit de vecteur logic ou conversion littérale 1'b0/1'b1 exactement exportée. Identité/type de base et cohérence des tokens #79, largeur/état, bornes et tag constant concordants ; aucune arête pour les constantes. Oracle attendu : 3 arêtes (999,1002,1006), 7 positions constantes (1000,1001,1003,1004,1005,1060,1070) dans cs_registers_i. Comparaison disjointe des sept sites #79. Fixture 4 sites/2 arêtes/2 constantes, 16 vecteurs/16 checks. Mesures à effectuer.
- [ ] **PR80-RESIDUAL-01 · P1** — Enum constants, Pmp_t local multidimensionnel, concat RHS, logique et NBA restent à traiter. Aucun ajout au 815/1199. Pas de preuve de valeur globale ni de priorité. Garder PR79-IDENT-01 et toutes les dettes agrégats ouvertes.
- Séquence de fusion : valider #79 séparément, fusion autorisée #79 puis retarget #80 sur main, vérifier le diff et relancer/contrôler le head exact #80. Pas de fusion #80 dans #79 par erreur.

Résultats #79 : [preuve locale/CI](https://github.com/Antoine310/scientist_parseur/pull/79#issuecomment-7193611455) ; 1140/1140 6,90 s, fixture 4 sites/16 candidats, 256 vecteurs/768 checks, core 7/30 sites/10 arêtes. Pipeline 4,472456 s (environnement Python 3.13.0rc1), graph build 2,250070 s, RSS Python/slang 184136/219632 Kio. #80 : [preuve locale/CI](https://github.com/Antoine310/scientist_parseur/pull/80#issuecomment-7193612334), head exact 698da07, 1156/1156 5,85 s, fixture 4 sites/2 arêtes/2 constantes, 16 vecteurs/16 checks, core 10/10 sites ciblés, 3 arêtes/7 constantes, disjoints #79. Cumul 17/30 sites, 13 arêtes/7 constantes, 13 résiduels. Pipeline 4,251796 s, graph build 2,284978 s, RSS Python/slang 184072/217548 Kio. Compteurs historiques inchangés ALU 479/254/225/477, cœur 1199/531/668/2842, 24 instances, 1597 nœuds, 3566 arêtes, 15 warnings, 39 TP/8 TN/0 FP/FN, 7 chemins, 0 troncature, AST 47778002, graphe 33322406 octets. Mesures ponctuelles. #79 fusion 292fb83, #80 retarget main puis fusion 9b01304, arbres fusionnés identiques aux heads CI. Pas de nouvelle CI PR observée après retarget ; CI main à relever.

### PR #81 — Constantes enum dans champs packed (fusionnée)

- [~] **PR81-ENUM-01 · P1** — Artefact #80 15115756390 : quatre sites CSR 1007/1054 (dcsr_n.prv), 1061/1071 (mstatus_n.mpp), RHS PRIV_LVL_M. TypeAlias de PrivLvl_t pointe exactement vers EnumType homonyme qualifié ; valeur EnumValue explicite adresse+nom et initialiseur binaire converti, type et encodage vérifiés, offsets #79 ; aucun fallback, aucune arête pour constantes. Oracle attendu 4 sites/8 positions constantes, cumul 21/30 sites disjoints ; pas de conclusion temporelle, de priorité, de reachability, ni de preuve indépendante de liaison des champs. Fixture deux écritures conditionnelles, 4 constantes, 4 vecteurs.
- [ ] **PR81-RESIDUAL-01 · P1** — Pmp_t multidimensionnel local (5 sites), concat RHS, logique (2 sites), StructuredAssignmentPattern (1 site) : 9 résiduels si #81 validée. Toutes les dettes agrégats restent ouvertes. CI #81 mutualisée dans job #80 avec référence fraîche #80, aucune suppression de validation, 50 jobs attendus ; conserver mesures et vérifier le gain, sans en présumer.

Résultats #81 : [preuve locale/CI](https://github.com/Antoine310/scientist_parseur/pull/81#issuecomment-7194223038), head local exact fc82e3e confirmé ensuite, 1175/1175 6,21 s. Fixture 2/2 sites, 4 constantes, simulation 4 vecteurs/4 checks, 1/1 à 8 ns ; core 4/4 sites/8 constantes/0 arête ; cumul 21/30, 13 arêtes/15 constantes, 9 résiduels. Pipeline 4,356839 s, graph build 2,278325 s, RSS Python/slang 183880/219760 Kio, tailles AST/graphe et compteurs historiques inchangés, aucune troncature. CI 50/50, fusion b8e79f6. Post-fusion #79/#80 réussie. Ne pas confondre les constantes locales avec une propriété permanente de valeur du signal.

### PR #82 — Structures locales packed multidimensionnelles (fusionnée)

- [~] **PR82-LOCAL-01 · P1** — Artefact #81 15123545136 : Pmp_t TypeAlias direct du corps élaboré de cs_registers_i, token adresse + module.type, offsets 256/128/0 pour pmpaddr/pmpcfg_packed/pmpcfg. Pas de fallback nom, corps non matérialisé ou scope local ambigu refusé. Champs logic packed non signés, 1 ou 2 dimensions, cibles 2D, ordre LSB cartésien (dimension droite varie le plus vite), bornes explicites. Cinq sites : 910–912 zéro non dimensionné typé exact (768 positions constantes), 1125–1126 lectures directes (640 arêtes positionnelles). Oracle exact positions/coordonnées, disjoint des 21 sites précédents ; objectif cumul 26/30. Fixture mixte ascendant/descendant, 4 sites, 12 arêtes/12 constantes, 4096 vecteurs/12288 checks. Mesures à effectuer, rapport distinct. CI même job #80/#81, extraction fraîche réutilisée, 50 jobs.
- [ ] **PR82-RESIDUAL-01 · P1** — Quatre sites résiduels si #82 validée ; concat RHS, logique (2), StructuredAssignmentPattern. Unions, champs imbriqués, identité de déclaration de champ indépendante, références aux corps partagés et priorités/temporalité non prouvées. Ne pas clôturer PR79-IDENT-01, PR76-STRUCT-01, PR78-CENSUS-01 ni les dettes associées. Pas d'ajout au 815/1199. 

Première validation #82 sur 3d8a06a : 1198/1198 locaux (6,40 s), rapport `reports/pr82/run-8rp_cvn2/summary.json` failed, fixture 2/4 sites, 12 arêtes, 0 constante ; CI 48/50 en 201 s, run 45837398777. Artefact 15126866660 : deux zéros refusés, `8'd0` et `4'b0`, cœur `512'h0` et `128'h0`. Correction limitée aux graphies exactes b/d/h et largeur/type concordants, avec tests négatifs ; oracle inchangé. Pas de gain #82 déclaré avant validation complète. Historique CI conserve l'échec. Post-fusion #81 : 50/50, 205 s.

Résultats #82 corrigée : [preuve locale/CI](https://github.com/Antoine310/scientist_parseur/pull/82#issuecomment-7194926735), 1210/1210 5,63 s, fixture 4/4 sites, 12 arêtes/12 constantes, simulation 4096 vecteurs/12288 checks à 8192 ns ; ALU 0, core 5/5, 640 arêtes/768 constantes, cumul 26/30 sites, 653 arêtes candidates/783 constantes. Pipeline 3,799949 s, graph build 1,928846 s, RSS Python/slang 183928/219532 Kio, AST 47778002, graphe 33322406 octets ; compteurs historiques inchangés, 0 troncature. SHA local non visible dans extrait, résultats correspondant au correctif validé sur CI exacte 5bb98e8 ; fusion explicitement autorisée 951e006. CI finale 50/50 167 s, première 48/50 201 s, 368 s cumulés, cycle 535 s. CI main à relever.

### PR #83 — Expressions membres et concat RHS (fusionnée)

- [~] **PR83-EXPR-01 · P1** — Artefact #82 15127347670, quatre sites résiduels exacts : 1104/1105 LogicalAnd/LogicalNot imbriqués (6 références structurales, distinctes des arêtes de copie), 467 concat RHS 32 bits (7 positions directes de membres, 25 bits d'opérandes opaques réservés par largeur vérifiée, site reste partiel), 1223 StructuredAssignmentPattern non bloquant AlwaysFF (refus explicite). Pas de preuve d'influence fonctionnelle ni de valeur globale. Oracle fixture deux sites, 3 références logiques/3 positions concat, deux bits opaques, 32 vecteurs/64 checks ; oracle core 2 sites supportés/1 partiel avec positions/1 partiel sans positions, 13 candidats. Cumul attendu 28/30 sites traités sur périmètre local et 1 site partiellement enrichi ; distinguer les relations logiques des positions. Rapport expérimental séparé, aucune addition au 815/1199.
- [ ] **PR83-RESIDUAL-01 · P1** — Concat ligne 467 : modéliser opérandes conditionnels/constantes sans déduire de branches depuis tags constant seuls. Ligne 1223 : affectation structurée NBA AlwaysFF, identité des setters, évaluation RHS avant mise à jour et preuve temporelle dédiée. Ne pas déclarer 30/30 avant preuve. PR79-IDENT-01, PR76-STRUCT-01, PR78-CENSUS-01 et autres dettes agrégats restent ouvertes. Mutualisation CI dans job #80–82, aucune validation supprimée.

Résultats #83 : [preuve locale/CI](https://github.com/Antoine310/scientist_parseur/pull/83#issuecomment-7195281660), head exact 21b7675, 16/16 ciblés 0,09 s, 1226/1226 6,31 s ; fixture 1 supporté/1 partiel, 3 références logiques/3 positions, 32 vecteurs/64 checks ; core 2 supportés, 1 partiel enrichi, 1 refusé, 6 références logiques/7 positions. Cumul 28/30 sites traités, 660 candidats positionnels, 6 références logiques, 783 constantes. Pipeline 3,925766 s, graph build 1,909055 s, RSS 184212/231812 Kio ; graphes historiques inchangés, 0 troncature. CI 50/50 184 s ; fusion e4389dc. #82 main 50/50 173 s.

### PR #84 — Setters NBA et littéraux concat (fusionnée)

- [~] **PR84-PATTERN-01 · P1** — Artefact #83 15128720344, ligne 1223 : StructuredAssignmentPattern de Status_t dans AlwaysFF, setters explicites complets sans doublon, token concordant avec MemberAccess observés (pas preuve indépendante de liaison), types exacts, deux copies depuis mstatus_n (offsets 3,5) et cinq bits constants (uie,upie,mpp,mprv). Candidats échantillonnés uniquement lors de l'exécution de cette instruction NBA ; pas de graphe combinatoire ni de transition globale, guard/last-writer/clock-domain non prouvés. Fixture vérifie maintien avant front et mise à jour après front, 32 vecteurs/65 checks.
- [~] **PR84-LITERAL-01 · P1** — Ligne 467 : 22 bits littéraux exacts, encodages non signés b/d/h, largeur et type concordants, aucune arête. Sept positions #83 conservées, disjointes des 22 constantes. Trois positions 13,14,31 restent conditionnelles et non modélisées ; 29/32 positions locales attendues pour ce site, toujours partiel.
- [ ] **PR84-RESIDUAL-01 · P1** — Conditions FPU/ZFINX, FS_t, égalités et sélection conditionnelle (dont état quatre valeurs), pas de pliage depuis tags seuls. Prouver gardes/priorité/temporalité et identité indépendante des champs avant intégration. Objectif #84 : 29/30 sites avec candidats complets au niveau instruction locale, 1 partiel ; ne pas confondre avec 29 transitions prouvées. Aucun ajout au dénominateur historique. CI mutualisée, 50 jobs.

Résultats #84 : [preuve locale/CI](https://github.com/Antoine310/scientist_parseur/pull/84#issuecomment-7195611773), SHA exact 6401827, 24/24 ciblés 0,09 s, 1250/1250 7,14 s ; fixture 2 sites, 2 candidats NBA/3 constantes NBA/2 constantes concat, simulation 32 vecteurs/65 checks, 132 ns. Core 2 sites, 2 candidats NBA/5 constantes NBA/22 constantes concat. Cumul 29/30 sites au niveau instruction locale, 1 partiel, 660 positions combinatoires, 6 références logiques, 2 candidats NBA, 810 constantes. Pipeline 3,726537 s, graph build 1,865346 s, RSS Python/slang 183952/213552 Kio, AST/graphe 47778002/33322406 octets, compteurs historiques inchangés et 0 troncature. CI 50/50 209 s, fusion d26fc18. #83 main 50/50 182 s.

### PR #85 — Constantes conditionnelles selon configuration élaborée (fusionnée)

- [~] **PR85-CONFIG-01 · P1** — Artefact #84 15128767123, ligne 467 : FPU/ZFINX dans le corps CSR sont des paramètres logic signed[31:0] liés aux paramètres du parent, initialisés à 0. Vérifier adresses/noms/scopes, chaînes d'initialisation explicites, type/valeur et tags concordants ; pas de pliage depuis tags seuls. Égalités et LogicalAnd sur valeurs connues 0/1, une seule condition, branche sélectionnée constante (littéral converti exact ou enum exact FS_OFF). Résultat attendu bits 13,14,31 à 0 uniquement pour la configuration épinglée FPU=0/ZFINX=0. Oracle partition exacte 7 positions #83 +22 constantes #84 +3 constantes #85 =32 sans recouvrement. Fixture activée/désactivée : branche runtime non pliée lorsque activée, simulation 8 vecteurs/16 checks. Rapport distinct ; 30/30 sites avec candidats au niveau instruction locale dans cette configuration si validation. Ne pas assimiler à couverture globale ni preuve de valeurs en exécution.
- [ ] **PR85-INTEGRATE-01 · P1** — Auditer le contrat d'intégration et les clés de liaison des 30 occurrences, distinguer arêtes de copie, références logiques, constantes locales, NBA, contrôles de configuration ; provenance, portée, limites et tests de non-régression. PR79-IDENT-01 et toutes les dettes d'identité champ, unions, gardes runtime, X/Z, priorité/temporalité, couverture multi-config restent ouvertes. Aucun ajout au dénominateur 815/1199, ni modification des graphes historiques. CI même job, 50 attendus.

Résultats #85 : [preuve locale/CI](https://github.com/Antoine310/scientist_parseur/pull/85#issuecomment-7197654522), SHA exact 3a5077a, 20/20 ciblés 0,09 s, 1270/1270 6,79 s ; fixture 1 résolu/1 partiel, 2 constantes, 8 vecteurs/16 checks ; core 1 site, 2/2 opérandes, 3 constantes (13,14,31, FPU=0/ZFINX=0). Partition 7+22+3=32, cumul 30/30 sites au niveau instruction locale, 660 positions, 6 références logiques, 2 NBA, 813 constantes. Pipeline 4,570594 s, graph build 2,267613 s, RSS Python/slang 184052/219676 Kio, compteurs historiques et tailles inchangés, 0 troncature. CI 50/50 195 s, fusion fdba646. #84 main 50/50 241 s. Mesures ponctuelles.

### PR #86 — Enveloppe commune des preuves expérimentales (fusionnée)

- [~] **PR86-ENVELOPE-01 · P1** — Recalcul des 7 audits #79–85 sur le même AST/index, empreintes SHA256 des fichiers dans runner, conservation sans perte des payloads lignes/candidats et métadonnées. Identifiants locaux producteur:site et producteur:collection:ordinal, pas de rapprochement par ligne ni dédoublonnage inter-producteurs. Liste fermée de 12 relations, distinction stricte des 6 catégories, contrôle des références aux lignes, des constantes sans source et des coordonnées multidimensionnelles. Oracle de reconstruction exacte de chaque rapport ; core attendu 56 lignes producteur (pas 56 occurrences), 1481 enregistrements : 660 positions, 6 références logiques, 2 NBA, 805 constantes locales, 5 constantes NBA, 3 constantes de configuration. Fixture #85 réutilisée pour 4 positions/2 constantes ; validations comportementales antérieures conservées. 25 tests ciblés attendus. CI même job, référence fraîche.
- [ ] **PR86-LINK-01 · P1** — Lier les occurrences par identité structurelle de parcours AST, non par localisation seule, analyser conflits et doublons avant promotion ; les identifiants producteur ne sont pas persistants entre élaborations. Contrat de provenance/coordonnées à auditer, aucune intégration aux graphes historiques ni ajout au 815/1199. PR79-IDENT-01, PR85-INTEGRATE-01 et toutes limites scientifiques précédentes restent ouvertes.

Résultats #86 : [preuve locale/CI](https://github.com/Antoine310/scientist_parseur/pull/86#issuecomment-7198085107), SHA exact bfc663b, 25/25 ciblés 0,12 s, 1295/1295 6,64 s ; fixture 8 lignes/6 records, ALU 0/0, core 56 lignes/1481 records, reconstruction exacte 7 rapports. Pipeline historique 4,910083 s, graph build 2,462214 s, RSS Python/slang 183840/213340 Kio, compteurs inchangés, 0 troncature. Coût total audits non mesuré. CI 50/50 201 s, fusion c70d6b8 ; #85 main 50/50 199 s.

### PR #87 — Liaison des occurrences et audit des recouvrements (fusionnée)

- [~] **PR87-OCC-01 · P1** — Ajouter un ordinal de parcours `assignment_sites` complet avant filtrage aux sept producteurs, optionnel (sorties historiques par défaut inchangées). Liaison fraîche au même AST, contrôle scope/contexte/source, census PR79, unicité producteur+ordinal, aucune jointure par ligne. Fixture réelle deux affectations même ligne, deux identités et positions ; test compatibilité sans champ optionnel. Core attendu 56 lignes → 30 occurrences distinctes, 1481 records conservés. Ordinal local à extraction et version du parcours, jamais stable entre élaborations.
- [~] **PR87-OVERLAP-01 · P1** — Groupes de doublons exacts (payload sans site_id, catégorie et occurrence), audit des recouvrements et désaccords candidats au même destinataire/position ; références logiques multiples non conflictuelles seules. Aucun aplatissement entre coordonnées déclarées et packed, systèmes mixtes signalés. Oracle attendu 1481 records exacts distincts, 0 doublon/recouvrement/désaccord/mixte, partition CSR 32 et NBA 7 ; conserver originaux même si doublons. Pas de preuve de conflit fonctionnel, ni promotion graphe. 16 nouveaux tests, CI même job.
- [ ] **PR87-PROMOTE-01 · P1** — Contrat d'intégration au moteur, validation des unités de coordonnées et du lien indépendant des champs, vérifier recouvrement avec graphe plat existant, distinguer toutes catégories, pas d'addition au 815/1199 sans rapprochement justifié. PR79-IDENT-01 et limites précédentes restent ouvertes.

Résultats #87 : [preuve locale/CI](https://github.com/Antoine310/scientist_parseur/pull/87#issuecomment-7200652938), SHA exact ce4a09c, 16/16 ciblés 0,18 s, 1311/1311 8,72 s ; fixture deux assign même ligne, 2 occurrences/2 records ; ALU 0 ; core 56 lignes/30 occurrences/1481 records exacts, 0 doublon/recouvrement/désaccord/mixte et occurrence sans record. Pipeline historique 4,755401 s, graph build 2,257145 s, RSS Python/slang 183820/217688 Kio, 0 troncature, compteurs et tailles historiques inchangés. CI 50/50 220 s, fusion 2da8fba ; #86 main 50/50 203 s. Coût audits non mesuré.

### PR #88 — Canal positionnel typé optionnel (fusionnée)

- [~] **PR88-POSITION-01 · P1** — Artefact #87 15144428065 : 660 candidats positionnels (640 PMP, 20 autres), 10 paires signal toutes présentes dans graphe historique, aucun tuple numérique plat identique observé (comparaison numérique seule non sémantique). Nouveau canal optionnel `member_position_candidates` via `build_dependency_graph(..., enable_member_positions=True)`, défaut désactivé ; vérification types exacts index, champs/offsets/indices et coordonnées, provenance et ordinal ; conserver les 821 autres records hors canal. Comparaison des paires et des tuples uniquement si les deux coordonnées sont des indices déclarés, jamais assimiler offset/coordonnée à index plat. Attendu 660 positions dont 640 multidimensionnelles et 0 comparable au plat, oracle PMP intégral et fixture. Aucune modification graphes historiques ni dénominateur, publication sous budget. 16 tests ciblés, CI même job.
- [ ] **PR88-INTEGRATION-01 · P1** — API Python opt-in seulement, CLI/MCP, coûts totaux audits, validation multi-config et champ indépendant encore à étudier. Intégration distincte des constantes/logique/NBA dans prochaines étapes ; aucun lien causal, garde/priorité/temporalité ni preuve globale. PR79-IDENT-01 et autres dettes maintenues.

Résultats #88 : [preuve locale/CI](https://github.com/Antoine310/scientist_parseur/pull/88#issuecomment-7201352254), SHA exact ee48ab7, 16/16 ciblés 0,09 s, 1327/1327 6,25 s ; core 660 positions typées/13 occurrences/10 paires historiques, 640 cibles multidimensionnelles, aucune comparable au plat, 821 autres non promues. Graphe historique identique hors empreinte/métriques, aucune troncature. Pipeline historique 3,808946 s, graph build 1,827748 s, opt-in 4,650151 s, RSS historique Python/slang 183916/209508 Kio, publication opt-in 884171 valeurs profondeur22. Mesures ponctuelles non appariées. CI 50/50 244 s, fusion a8da596 ; #87 main 50/50 200 s.

### PR #89 — Constantes et références logiques optionnelles (fusionnée)

- [~] **PR89-COMB-01 · P1** — Nouveau canal `member_combinational_candidates` via `enable_member_combinational=True`, défaut off. 805 constantes locales, 3 constantes de configuration, 6 références logiques structurelles, 814 records sur 17 occurrences attendus (artefact #88 15147088281). Vérifier type et coordonnées exacts, conserver preuve conditionnelle liée à l'opérande, aucune source artificielle pour constantes, aucune assimilation logique à copie/influence. 660 positionnels distincts, 7 NBA non promus ; 667 autres records hors canal. Oracle indépendant toutes constantes (dont 768 PMP), 6 références, partition CSR 32, fixtures #82/#83/#85. Graphe historique inchangé, budget publication conservé.
- [~] **PR89-SHARE-01 · P2** — Mutualiser une collecte fraîche des 7 audits et liaison quand les deux canaux sont activés. Test appel unique et mesure temps construction deux canaux ; coût total et benchmark répété restent ouverts. 18 tests ciblés attendus, 50 jobs CI, références fraîches.
- [ ] **PR89-SEMANTIC-01 · P1** — Aucun invariant global, garde/priorité/temporalité prouvés ; liaison indépendante champ, multi-config, CLI/MCP restent ouvertes. #90 intégration NBA séparée avec hypothèses explicites ; aucun ajout au dénominateur historique. 

Résultats #89 : [preuve locale/CI](https://github.com/Antoine310/scientist_parseur/pull/89#issuecomment-7203327646), SHA exact be59162, 18/18 ciblés 0,10 s, 1345/1345 6,98 s ; 814 records (805 locales,3 config,6 logique) sur 17 occurrences, 660 positions conservées, 7 NBA non promus. Fixtures #82/#83/#85 conformes, ALU 0, graphe historique identique intra-run hors empreinte/métriques. Pipeline historique 4,544982 s, graph build 2,416650 s, deux canaux 5,890925 s, RSS historique Python/slang 185932/211364 Kio, publication 909275 valeurs profondeur22. AST/index/graphe 47967016/856321/33354606 octets, différents #88 ; chemin de sortie pr89µ et métadonnées possibles, cause non vérifiée. Mesures ponctuelles non appariées. CI 50/50 217 s, fusion e7048c2 ; #88 main 50/50 170 s.

### PR #90 — Canal NBA optionnel (fusionnée)

- [~] **PR90-NBA-01 · P1** — Nouveau canal `member_sequential_candidates` via `enable_member_sequential=True`, défaut off. Recontrôler l'occurrence AST, AlwaysFF/NBA explicite, pattern struct complet, destination exacte, types et offsets de champ, partition locale sans trou ni doublon. 2 candidats RHS échantillonnés +5 constantes NBA sur une occurrence core ; fixture #84 2+3. Aucun événement/horloge/reset, garde, dominance ou priorité inférés ; aucune latence de cycle ni next-state global. Les constantes n'ont pas de source fictive. 1474 autres records préservés dans canaux distincts ; oracle exact et unicité IDs sur 1481 records cumulés, aucun ajout au graphe historique/denominateur. 23 tests ciblés attendus, CI même job.
- [~] **PR90-SHARE-01 · P2** — Une collecte fraîche pour les combinaisons d'options ; test appel unique, ancienne API préservée. Mesure ponctuelle 3 canaux, benchmark répété/performance/RSS opt-in encore ouverts.
- [ ] **PR90-TIME-01 · P1** — Rapprochement avec événements exacts et relations séquentielles existantes, gardes et priorité à prouver séparément ; liaison indépendante des champs, CLI/MCP, couverture/configurations, coût total restent ouverts. #91 bilan consolidé avant extension des familles arithmétiques, sans clore les dettes historiques par simple intégration.

Résultats #90 : [preuve locale/CI](https://github.com/Antoine310/scientist_parseur/pull/90#issuecomment-7203962197), SHA exact fe5718c, 23/23 ciblés 0,12 s, 1368/1368 6,57 s. Core 2 NBA sampled +5 constantes, partition locale 7 positions, 1474 autres records conservés, 1481 IDs disjoints. Fixture 2+3 NBA, 5 positions et 2 constantes locales. ALU 0. Graphe historique identique intra-run hors empreinte/métriques, 0 troncature ; pipeline 4,831719 s, graph build 2,347725 s, opt-in 6,337471 s, RSS historique Python/slang 184700/231700 Kio, publication 909543 valeurs profondeur22. AST/index/graphe 47778002/851329/33322406 octets, cause variation #89 non vérifiée. Mesures ponctuelles non appariées. CI 50/50 330 s, fusion cb3cd2a ; #89 main 50/50 207 s.

### PR #91 — Bilan scientifique consolidé (fusionnée)

- [x] **PR91-RECONCILE-01 · P1** — Recalcul sur même AST/index : 3811 occurrences syntaxiques cœur/612 ALU ; 1199/479 lignes plat ; union des IDs plats validés et récupérés #71–76 (815/1199, 381/479 attendus) ; histogramme résiduel sur IDs sans support lié. 30 occurrences membres/56 lignes producteur/1481 records ; correspondance exacte catégories, payloads, provenance et occurrence entre enveloppe et canaux, aucun ajout au dénominateur plat (pas de liaison exacte entre les univers). Tests négatifs. Oracles précédents maintenus.
- [x] **PR91-BENCH-01 · P2** — Trois paires par design, processus Linux frais, ordre alterné sur fichiers AST/index identiques, min/médiane/max et différences appariées : temps mur/CPU construction, RSS high-water VmHWM de l'espace d'adressage courant incluant chargement, taille JSON compact et temps sérialisation, RSS après sérialisation ; vérification après chronométrage, empreintes des entrées et graphes par mode, mêmes sorties historiques. Pas de seuil performance arbitraire, ni comparaison RSS avec ancien worker comme mesure équivalente. 30 tests ciblés attendus après correction RSS ; même job CI, 50 jobs.
- [ ] **PR91-NEXT-01 · P1** — Priorités proposées après bilan : exposition lecture seule CLI/MCP avec provenance et pagination ; mesurer/optimiser collectes redondantes sans retirer de contrôles ; arithmétique (add/sub/carry, comparaisons, shifts), familles résiduelles puis validation multi-config. Liaison indépendante champs, unions, gardes/priorité, événements, X/Z et preuves fonctionnelles restent ouvertes ; pas de clôture automatique des dettes.

Première validation #91 sur 2f0480d : 22/22 ciblés 0,16 s, 1390/1390 6,65 s, rapport reports/pr91/run-m87vqas0/summary.json passed, CI 50/50 245 s. Union historique 815/1199 et 381/479, 1481 records exacts, déterminisme même AST. Médianes build ALU 0,433366 → 1,207348 s (delta 0,773981), core 2,282853 → 5,779960 s (delta 3,468386), JSON compact 3158761→3161269 et 20657851→21954132 octets. RSS 261420 Kio identique 12 fois, invalide pour conclure à absence de surcoût : reproduction Linux indépendante ru_maxrss hérité après exec, correction VmHWM /proc/self/status +8 tests, nouvelle validation requise. Résidus historiques 384 core (371 partial_bit_access,10 unvalidated_ast_positions,2 unproven_packed_layout,1 target_rhs_width_mismatch) et 98 ALU (96 partial_bit_access,1 unproven_packed_layout,1 target_rhs_width_mismatch).

- [x] **PR91-RSS-01 · P1** — Corriger le benchmark mémoire hérité du parent : VmHWM de l'espace d'adressage courant, lecture stricte, rapport méthode explicite, revalider paires et CI. Ne pas déduire un delta nul des anciennes mesures.
- [x] **PR91-REASONS-01 · P1** — Ventiler partial_bit_access (371 core/96 ALU) par raison détaillée du bit_accesses et ID exact, sans rapprochement approximatif ni addition de dénominateurs ; audit avant sélection des familles arithmétiques.
- [~] **PR91-FASTPATH-01 · P2** — Mesurer et réduire coût de la collecte membre sur ALU sans site ; aucun raccourci qui masque une occurrence active, conserver comparaisons d'empreintes et oracles.

Validation finale #91 : [preuve](https://github.com/Antoine310/scientist_parseur/pull/91#issuecomment-7204312688), SHA exact 00daf57, 30/30 ciblés 0,19 s, 1398/1398 7,70 s, rapports/pr91/run-dumuds1l/summary.json (reports/pr91). 1481 payloads et provenances exacts, 30 occurrences, union historique 815/1199 et 381/479. Temps build médian ALU 0,449009→1,216879 s (delta apparié 0,768667), core 2,096685→4,964367 s (delta 2,769435), CPU delta 0,765762/2,760002 s. VmHWM build médian ALU 54796→54816 Kio (delta -8), core 158992→158896 (delta +4), après sérialisation core 162692→167472 (delta +4808 Kio). JSON compact +2508/+1296281 octets. Pas de gain garanti intercampagnes, ni absence d'allocations déduite du pic. CI finale 50/50 215 s, initiale 245 s, deux heads sans échec/relance ; fusion 11cd261, #90 main 181 s. 

### PR #92 — Mutualisation locale des audits membres (fusionnée)

- [x] **PR92-SHARE-01 · P2** — Contexte privé par collecte fraîche AST/index : inspect_ast une fois, parcours complet borné 100000, ordinal conservé, préfiltrage des 7 producteurs par census membre, types package, observations globales (pas de filtrage des tokens), resolver, layouts et instances partagés. Inventaires local/paramètres et contrôles budgets conservés. Aucun cache persistant ni modification des rapports autonomes. Chemin indépendant `collect_linked(..., shared=False)` de référence, mêmes résultats attendus.
- [x] **PR92-BENCH-01 · P2** — Benchmark apparié #91 adapté : deux modes avec trois canaux, seule collecte différente ; trois paires ALU/core, une paire 4 fixtures, processus frais VmHWM, empreinte graphe complet identique, égalité exacte sept rapports/enveloppe/linkage, contrôles historiques et oracles #87/#90. 11 tests ciblés, 1409 suite attendue, 50 jobs CI. Pas de seuil arbitraire, gain à mesurer ; ne pas masquer les limites d'un AST sans membre.
- [ ] **PR92-REMAIN-01 · P2** — Si le profil reste coûteux, auditer les inventaires redondants des trois builders et mesurer séparément leur coût ; aucune suppression d'observation globale ou validation de type sans démonstration. PR91-FASTPATH-01 partielle jusqu'aux mesures. CLI/MCP #93/#94 proposés ; résidus #95, arithmétique #96+, numéros historiques conservés.

Validation #92 : [preuve](https://github.com/Antoine310/scientist_parseur/pull/92#issuecomment-7205432157), SHA exact 2ed2e0d, 11/11 ciblés 0,16 s, 1409/1409 7,74 s, reports/pr92/run-ea7ejg14/summary.json passed. Six designs, dix paires, rapports/enveloppe/linkage et graphes complets identiques. Core 30/1481 ; ALU 0 ; fixtures 2/12/6/24 records. Médianes build indépendante→partagée ALU 1,330794→0,652718 s (-50,95 %, delta apparié -0,678076), core 5,636274→2,969595 s (-47,31 %, delta -2,666679). VmHWM build ALU59348→59380 Kio, core163480→163492 ; après sérialisation core177164→175836, delta -1328 Kio. JSON identique 3161269/21954132 octets ; pas de généralisation. CI #92 50/50 265 s, fusion ea19b3e, #91 main 225 s.

### PR #93 — Exposition CLI opt-in (fusionnée)

- [x] **PR93-CLI-01 · P1** — `deps --member-positions/--member-combinational/--member-sequential`, raccourci `--member-all`. Défaut historique inchangé, propagation au moteur, provenance/fingerprint conservées, compteurs dans deps.result uniquement sur opt-in, pas de mélange des graphes ni de dénominateurs. Échec de construction sans ancien graphe trompeur.
- [x] **PR93-QUERY-01 · P1** — Consultation lecture seule `member-evidence GRAPH --category ... --signal ... --limit ... --offset ...` ; catégories distinctes, filtrage exact source ou cible, pagination max100, lecture bornée 64 Mio et gate valeurs/profondeur, absence de canal distincte de zéro publié, contrôle structure/compteurs/provenance sans prétendre revalider les preuves. 27 tests ciblés attendus ; runner vrai CLI huit combinaisons fixture, ALU/core tous canaux, égalité API même AST, pagination, oracle #90. 
- [x] **PR93-MCP-SIZE-01 · P1** — MCP existant max 32 Mio graphe ; taille cœur historique 33322406 octets proche de la limite, nouveau JSON indenté à mesurer. #94 exposition lecture seule via module query, réexaminer budget d'admission et bornes réponse sans exposer chemin arbitraire ou exécuter EDA. Les limites historiques de couverture/preuve restent ouvertes.
 
Validation #93 : [preuve](https://github.com/Antoine310/scientist_parseur/pull/93#issuecomment-7213337324), SHA exact e67a6ab, 27/27 ciblés 0,27 s, 1436/1436 4,37 s, reports/pr93/run-6jaze7c1/summary.json passed. 8 combinaisons fixture 0/5/2/7/5/10/7/12 records, ALU 0, core 1481 ; égalité CLI/API, graphe historique et pagination exacte. Core JSON indenté 35378741 octets contre 33322406 historique, +6,17 %, dépasse plafond MCP 32 Mio de 1824309 octets. Core pipeline historique 4,557208 s, build 2,122867 s, RSS Python/slang 184668/231928 Kio, aucune troncature ; pas de benchmark apparié ni nouvelle simulation. CI 50/50 216 s, fusion 4bf25f9, #92 main 256 s.

### PR #94 — Exposition MCP lecture seule (fusionnée)

- [x] **PR94-MCP-01 · P1** — Outil `rtl_member_evidence(category,signal,limit,offset)` dans SDK 2.3.0 stdio existant, réutilise query_members #93, signal exact du graphe, provenance/empreinte et statut fraîcheur du snapshot, absent distinct de zéro. 18 outils attendus, aucun fichier choisi par agent, aucune exécution EDA, aucune modification du graphe.
- [x] **PR94-BUDGET-01 · P1** — Plafond graphe 64 Mio aligné CLI, lecture bornée même si fichier grossit, gate valeurs/profondeur et validation des canaux à l'admission. Page max100, réponse structurée JSON compact ASCII max256 Kio (hors enveloppe protocole), refus explicite si dépassée, sans couper un candidat. Les autres outils MCP conservent leurs budgets historiques de pagination ; plafond global mémoire/CPU et taille des autres réponses restent à étudier.
- [x] **PR94-VALIDATION-01 · P1** — 16 tests ciblés attendus, SDK réel stdio quatre snapshots #93 (fixture défaut, fixture opt-in, ALU, cœur), pagination complète, comparaison exacte backend CLI, empreintes inchangées, erreurs paramètres, anciennes intégrations maintenues. Même job partagé, 50 jobs. Pas d'association de preuve par signal ni de nouvelle validation formelle. #95 audit des raisons détaillées résiduelles, #96 arithmétique.

Validation #94 : [preuve](https://github.com/Antoine310/scientist_parseur/pull/94#issuecomment-7213531948), SHA exact 8aabc00, 16/16 ciblés 0,16 s, 1452/1452 6,26 s, reports/pr94/run-dunrdcyd/summary.json passed. SDK 2.3.0, 4 snapshots 18 outils, 0/12/0/1481 records, 1/1/1/15 pages, réponses max1248/12321/2931/108106 octets ; graphes 31310/49078/5306791/35783104 octets. Égalité exacte backend, empreintes entrées inchangées, 16 refus protocolaires attendus. Core historique pipeline3,836321 s, build1,908772 s, RSS Python/slang186744/215632 Kio, AST/index/graphe49951663/908737/33692706 octets, variation #93 non expliquée définitivement (chemins plus longs possibles). Pas de benchmark apparié ni preuve nouvelle. CI #94 50/50 268 s, fusion 5331a85, #93 main 251 s.

- [ ] **PR94-ERROR-01 · P2** — Erreurs MCP attendues plus explicites et moins verbeuses ; conserver refus et sécurité, ne pas supprimer les exceptions inattendues.
- [ ] **PR94-GLOBAL-BUDGET-01 · P2** — Auditer les autres outils MCP et budgets globaux mémoire/CPU/transport ; le plafond 256 Kio concerne uniquement réponse structurée membre.

### PR #95 — Audit des résidus historiques (fusionnée)

- [x] **PR95-IDS-01 · P1** — Recalcul union explicite six canaux #91, 98/384 IDs restants attendus ; replay bit_accesses et bitgraph exacts sur même AST/index, capture par identité objet/ordinal existante (pas de rapprochement ligne/nom), vérification métadonnées, refus de troncature et incohérences. Détail raison primaire, raison bit_access, refus liés par canal, cas sans ID séparés. Aucun membre ajouté.
- [x] **PR95-SYNTAX-01 · P1** — Inventaire RHS borné : racine, racine après conversions, opérateurs imbriqués, types LHS/RHS, contexte, instance/module, localisation. Histogrammes raisons et racines disjoints, opérateurs et refus potentiellement chevauchants, expliciter limites ; pas de prédiction d'éligibilité ni preuve d'influence. Résultats détaillés par ID en JSON, synthèse compacte. 17 tests ciblés attendus après correctif, 1469 suite attendue, 50 jobs. Pas de modification du moteur de dépendances.
- [ ] **PR95-ARITH-01 · P1** — Prioriser #96 selon résultats réels, distinguer addition/soustraction, comparaison, décalage, conversion, index et conditions ; sélectionner oracles indépendants et mutants. Pas de déduction de couverture globale à partir des 482 résidus (deux designs, univers séparés).

Première campagne #95, SHA exact 1382878 : 13/15 ciblés 0,18 s, 1465/1467 suite 6,74 s, 2 échecs (test_union_and_same_line_distinct, test_unlinked_not_guessed). Fixture synthétique omet guards/events [] pourtant présents dans les lignes plates produites par bitgraph ; contrôle strict correct, pas de changement de l'audit. Les tests négatifs doivent vérifier le motif exact pour ne pas passer pour une mauvaise raison. Correctif fixture +2 tests guards/events, 17 ciblés/1469 suite attendus. Runner réel reports/pr95/run-4ig0yxcy/summary.json passed sur head initial, ALU 98 et core384 résidus, replay exact, aucun scan limité, graphes et entrées inchangés. Audit 0,142214/0,686537 s. Raison détaillée ALU : BinaryOp42, conversion largeur39, largeur cible/RHS9, ConditionalOp7, layout1 ; core BinaryOp151, ConditionalOp99, conversion largeur48, largeur cible/RHS40, conversion état29, positions10, contexte4, layout2, largeur source1. Racines ALU Call32, Add31, concat8, conditional7, arithmetic shift6, equality4, greater4, and2, element2, shifts logiques1+1 ; core conditional95, LogicalAnd69, Add64, IntegerLiteral61, Call32, concat17, element10, arithmetic shift6, Multiply6, BinaryAnd5, Equality5, RangeSelect5, GreaterThan4, Subtract2, Inequality1, shifts logiques1+1. Opérateurs imbriqués (comptes chevauchants) Add39/137, Equality8/150, Multiply38/44, Subtract0/7. Core CSR189, register file67, ff_one33, popcnt31, ALU30 ; ALU ff_one33, popcnt31, ALU30, div4. Pas de prédiction de récupération, racines distinctes des motifs de refus. Priorité proposée #96 addition directe bornée et retenues, à confirmer sur détail des IDs/types ; logique/conditions, appels et conversions à conserver. CI initiale 45966588446 échec gate Python, 2 jobs échec,48 ignorés ; 21 s, aucune analyse spécialisée. Les 16 exceptions MCP du log appartiennent à #94, dette PR94-ERROR-01 inchangée.

Validation finale #95 : [preuve](https://github.com/Antoine310/scientist_parseur/pull/95#issuecomment-7213882972), SHA exact 6dd33c5, 17/17 ciblés 0,09 s, 1469/1469 6,40 s, reports/pr95/run-nndndxhp/summary.json passed. ALU98/98 0,113753 s, core384/384 0,620102 s ; distributions identiques initiale, replay exact, zéro scan limité, entrées et graphes inchangés. 33 ALU et94 core array candidates non liés +10 core partial non ajoutés. Core pipeline4,107074 s, graph2,016933 s, RSS Python/slang184220/227820 Kio, AST/index/graphe47778002/851329/33322406 octets. CI finale50/50 202 s, initiale21 s, cumul223 s, fenêtre520 s ; fusion92fb24f, main50/50 217 s.

### PR #96 — Addition modulaire (fusionnée)
- [x] **PR96-ADD-01 · P1** — Racines Add résiduelles #95, replay exact et sélection bornée blocking continu/AlwaysComb, deux opérandes directs ou sélections packed littérales fixes, identité/type exact, mêmes largeur/état non signé logic/bit, 1–64 bits, sans conversion ni alias recouvrants. Préfixes LSB compacts, paires potentielles, aucun ajout historique ni promesse d'éligibilité réelle. Rapport séparé, compteurs et refus.
- [x] **PR96-FORMAL-01 · P1** — Oracle exhaustif Python 1–4, fixture slang+cocotb 264 checks, Z3 modèle abstrait 4/32 bits, 36 UNSAT non-interférence et 1076 SAT témoins, 2 SAT mutant XOR ; pas de preuve RTL, X/Z, garde ou temporelle. 19 tests ciblés attendus, 1488 suite attendue, 50 jobs avec job formel existant. Garder logs/SMT2.
- [ ] **PR96-COMPOSE-01 · P1** — Conversions, littéraux, signedness, expressions imbriquées, alias, X/Z, paramètres et indices runtime à traiter séparément après mesure ; intégration des nouveaux canaux et preuves dans CLI/MCP ultérieure. PR95-ARITH-01 reste ouverte jusqu'à bilan. 

Validation #96 : [preuve](https://github.com/Antoine310/scientist_parseur/pull/96#issuecomment-7214346028), SHA exact 07d0937, 19/19 ciblés0,12 s,1488/1488 6,89 s, reports/pr96/run-h1cdv18i/summary.json passed ; fixture2/2,1076 paires,108 coordonnées,264 checks simulation. ALU0/31 (30 nonliteral_selection,1 unsupported_selection_chain), core0/64 (62/2), audits0,150924/0,562153 s. Aucun gain RTL réel. Z3 4.15.5 reports/pr96-formal/summary.json passed,36 UNSAT,1076 SAT témoins,2 SAT XOR mutant ; modèle abstrait uniquement. Core historique pipeline3,852750 s, build1,895633 s, RSS184576/225804 Kio, AST/index/graphe47778002/851329/33322406 octets. Aucun changement historique, troncature ou benchmark apparié. CI235 s 50/50, job formel38 s, fusion519df7e, main à relever.

### PR #97 — Popcnt et sélecteurs élaborés (fusionnée)

- [x] **PR97-SELECT-01 · P1** — Artefact CI #96 15184771945 : 31 racines popcnt ALU et cœur, 32 CSR incréments et 1 adresse cœur. Inspecter groupes AST, pas identité par ligne ; replay exact avec constantes lexicales de capture, evaluate sans Power, preuve de chaque sélection, type et identité exacts, refuse runtime, tags seuls et incohérences.
- [x] **PR97-ZERO-01 · P1** — Deux concaténations zéro MSB littéral+feuille n, résultat n+1, mêmes types d'état, coordonnées non recouvrantes, préfixes bornés. Oracle coordonné indépendant arbre popcnt : 31 lignes,312 paires,202 coordonnées attendues par design, 33 racines restantes cœur. Rapport séparé, aucune promotion au graphe ni CLI/MCP. 16 tests ciblés attendus,1504 suite.
- [x] **PR97-FORMAL-01 · P1** — Modèle Z3 largeur opérandes1..5 :20 UNSAT,100 SAT témoins,5 SAT mutant perte retenue ; simulation popcnt officiel 196 checks, oracle Python exhaustif, pas de preuve RTL. Même 50 jobs.
- [x] **PR97-INCR-01 · P1** — #98 proposée : incréments constants CSR (32) et adresse (1), modéliser littéraux/conversions et concaténation sans extrapoler ; soustraction ensuite. Garder PR96-COMPOSE-01 et PR95-ARITH-01 ouvertes.

Validation #97 : [preuve](https://github.com/Antoine310/scientist_parseur/pull/97#issuecomment-7214627976), SHA c9249d3, 16/16 ciblés 0,12 s,1504/1504 6,48 s, reports/pr97/run-4n98wfuj/summary.json passed. ALU31/31 et cœur31/64,312 paires202 coordonnées par design, audit0,189339/0,515684 s ; 33 refus cœur (32 not_single_zero_extended_operand,1 unproven_single_zero_prefix). Popcnt RTL officiel196 checks, Z3 20 UNSAT/100 SAT témoins/5 SAT mutant, modèle abstrait seulement. Graphes historiques et entrées inchangés, aucune troncature, pipeline4,114789 s, graph2,024390 s, RSS184344/211216 Kio, AST/index/graphe47778002/851329/33322406 octets. CI #97 230 s, #96 main209 s, fusion43a8ff1. Pas de preuve RTL ou de couverture globale.

### PR #98 — Incréments constants (fusionnée)
- [x] **PR98-INCR-01 · P1** — Artefact CI #97 15184969853 : groupe AST CSR 32 Add 64 bits +1 (ligne1387) et prefetch adresse alignée +4 (ligne138). Exact replay et coordonnées #97 ; littéral défini, conversion unique, refus explicites. Oracle coordonné 33 core, 67025 paires,4158 coordonnées attendues ; ALU0. Union IDs disjointe #97/#98 31/64 racines attendues ; pas de promotion dans historique. 22 tests ciblés/1526 suite attendue après correctif.
- [x] **PR98-FORMAL-01 · P1** — Oracle Python exhaustif 1–4 bits, fixture réelle slang/cocotb 32 checks, Z3 modèles 4/64/32 bits,100 UNSAT non-interférence +1 alignement,2555 SAT témoins,3 SAT mutant sans retenue ; modèle abstrait uniquement. 50 jobs attendus.
- [ ] **PR98-NEXT-01 · P1** — Soustraction après validation ; extension générale littéraux, casts, concat, alias, X/Z, gardes et intégration ultérieures. 

Correctif après validation locale initiale bc1dfc3 : 20/20 ciblés 0,10 s, 1524/1524 suite 6,65 s, Z3 2659/2659 (run-ibiaq9b8), mais reports/pr98/run-wy9h2wud/summary.json failed avant simulation et RTL réel. La fixture initiale a deux incréments de vecteurs entiers sans sélection, hors census historique selon bitaccess.extract/_contains_selection ; seul le concat d'adresse est éligible syntaxiquement. Corriger les deux entrées à 5/65 bits avec sélections [3:0]/[63:0], stimuler leur bit supérieur ignoré ; garder oracle trois résidus et mêmes coordonnées, diagnostiquer les comptes et publier détails/AST/graphe même en échec. Deux tests du gate, 22 ciblés/1526 suite attendue. Aucun changement analyseur ni formel. Ne pas réduire le dénominateur de fixture. La reproduction sur vrai slang reste à valider. Main #97 50/50.

Validation finale #98 [preuve](https://github.com/Antoine310/scientist_parseur/pull/98#issuecomment-7214932274) : SHA371dc57, 22/22 ciblés 0,10 s,1526/1526 6,48 s, reports/pr98/run-d4mm9vfy/summary.json passed. Fixture3/3,2555 paires198 coordonnées, 32 checks simulation ; core33/64,67025 paires4158 coordonnées, ALU0/31 ; union exacte disjointe #97/#98 31 ALU64 core, 67337 paires4360 coordonnées core, aucun ajout historique. Audits fixture/ALU/core0,002454/0,133651/0,549817 s, aucun tronqué, graphes inchangés. Z3 4.15.5 reports/pr98-formal/run-1s28ifro/summary.json passed 2659 requêtes abstraites (101 UNSAT,2558 SAT). Core24 instances1597 nœuds3566 arêtes15 warnings39 TP8 TN0 FP/FN annotés7 chemins ; pipeline3,926017 s, graphe1,894055 s, RSS ancien worker184316/slang217548 Kio, AST/index/graphe47778002/851329/33322406 octets. CI initiale48/50 265 s, finale50/50 296 s, cumul561 s fenêtre587 s ; main à relever. PR95-ARITH-01 et PR96-COMPOSE-01 restent ouvertes globalement.

### PR #99 — Soustraction et masque (fusionnée)
- [x] **PR99-SUB-01 · P1** — Artefact #98 15186144129, 0 ALU/2 core racines Subtract, 5 core imbriquées. Exact replay partagé sans changement Add, soustraction modulo 1–64, coordonnées fixes exactes et états/largeurs égaux ; oracle LSU offset 2 bits,6 paires/6 coordonnées. 
- [x] **PR99-MASK-01 · P1** — Forme exacte (1<<k)-1 avec k 5 bits, résultat32, littéraux 1 prouvés, support seuil t=i+1 : suffixe à partir de v2(t), bit31 constant0,129 paires37 coordonnées. Oracle exhaustif indépendant ; union core66 racines arithmétiques et318 résidus, ALU31 et67, aucun ajout graphe. 
- [x] **PR99-FORMAL-01 · P1** — 22 nouveaux tests ciblés (1548 suite attendue), fixture48 checks, Z3 1287 requêtes (soustraction2/4/32 et masque5→32), modèle abstrait binaire, pas preuve RTL. 50 jobs existants.
- [ ] **PR99-NESTED-01 · P1** — Cinq lignes Subtract imbriquées et autres compositions/omissions non promues ; poursuivre comparaisons après validation, conserver phases indicatives et dettes.

Validation finale #99 : [preuve permanente](https://github.com/Antoine310/scientist_parseur/pull/99#issuecomment-7215490068), head exact 42ff60aae36a637b9fa09d758a8a4ae2a97745b8, fusion 164a16e4829045b6b822ca721df926570b349747. 22/22 ciblés 0,16 s, 1548/1548 suite 6,76 s, reports/pr99/run-jldsvi31/summary.json passed, fixture2/2, 48 checks Verilator/cocotb, 135 paires/43 coordonnées ; ALU0 racine Subtract, core2/2, 5 imbriquées non promues. Union exacte core66 IDs, 67472 paires, 4403 coordonnées ; ALU31, restants core318/ALU67. Z3 4.15.5 reports/pr99-formal/run-z5hk7p51/summary.json passed, 1287 requêtes (72 UNSAT, 1215 SAT dont 4 mutants), modèle binaire abstrait seulement. Graphes et fichiers historiques inchangés intra-run ; pas de troncature, pas de benchmark apparié. CI finale 226 s 50/50, main 245 s 50/50 (voir ci-history). PR95-ARITH-01, PR96-COMPOSE-01, PR99-NESTED-01 et dettes P0 restent ouvertes.

### PR #100 — Égalités et comparaisons (fusionnée)

- [x] **PR100-EQUALITY-01 · P1** — Artefact #99 15187058271, ALU 4 Equality +4 GreaterThan, core 5 Equality +1 Inequality +4 GreaterThan ; 12/155 lignes contenant ces opérateurs (union, non additive avec arithmétique). AST réel : quatre comparaisons d'octets à indices lexicaux, décodeur instr_i[1:0] != 2'b11, FIFO status_cnt_q == FIFO_DEPTH[ADDR_DEPTH:0]. Premier périmètre : feuilles exactes indépendantes non signées, littéral défini ou tranche basse de paramètre int unsigned lexicalement identifié, aucun X/Z ni conversion dynamique. Attentes à vérifier : ALU4/core6 nouveaux IDs, 64/68 paires, 68/74 coordonnées. Aucune promotion historique.
- [~] **PR100-ORDER-01 · P1** — Quatre GreaterThan par design : véritables AST avec $signed, concaténation et bitwise AND du bit de signe avec cmp_signed ; ne pas traiter comme comparaison unsigned ou opérandes indépendants. Étudier composition et signe ; garder comparaisons imbriquées, alias, comparaisons à quatre états et conversions hors périmètre. #101 traite exclusivement les 4 racines GreaterThan par design observées dans l'artefact #100 15190255669 (ALU IDs 186–189, core 508–511 dans cet artefact uniquement). Forme $signed({data[MSB] & ctrl,data}) des deux côtés, même bit ctrl ; MSB répété et contrôle partagé dédupliqués, alias non prouvé refusé. Attendu 17 paires/18 coordonnées par octet, 68/72 par design ; union ALU39/core76, restants59/308. Aucun gain avant validation.
- [x] **PR100-FORMAL-01 · P1** — Oracle indépendant, tests négatifs, simulation fixture, modèle binaire SMT et mutants, conservation des 50 jobs historiques ; résultats à mesurer, pas une preuve RTL.

Validation finale #100 : [preuve permanente](https://github.com/Antoine310/scientist_parseur/pull/100#issuecomment-7215937244), head bb2c5f2a95f358bafa107340325a98fb84049b58, fusion ecab557bb5a8bdbfbcc409f88175a9e70f7a7b8a. Local premier essai 39/39 0,17 s, 1587/1587 7,62 s ; simulation bloquée Verilator 5.008 et Z3 absent du PATH, rapports run-wdbg8re7 et run-457ltsiv conservés. Deuxième essai 39/39 0,11 s, 1587/1587 6,47 s ; Verilator5.055/cocotb2.0.1, slang12.1, Z3 4.15.5. reports/pr100/run-l36zocli/summary.json passed, fixture3/3, 20 paires/23 coordonnées, 2336 assertions, 2320 ns, SHA256 2fa82cfd50a7c618abe75b8c2681480d1373266a57c6cd54679e9b1ef87adb80. ALU4/8,64 paires/68 coordonnées ; core6/10,68/74 ; 4/145 lignes imbriquées non promues. Union exacte disjointe #97–100 : ALU35/core72, restent63/312. Z3 reports/pr100-formal/run-1o8i5sc9/summary.json passed, 188 requêtes (8 UNSAT,172 témoins SAT,8 mutants SAT). CI finale 50/50,255 s ; Main #100 : [45982695597](https://github.com/Antoine310/scientist_parseur/actions/runs/45982695597), 50/50, tentative1, 216 s. Aucune promotion historique, pas de couverture globale ni preuve RTL.

### PR #101 — Comparaison d'ordre à signe contrôlé (fusionnée)

- [x] **PR101-SIGNED-01 · P1** — Oracle indépendant signé/non signé, preuve QF_BV du modèle et témoins bit, mutants signe forcé et comparaison unsigned ; simulation fixture, réconciliation exacte #97–100, rapport séparé. 50 jobs historiques, pas de promotion CLI/MCP.
- [ ] **PR101-COMPOSE-01 · P1** — Autres formes signées, largeur/conversions, contrôles différents, X/Z, autres ordres, compositions et comparaisons imbriquées restent ouvertes ; ne pas extrapoler aux autres AST. PR95-ARITH-01, PR96-COMPOSE-01, PR99-NESTED-01 et P0 inchangées.

- [ ] **PR101-CAPTURE-01 · P0** — Omission de census observée sur fixture scalaire `greater = $signed({a[7]&mode[0],a[7:0]}) > ...`. AST réel et graphe CI artefact 15189859595 : assignments_seen=1, captured=0, aucune troncature. `_contains_selection` ne traverse pas Call.arguments ; cible scalaire sans sélection explicite. Correctif fixture #101 : cible packed [0:0] avec sélection explicite [0], même fonction binaire et même oracle ; ne pas modifier le census historique pour cette PR. Clôture : inventaire indépendant des omissions Call.arguments et autres champs, analyse conservatrice bornée, IDs/dénominateurs et réconciliation nouvelle version, tests positifs/négatifs, effets sur graphes historiques et budgets documentés. PR23-COV-01, PR67-CENSUS-01, PR53-CPLX-01 liés.

Premier head #101 ef11507e8058379f0035188b9da73a22ad2399d1 : local22/22 0,10 s,1609/1609 7,27 s, fixture échec 0 résidu (reports/pr101/run-wzo4knhc/summary.json), simulation/formel locaux non exécutés par set -e. CI 47/50, 3 échecs : fixture, bitwise-pr72 téléchargement slang HTTP403 (curl22), gate final ; étape Z3 #101 réussie. Artefact 15189859595 conservé. Correction sans assouplir oracle ni changer moteur historique.

Validation finale #101 : [commentaire permanent](https://github.com/Antoine310/scientist_parseur/pull/101#issuecomment-7216325288), head 1c5d2688776746607859c9d028767e4417634951, fusion a84d885b57084f4cbd9beb80c8faf86a28f4ed86. Local22/22 0,09 s,1609/1609 7,12 s ; reports/pr101/run-bkh5cpbb/summary.json passed, fixture1/1,17 paires/18 coordonnées,131072 assertions/131072 ns/2,80 s, SHA256 3ce2861793e9cfa9c64971812c90bc21706a0ec627967cf321124bb165083e09 ; ALU/core4/4 chacun68 paires/72 coordonnées, aucune troncature, union39/76 reste59/308. Z3 reports/pr101-formal/run-d3fpetsx/summary.json passed,112 requêtes (4 UNSAT,96 témoins SAT,12 mutants SAT). CI finale50/50,253 s ; premier head47/50 conservé ; pas de promotion historique, ni preuve RTL. PR100-ORDER-01 reste ouvert globalement.

### PR #102 — Audit P0 du census (fusionnée)

- [x] **PR102-AUDIT-01 · P0** — Traçage opt-in des décisions historiques, replay exact, rapprochement par identité objet et JSON pointer local à l'artefact, partition par occurrence et instance ; fixture scalaire manquante, sélection explicite et absence de sélection. Attentes 3/1 fixture, 612/479 ALU,3811/1199 core (AST/lignes historiques), classifications à mesurer. Aucun changement du filtre historique ou promotion. PR101-CAPTURE-01, PR23-COV-01, PR67-CENSUS-01, PR53-CPLX-01 restent ouverts.
- [~] **PR102-VERSION-01 · P0** — Après audit, corriger le filtre de sélection avec nouveau dénominateur versionné, réconciliation des IDs, impact sur budgets et corpus, refus explicites ; aucun gain avant validation. Ne pas modifier rétrospectivement les dénominateurs #95.

Validation #102 : [commentaire permanent](https://github.com/Antoine310/scientist_parseur/pull/102#issuecomment-7218313125), head 35290a8632a6d47547ba0e9ea11e8926be78a433, fusion b75c9ecce8b594f909c7cf5121219e5ce1cf7afc. Local21/21 0,12 s et1630/1630 6,96 s ; reports/pr102/run-u9jikssa/summary.json passed ; fixture3/1/1 omission/1 sans sélection, ALU612/479/133 sans sélection/0 omission, core3811/1199/2594 sans sélection/13 omissions/5 cibles non supportées/0 non visitées. 7 omissions avec Call.arguments, 5 conditions ternaires,1 pattern structuré (artefact15190879320). Audits0,00156/0,201/0,758 s, visites160/21217/73214, sélections17/1248/2490, replay exact et PR67 réconcilié, aucune troncature. CI50/50,321 s ; main #101 50/50,269 s. Pas de promotion ni nouvelle simulation/formel. PR101-CAPTURE-01 reste ouvert.

### PR #103 — Correction versionnée opt-in (fusionnée)

- [x] **PR103-GATE-01 · P0** — Corriger les omissions de sélection après résultat négatif v1 par parcours borné des conteneurs hors métadonnées, refus explicite au budget. Mode opt-in, rapport v2 distinct, projection exacte IDs/lignes/arêtes v1. Attentes fixture1→2, ALU479→479, core1199→1212, 13 nouvelles lignes strictement partielles, zéro arête ajoutée ; aucun gain avant validation. PR101-CAPTURE-01 et PR102-VERSION-01 restent ouverts globalement.
- [x] **PR103-PUBLIC-01 · P0** — Intégration versionnée au pipeline public, corpus indépendants et budgets ; définir stratégie de migration des consommateurs CLI/MCP, maintenir lecture historique et IDs #95. Les cinq cibles non supportées CSR, PR23-COV-01, PR67-CENSUS-01, PR53-CPLX-01 restent ouvertes. Sémantique des nouveaux sites à traiter séparément.

Validation #103 : [commentaire permanent](https://github.com/Antoine310/scientist_parseur/pull/103#issuecomment-7218489812), head 25efa5372b642de2e285c45628cdd12468168efc, fusion e34bdc2d9f25e1549108f494cc919e52a61aab11. Local25/25 0,10 s,1655/1655 6,92 s ; reports/pr103/run-xssmexzs/summary.json passed, fixture3/1→2, ALU612/479→479, core3811/1199→1212, 13 ajoutées strictement partielles (7 appels,5 conditions,1 pattern),531 supportées inchangées,668→681 partielles,2842 arêtes inchangées,5 cibles non supportées. Projection et replay exacts, aucune troncature historique, audits0,00287/0,354/1,464 s ; unions historiques39/76 et reste59/308 inchangés. CI50/50,256 s, main #102 50/50,246 s. Artefact15197128504. Pas de promotion sémantique.

### PR #104 — Publication CLI/MCP du census (fusionnée)

- [x] **PR104-PUBLIC-01 · P0** — Export séparé depuis artefacts deps, version explicite V1/V2, pagination bornée, provenance SHA256, validation structure/partition/IDs, refus écrasement et artefacts incohérents. MCP outil conditionnel19 vs18, lecture seule et parité CLI/protocole. Fixture et CV32E40P, corpus indépendants épinglés verilog-axis (axis_register,priority_encoder) et wbuart32 (rxuart) ; comptes externes à mesurer. Aucune modification graphe historique ni sémantique. PR103-PUBLIC-01 et PR102-VERSION-01 restent ouvertes globalement avant validation.
- [ ] **PR104-MIGRATE-01 · P1** — Étudier une migration explicite du défaut, consommateurs CLI/MCP, budgets globaux et corpus plus larges sans réécrire les dénominateurs historiques ; cinq cibles CSR et PR23-COV-01/PR67-CENSUS-01/PR53-CPLX-01 restent ouvertes.

Validation #104 : [commentaire permanent](https://github.com/Antoine310/scientist_parseur/pull/104#issuecomment-7218707415), head e622dbc3faa91f81b43c8396b631c8f2e43449e2, fusion cfce52cb503cb121b4af42f6fc64857c8cb23bfd. Local29/29 0,21 s et1684/1684 7,34 s ; reports/pr104/run-25vlkfqz/summary.json passed, 4 dépôts/15 fichiers épinglés, 6 cas,43 pages MCP (2/10/25/2/2/2),24 refus attendus, SHA local non affiché dans extrait. Fixture3/1→2, ALU612/479→479, core3811/1199→1212,531 supportées,13 ajoutées partielles, zéro arête. Externes axis_register44/4→4/0 supportée, priority_encoder9/8→8/0, rxuart87/16→16/1,54 sans sélection,15 non visitées,2 cibles non supportées. Parité CLI/MCP, entrées inchangées ; 19 outils avec census,18 sinon. CI50/50,258 s, main #103 50/50,296 s ; artefact15199185312. PR101-CAPTURE-01/PR102-VERSION-01 satisfaites pour l'admission/publication opt-in des 13 sites mesurés, migration défaut/corpus plus larges et autres omissions ouvertes ; ne pas modifier l'historique. 

- [x] **PR104-WALK-01 · P0** — Auditer les 15 non visitées rxuart, toutes Initial d'après artefact #104, 1 sélection de plage ; établir les frontières effectives par traçage, distinguer des 2 cibles concaténées refusées. Aucune promotion.
- [ ] **PR104-MCP-ERROR-01 · P2** — Erreurs attendues MCP présentées en UnexpectedToolError ; améliorer messages structurés et lisibles sans masquer les erreurs inattendues, conserver is_error et les contraintes. 24 refus attendus #104, runner passed.

### PR #105 — Audit des exclusions du walker (fusionnée)

- [x] **PR105-TRACE-01 · P0** — Traçage opt-in des décisions effectives, rapprochement par identité/instance/ancêtre JSON pointer, replay historique exact. Fixture Initial et RepeatLoop, 6 designs épinglés, oracle PR67, refus explicites, non expliqué reste explicite. Attendu rxuart15 exclusions Initial dont1 sélection,2 concaténations refusées ; aucune modification de graphe.
- [ ] **PR105-INITIAL-01 · P1** — Étudier sémantique des initialisations et périmètre synthétisable (simulation/formel, état au démarrage, X/Z, priorité et temporalité), ne pas assimiler Initial à Always ni à une constante. **PR105-CONCAT-TARGET-01 · P0** — Auditer et caractériser les cibles concaténées (rxuart2), widths/ordre/alias/positions et refus, corpus indépendants. Les cinq cibles CSR et autres P0 restent ouvertes.

Validation #105 : [commentaire permanent](https://github.com/Antoine310/scientist_parseur/pull/105#issuecomment-7218894883), head 7819aa8bce55f5e585e1b987fe7a2a3af971b643, fusion 4ec7d64140b84f5eac0f370f94ef5a05b3269f4e. Local19/19 0,12 s,1703/1703 7,27 s ; reports/pr105/run-ndqfq508/summary.json passed, fixture5 AST/1 capture/3 non visitées (2 Initial,1 RepeatLoop),2 frontières et2 sélections ; ALU612/479,core3811/1199/13 omissions filtre V1/5 cibles refusées, axis44/4,encoder9/8,rxuart87/16/72 tentatives/15 Initial/15 frontières (1 sélection)/2 cibles concaténées/54 sans sélection. Zéro inexpliquée sur six cas, replay exact, aucune promotion ni troncature. Audits0,00223/0,270/1,203/0,00799/0,00616/0,0161 s. CI50/50,330 s, main #104 50/50,241 s ; artefact15198817914. PR104-WALK-01/PR105-TRACE-01 satisfaites dans périmètre testé ; sémantique Initial reste ouverte.

### PR #106 — Cibles concaténées NBA (fusionnée)

- [x] **PR106-CONCAT-SCALAR-01 · P0** — PR105-CONCAT-TARGET-01 : deux cibles rxuart (lignes179/181), concat scalaires reg/logic distincts, largeur/ordre/identité exacte, copie RHS ou zéro de même largeur. Canal séparé, 2 sites/6 records chacun fixture et rxuart attendus ; 5 CSR hors famille, historique inchangé. Simulation fixture32 transitions +128 préparations, Z3 modèle8 requêtes attendues. Ni temporalité globale ni preuve RTL, pas de promotion.
- [ ] **PR106-CONCAT-GENERAL-01 · P0** — Cibles vectorielles, sélections, concat imbriquées et alias, autres expressions et contextes, corpus supplémentaires ; PR105-CONCAT-TARGET-01 reste ouverte globalement. Auditer les cinq cibles CSR séparément, vérifier chevauchement avec canaux membres existants ; PR105-INITIAL-01, PR104-MCP-ERROR-01 et autres dettes conservées.

Validation #106 : [commentaire permanent](https://github.com/Antoine310/scientist_parseur/pull/106#issuecomment-7219057869), head 54ff17d1827b415dd275030c3b155e7b47816516, fusion 04f2f516f0d17e24767dc8cde38534ff4f6413f1. Local28/28 0,09 s,1731/1731 7,04 s (SHA local non visible dans extrait), reports/pr106/run-ag3mffvb/summary.json passed, fixture/rxuart2 sites/6 records chacun (3 sampled,3 zéro),5 autres CSR, 6 designs, replay exact. Cocotb1/1,320 ns,160 tuples (32 transitions,128 préparations), SHA256 fixture 7e9e6bb96c3a1b55ea3fa325ef70842b635052b39333d20dda3ffc3b61928357. reports/pr106-formal/run-wofn8rph/summary.json passed,8 Z3 (2 UNSAT équivalence modèle,3 SAT sensibilité,3 SAT mutants), aucune preuve RTL/temporelle. CI50/50,337 s, main #105 50/50,246 s, artefacts15201005092/15198493897. Pas de promotion ou nouvelle arête historique ; autres concat et dettes conservées.

### PR #107 — Audit cibles CSR (fusionnée)

- [x] **PR107-CSR-AUDIT-01 · P0** — Réconcilier cinq cibles refusées core avec positions membres existantes et résolution exacte des scopes generate. Trois champs DCSR déjà présents PR80/88, deux cibles gen_trigger_regs. Joindre uniquement identité AST+instance→ordinal, replay historique, aucune promotion/double comptage. Fixture 2 champs+2 cibles generate, six designs, refus explicites, pas de nouvelle preuve sémantique. 
- [~] **PR107-SCOPE-01 · P0** — Étudier admission versionnée des cibles generate et positions NBA avec oracle indépendant, préserver identités et dénominateurs ; aucune assimilation aux signaux directs. PR106-CONCAT-GENERAL-01 et PR105-INITIAL-01 restent ouvertes ; réordonner selon mesures. 

Validation locale #107 corrigée : head 7fc056994cd2f97506553b5a9d75656e8e479049, 20/20 en0,19 s et1751/1751 en7,09 s (SHA non réaffiché), reports/pr107/run-bbxgrxxz/summary.json passed, 6 designs. Fixture7 AST/4 refus/2 positions déjà existantes ; ALU612/0/0,core3811/5/3,axis44/0/0,encoder9/0/0,rxuart87/2/0 (concat #106). 3 champs PR80/88,2 scopes generate, zéro nouvel enregistrement/arête, replay et PR67 exacts. [Rapport](https://github.com/Antoine310/scientist_parseur/pull/107#issuecomment-7219231710). Initiale head991264c : 1750/1750 7,17 s, runner top erroné avant audit, run-ax3c5oxw, CI annulée40 success/9 cancelled/1 failure. Correctif top dérivé + test + census exact. Main #106 CI50/50,362 s. CI corrigée 50/50,363 s, head exact, artefact15200552325, [verdict permanent](https://github.com/Antoine310/scientist_parseur/pull/107#issuecomment-7219299483). Fusion 3fe7421eee587fd3669bfa7b603832fc807c7aa0.

### PR #108 — Cibles NBA generate (fusionnée)

- [x] **PR108-GENERATE-NBA-01 · P0** — PR107-SCOPE-01 : deux destinations CSR exactes, sélection fixe scalaire et vecteur 32 bits, candidats locaux séparés (33 records attendus), refus explicites. Fixture deux scopes homonymes, quatre sites/10 records, 768 tuples simulation,43 Z3 modèle. Pas de promotion historique, aucune preuve RTL/temporelle.
- [ ] **PR108-SCOPE-GENERAL-01 · P0** — Autres scopes, sources/targets composés, indices dynamiques, conversions, intégration/versionnement public et corpus supplémentaires ; PR107-SCOPE-01 globale reste ouverte. PR106-CONCAT-GENERAL-01, PR105-INITIAL-01 et autres dettes préservées.

Validation #108 : [local](https://github.com/Antoine310/scientist_parseur/pull/108#issuecomment-7219482048), [CI](https://github.com/Antoine310/scientist_parseur/pull/108#issuecomment-7219510930), head a272b4cd1f20fa90ca76802081e2db17456c8ea8, fusion e2a65ba1d1a8b15e26619d75663637d1669b4633. Local34/34 0,20 s,1785/1785 6,89 s, reports/pr108/run-6qcqfont/summary.json passed, 6 designs, fixture4/4 sites/10 records,core2/2/33,3 PR80/88 non recomptées ; replay exact. Cocotb1/1,1536 ns,768 tuples, SHA256 fixture0855e77d00932bac6b28d3157bf953a50c2eb9251ee098def43d43a83bb3473d. reports/pr108-formal/run-zhr6g8pr/summary.json passed,43 Z3 (3 UNSAT modèles,37 SAT sensibilités,3 SAT mutants). Initiale fcb93ef :1781/1781,6,97 s, fixture3/4,6/10, failed run-gyukruvf ; correctif bornes RangeSelect, cause initiale précise inférée, oracle inchangé. CI initiale annulée189 s (37 succès/12 annulés/1 échec), intermédiaire annulée35 s (1 annulé/48 skipped/1 échec), finale50/50,353 s ; main #107 50/50,265 s. Artefacts15201912795/15201816919. PR107-SCOPE-01 et PR108-SCOPE-GENERAL-01 restent ouvertes globalement.

### PR #109 — Concaténations vectorielles NBA (fusionnée)

- [x] **PR109-VECTOR-CONCAT-01 · P0** — Concat plate de scalaires/vecteurs/sélections fixes, largeur et type exacts, ordre LSB, chevauchement destination (signal,bit) refusé, identité exacte, PR106 d'abord pour éviter recompte. Fixture2 sites/9 records,768 assertions simulation,20 Z3 modèle attendus. Six designs, aucun nouveau site réel attendu ; rxuart2/6 déjà PR106, core5 hors famille. Pas de promotion.
- [ ] **PR109-CONCAT-CORPUS-01 · P0** — Corpus indépendant comportant des concat vectorielles pertinentes, nested/alias/dynamique/conversions et sémantique quatre états restent ouverts ; PR106-CONCAT-GENERAL-01 globale non close. Initial PR105-INITIAL-01 ensuite ; préserver toutes dettes et bilan cœur indicatif.

Validation locale #109 : head attendu fbb047a6be1a1cb2f836a00c29f61e0fc279fd8d (SHA non réaffiché), 30/30 0,23 s,1815/1815 7,14 s, reports/pr109/run-154r96mt/summary.json passed, six designs, fixture2 sites/9 records, rxuart2/6 PR106 existants, core5 hors famille, zéro promotion historique. Simulation768 assertions,512 ns, source SHA256 5bf7cc52da28963a0d374d50ab33077dd9c9a20a309e0a3ffe9616c73f90d896 ; reports/pr109-formal/run-_3vxccxr/summary.json passed,20 Z3 (9 UNSAT,11 SAT). CI50/50,394 s, artefacts15202329074/15200784680, [verdict permanent](https://github.com/Antoine310/scientist_parseur/pull/109#issuecomment-7219716884). Fusion d6db176da58a722881a6f669a271779078e6debe. Corpus vectoriel réel P0 ouvert.

### PR #110 — Initialisations directes à zéro (fusionnée)

- [x] **PR110-INITIAL-ZERO-01 · P1** — Audit PR105 des 15 Initial rxuart ; 13 affectations directes à zéro /47 bits attendus, deux références paramètres partielles. Aucun invariant permanent, aucune preuve état global ou synthèse. Fixture5 sites/3 supportés/13 bits,771 assertions simulation,12 Z3 modèles. Six designs, replay historique exact.
- [ ] **PR110-INITIAL-GENERAL-01 · P1** — Paramètres, valeurs non nulles/X/Z, initialisations de déclaration, blocs/délais/concurrence/ordonnancement, synthèse et état global ; PR105-INITIAL-01 globale reste ouverte. PR109-CONCAT-CORPUS-01 P0 et autres dettes préservées.

Validation #110 : [local](https://github.com/Antoine310/scientist_parseur/pull/110#issuecomment-7219808351), [CI et fusion opérateur](https://github.com/Antoine310/scientist_parseur/pull/110#issuecomment-7219932050), head c8bd55cba22c4a704d213705e3f5aa520c01416c, fusion 89f677c3e095d02e54b59fac575b0199fbceaef9. 30/30 0,18 s,1845/1845 7,16 s (SHA non réaffiché), reports/pr110/run-yhfof0an/summary.json passed,6 designs,fixture3/5/13,rxuart13/15/47,2 paramètres partiels. 771 assertions,513 ns, fixture SHA256 3774abe7ac96417113a7aa71e64607e965ea1f710ecd26ffd1c06caf017b7a94 ; reports/pr110-formal/run-msjo7dy2/summary.json passed,12 Z3 modèle (4 UNSAT,8 SAT). Aucune constante permanente ou arête historique nouvelle. CI50/50,355 s, artefacts15204070536/15201999973 ; main #109 50/50,275 s. Dettes générales Initial conservées.

### PR #111 — Arbres logiques et réductions (fusionnée)

- [x] **PR111-LOGICAL-01 · P0** — 69 racines LogicalAnd résiduelles core (artefact #105), 4 read-once candidates attendues IDs182/183/882/883,11 paires/15 coordonnées ; 65 partielles. Fixture6 sites/23 paires,1536 assertions,60 Z3 modèles. ALU/core et fixture. Exact lexical endpoint, aucun double comptage PR72 ni promotion.
- [ ] **PR111-LOGICAL-COMPOSE-01 · P0** — 64 racines comparaisons/adresses et une réduction de masque composé, autres opérateurs imbriqués, alias, X/Z, constantes et conversions, corpus supplémentaires, intégration versionnée restent ouverts. Décalage indicatif : shifts #112, multiplication #113 ; bilan cœur #123 ou ultérieur. Conserver toutes dettes.

Validation #111 : [local](https://github.com/Antoine310/scientist_parseur/pull/111#issuecomment-7220047693), [CI](https://github.com/Antoine310/scientist_parseur/pull/111#issuecomment-7220131694), head4c882518a5d22c349f302f1ab927af66041a8e1a, fusion 3645a8c4ac74ceffd028bff80f7af104e077f5cc. Local30/30 0,33 s,1875/1875 8,09 s (SHA non réaffiché), reports/pr111/run-kjootcoi/summary.json passed, fixture6/6/23 paires,ALU0/0 et1 nested-only,core69/4/11 paires/15 coords,65 partielles/15 nested-only. Simulation1536 assertions,256 ns, deux WIDTHTRUNC intentionnels non fatals, source SHA256 df629674002e0bffae98000f57e144fba34e0546d7892c5d28642c6a552eb895 ; reports/pr111-formal/run-jynd925r/summary.json passed,60 Z3 (31 UNSAT,29 SAT). CI50/50,347 s, artefacts15203393162/15203831763. Main #110 50/50,278 s. Union indicative80/384 non recalculée, aucune promotion.

### PR #112 — Décalages logiques bornés (fusionnée)

- [x] **PR112-SHIFT-LOGICAL-01 · P0** — 8 racines ALU/core chacune, 2 candidats attendus (masque constant et droite 64→32),1313 paires/138 coords par design,6 partielles signées ; 4 sites fixture/233 paires,32768 assertions,10 Z3 modèle. Replay exact, aucun gain historique promu.
- [ ] **PR112-SHIFT-SIGNED-01 · P0** — 6 formes signe construit, conversion/troncature, autres décalages signés et compositions, X/Z, intégration et corpus supplémentaires. Ne pas généraliser le modèle unsigned ; étudier avant multiplication. Bilan cœur #123 indicatif ou ultérieur ; toutes dettes conservées.

Validation #112 : [initiale](https://github.com/Antoine310/scientist_parseur/pull/112#issuecomment-7220254587), [local corrigé](https://github.com/Antoine310/scientist_parseur/pull/112#issuecomment-7220310595), [CI](https://github.com/Antoine310/scientist_parseur/pull/112#issuecomment-7220417875). Head initial3f0f7c6,29/30 SyntaxError runner, CI20 s 2 échecs/48 skipped ; correction syntaxique seule f4d83fba7f5c6811e8cad08faccc0a9c02782fc1, SHA local exact,30/30 0,17 s,1905/1905 7,42 s. reports/pr112/run-7uy0qz_h/summary.json passed, fixture4/4/233 paires, ALU/core2/8/1313 paires/138 coords chacun,6 partielles, core1 nested-only. Simulation32768 assertions,8192 ns, WIDTHTRUNC intentionnel non fatal, source SHA256 7320ae89b928dcde1daf555f708ae4e5a6eac380ac64b3ececd2392f177988f9. reports/pr112-formal/run-0fosd2ka/summary.json passed,10 Z3 modèle (5 UNSAT,5 SAT). CI50/50,309 s, artefacts15205235098/15203064492, fusion 6015ecf35da85e5c141d33da8129c7a9306f1e7f. Main #111 50/50,369 s. Union indicative82/384 non recalculée.

### PR #113 — Décalages arithmétiques à signe conditionnel (fusionnée)

- [x] **PR113-SIGNED-SHIFT-01 · P0** — Six sites réels ALU/core, 2×16 et4×8, signe construit AND mode/MSB, conversion n+1→n. 698 paires/154 coordonnées attendues par design, fixture2/88,8192 assertions,469 Z3 modèles, 30 tests/1935 suite. Pas de promotion. PR112-SHIFT-SIGNED-01 satisfaite pour les six occurrences réelles ; périmètre générique conservé sous PR113-SIGNED-SHIFT-GENERAL-01.
- [ ] **PR113-SIGNED-SHIFT-GENERAL-01 · P0** — Autres formes signées, quantités plus larges/overshift, conversions/composition, alias, X/Z, intégration et corpus supplémentaires. Multiplication #114 indicative, jalon cœur #124 ou ultérieur ; toutes dettes conservées.

Validation #113 : [local](https://github.com/Antoine310/scientist_parseur/pull/113#issuecomment-7220516993), [CI](https://github.com/Antoine310/scientist_parseur/pull/113#issuecomment-7220606930). SHA exact151e286b4692142c0265a4f7a4cffb7d0608e7fe, fusion bb7d0c98b3804809d0d1ea7e82e2b0333740830f. 30/30 0,18 s,1935/1935 7,63 s, reports/pr113/run-qalurw3e/summary.json passed, fixture2/2/88 paires/31 coords, ALU/core6/6/698/154 chacun ; simulation8192 assertions,4096 ns, deux WIDTHTRUNC intentionnels, source SHA256 7c151463136dfe62fdbdaac0b4905682f0b0c7084b9ebd35a73e0536205528be ; 469 Z3 modèles (160 UNSAT,309 SAT). CI50/50,296 s, artefacts15205611277/15206090433 ; main #112 50/50,380 s. Union indicative88/384 non recalculée, aucune promotion.

### PR #114 — Produits signés pleine largeur (fusionnée)

- [x] **PR114-MULTIPLY-01 · P0** — Six racines core IDs805–808/817–818, quatre produits9×9→18 et deux17×17→34, 2776 paires/280 coords attendues. 38 nested-only ALU/core, ALU0 racine. Fixture4/1240/136,800 assertions,123 Z3 modèles,30 tests ciblés/1965 suite. Coordonnées packed préservées, opérande pré-négativé direct, pas de composition ou promotion.
- [ ] **PR114-MULTIPLY-GENERAL-01 · P0** — Multiplications imbriquées, produits tronqués/mixtes, autres largeurs et conversions, X/Z, intégration, corpus supplémentaires ; conversions #115 ensuite, bilan cœur #124 ou ultérieur. Préserver toutes dettes.

Validation #114 : [local](https://github.com/Antoine310/scientist_parseur/pull/114#issuecomment-7220721433), [CI](https://github.com/Antoine310/scientist_parseur/pull/114#issuecomment-7220812727). SHA exact8b87ec2b3a68804f0302c86dd1baff6b10839c6a, fusion 1254826e67d5c4da8853d1e979876be4c335687d. 30/30 0,19 s,1965/1965 7,55 s, reports/pr114/run-cdbs2ff6/summary.json passed, fixture4/4/1240 paires/136 coords, ALU0 racine,core6/6/2776/280,38 nested-only chacun. Simulation800 assertions,400 ns,source SHA256739907f5c1446dd357c45bae0dca0440ae2f33473b474d2be71f31e18abdd80e ; reports/pr114-formal/run-_ikxvcfw/summary.json passed,123 Z3 modèles (57 UNSAT,66 SAT). CI50/50,302 s, artefacts15205932538/15206286747 ; main #113 50/50,335 s. Union indicative94/384 non recalculée, aucune promotion.

### PR #115 — Conversions constantes directes (en cours)

- [~] **PR115-CONSTANT-CONVERSION-01 · P0** — Core61 zéros CSR/2864 coordonnées et32 LUT unsigned/160 coordonnées,93 sites/3024 valeurs ; ALU32/160. Enum FS_t ID314 explicitement refusé. Fixture12/388,48 assertions,38 Z3 modèles,30 tests/1995 suite attendus. Zéro paire dynamique, pas de constante permanente ni promotion.
- [ ] **PR115-CONVERSION-GENERAL-01 · P0** — Conversions dynamiques signe/largeur/état, ambiguïté ConversionKind, enum, X/Z, appels et compositions ; évaluer avant composition générale. Conserver toutes dettes. Jalon cœur indicatif #124 ou ultérieur.

## 4. Feuille de route révisée — propositions de découpage, non engagements de numéros

**Feuille de route courante : [après #95](roadmap-after-pr95.md).** Le tableau ci-dessous est historique, les numéros proposés ne sont pas les PR réelles. Le document est introduit par une PR exclusivement documentaire, envisagée #66. Les travaux moteur partent **après fusion effective de #65 et de cette documentation**. Les numéros suivants sont prévisionnels, les IDs de dettes restent permanents.

**Ordre de priorité : mesurer → rendre les omissions visibles → corriger → vérifier par oracle → intégrer.** Ne pas attendre la fin de toutes les améliorations avant d'ajouter des tests scientifiques : chaque correction possède son propre oracle et sa non-régression. Ne pas viser artificiellement 100 % d'arêtes positionnelles ; viser une classification honnête de toutes les affectations recensées.

| PR proposée | Périmètre | Dettes principales | Gate de validation |
|---|---|---|---|
| #66 | Registre versionné, audit historique et roadmap | PR01-16-AUDIT-01, PR49-AUDIT-01, PR03-PLAN-01 | Aucun changement moteur ; historique et IDs conservés |
| #67 | Baseline détaillée des 24 instances, ALU, warnings, exclusions et causes de troncature | PR65-BIT-01/WARN-01/COV-01/LIMIT-01, PR61-BIT-01, PR23-COV-01 | Rapports avant correction, comptes réconciliés, causes de plafonds mesurées et non supposées |
| #68 | Budgets ciblés expressions/constructions complexes ; diagnostics d'omissions | PR19-EXPR-01, PR53-CPLX-01, PR62-LIMIT-01/02/COV-01, PR04-AST-01 | Seuils configurables bornés, tests aux limites ; comparaison temps/RSS, AST borné aussi dans worker #55 |
| #69 | Largeurs, extensions zéro/signe, troncature et casts | PR61-BIT-02, PR39-WIDTH-01, PR64-CAST-01, PR34-SEG-01 | Oracles exacts + simulation/mutants ; avant/après ALU et core |
| #70 | Largeurs et littéraux, deuxième partie | PR69-WIDTH-02, PR70-WIDTH-01/EVAL-01 | Types et positions prouvés, nouvelles récupérations mesurées et anciennes arêtes préservées |
| #71 | Layouts packed multidimensionnels et coordonnées fixes, dont tableaux procéduraux | PR70-ARRAY-01, PR60-ARRAY-01/02, PR61-BIT-06 | Positions/coordonnées démontrées, oracles sur CSR, register file et ALU ; pas d'aplatissement implicite |
| #72 | Opérateurs bitwise, réductions et transformations unaires | PR61-BIT-03 (logique), PR40-UNARY-01 | Représentation distincte des transformations, oracles et cas inconnus |
| #73 | Expressions conditionnelles, mux et gardes | PR61-BIT-04, PR20-PROC-01 | Gardes explicites, branches et priorités ; pas de faisabilité inférée |
| #74 | Indices dynamiques et tableaux : alternatives bornées | PR57-IDX-01, PR60-ARRAY-01/02, PR74-IDX-01 | Coordonnées et rôles exacts, oracles FIFO/fixture, aucune fausse arête |
| #75 | Sélecteurs constants élaborés : Power et preuve lexicale | PR57-IDX-01, PR74-IDX-02, PR75-IDX-01 | Oracle arbre ff_one, réutilisation bitwise/mux, aucune supposition runtime |
| #76 | Types de package : typedef/enum, constantes et coordonnées | PR76-TYPE-01, PR74-IDX-02 | Identité exacte, oracles debug et CSR |
| #77 | Orchestration CI, audit et gate Python | PR62-CI-01, PR05-CI-01, PR77-ORCH-01 | 46 validations historiques conservées, mesure avant/après, checks requis |
| #78 (première étape, initialement #77) | Structures/unions et concaténations LHS : inventaire et concat directes, puis layout et composition des sélections | PR36-TYPE-01, PR37-LVALUE-01, PR32-LVALUE-01, PR61-BIT-05/06, PR74-IDX-02 | Types et coordonnées prouvés, sans inférence de layout |
| #78 | Addition/soustraction, retenues, comparaison, shifts et multiplication (à découper) | PR61-BIT-03 (arithmétique), PR54-BUDGET-01 | Modèles justifiés de dépendances potentielles, bornes et oracle indépendant |
| #79 | Fonctions et appels | PR58-FUNC-01, PR10-ALU-01 | Identités, branches, actuals, effets de bord et appels non supportés explicités |
| #80 | Boucles et constructions procédurales complexes | PR59-LOOP-01, PR38-PBIT-01, PR20-PROC-01, PR29-GEN-01, PR33-INIT-01 | Bornes, exécution locale et cibles ; aucune expansion non bornée |
| #81 | Connexions bit à bit entre modules, index, InOut et traces | PR54-BIT-01, PR06-INDEX-01, PR07-PORT-01/TRACE-01, PR22-BIT-01 | Positions intermodules, limites de parcours, directions vérifiées ; oracle hiérarchique |
| #82 | Transitions séquentielles et écritures concurrentes | PR21-NBA-01, PR24-SEQ-01, PR47-NBA-01, PR51-TIME-01 | Priorité/hold/reset, blocking vs NBA, tests et propriétés ciblées |
| #83 | Intercycles hiérarchiques, événements et clock gating | PR31-EVENT-01, PR52-HIER-01, PR65-PATH-01 | Frontières d'événements et latences sous hypothèses explicites ; aucun CDC non prouvé |
| #84 | Réévaluation scientifique ALU, six unités et core + références externes | PR56-EVAL-01/02, PR63-MULTI-01, PR09-DEC-01, PR28-RTL-01, PR41-ORACLE-01, PR45-EVID-01 | Corpus gelé élargi, labels difficiles/negatifs/inconnus, scores par canal et avertissements résiduels |
| #85 | Répétitions performance et optimisation mesurée | PR55-PERF-01/02, PR65-PERF-01, PR62-CI-01, PR05-CI-01 | Min/médiane/max, CPU/RSS, requêtes, cache et CI sans perte de validation |
| #86 | Simulation du vrai CPU avec programmes RISC-V | PR65-SIM-01, PR64-EX-01, PR11-SIM-01, PR64-LINT-01 | Oracle ISA indépendant, mémoire et handshakes, traces architecturales et tests négatifs |
| #87 | Propriétés formelles et équivalence ciblées | PR17-FORMAL-01, PR12-FORMAL-01, PR13-EQY-01, PR14-EQY-01, PR48-FORMAL-01, PR25-EVID-01, FUT-FORMAL-01 | Hypothèses, preuves, contre-exemples, mutants et liaison exacte aux sources |
| #88 | MCP complet lecture seule et provenance | PR15-MCP-01, PR18-MCP-01/02, PR25-EVID-01, FUT-MCP-01, PR02-DOC-01, PR01-BASE-01 | Tests stdio réels, fraîcheur, pagination, budget et erreurs contrôlées |
| #89 | Variantes CV32E40P et import/reproductibilité | PR65-CONFIG-01, PR63-CONFIG-01, PR27-IMPORT-01, PR50-PIN-01, PR26-ENV-01 | Configurations indépendantes, pins et manifests vérifiés |
| #87+ | CVA6 (sous-hiérarchie puis cœur), IP OpenTitan et campagne de validation | PR35-CVA6-01, PR42-CJ-01, PR43-COMP-01, PR44-ISA-01, PR46-RAS-01, FUT-CVA6-01, FUT-OT-01 | Corpus autorisé, sources épinglées, mêmes métriques, oracles indépendants, exclusions |
| Après ces jalons | Benchmark agent et démonstration GhostGate | PR16-BENCH-01, FUT-AGENT-01, FUT-DEMO-01 | Comparaison A/B/C contrôlée, résultats reproductibles et limites explicites |

**Règle transversale :** PR61-BIT-01 et PR65-BIT-01 restent ouverts jusqu'à la classification justifiée de chaque famille, pas simplement jusqu'à #74. Les PR peuvent être scindées ou réordonnées selon la baseline #67 ; les tâches déjà ouvertes ne sont pas effacées. PR01-16-AUDIT-01 reste un audit de code/tests distinct des descriptions. PR03-PLAN-01 est révisé à chaque jalon. Les chiffres 225 ALU et 61 tableaux sont historiques #62 : recalculer avant chaque correction sur un même RTL/configuration. Les optimisations de CI peuvent être avancées dès qu'un blocage apparaît, sans retirer un test.

## 5. Objectifs différés de la feuille de route initiale (numéros historiques proposés ≠ PR réelles)

| ID | Travail ouvert | Critère de réussite |
|---|---|---|
| FUT-CVA6-01 | Sous-hiérarchie CPU CVA6 puis cœur complet, autre configuration reproductible | Manifest et sources épinglés, métriques, annotations et validations ciblées |
| FUT-OT-01 | Première IP OpenTitan autonome et autorisée | Elaborer, indexer, annoter, tests positifs/négatifs ; dépendances et paramètres documentés |
| FUT-FORMAL-01 | Catalogue de propriétés matérielles de sécurité (CSR, verrouillage, non-interférence, équivalence) | SBY/Yosys/Z3/EQY, hypothèses, contre-exemples, mutants, portée exacte |
| FUT-EVIDENCE-BRIDGE-01 | P3 — Relier automatiquement graphes de dépendances statiques, preuves SBY/EQY/Z3 et observations dynamiques Verilator/cocotb VCD/FST | Correspondance exacte hiérarchie/signaux/bits/configuration et provenance des sources ; reconstruire cycles par fronts d'horloge et phases explicites, traces bornées, témoins et contre-exemples, distinguer observation, corrélation, preuve et inconclusif ; oracle indépendant et mutants ; aucune preuve d'influence déduite de la seule corrélation, absence de trace non assimilée à absence de signal. Étudier après l'intégration actuelle, sans changement de priorité. |
| FUT-MJOLNIR-STUDY-01 | P3 — Étude différée de MJOLNIR ; références fournies à vérifier, [fiche](research/mjolnir.md) | Audit technique et juridique, provenance/licences, inventaire, comparaison RTLPrep et propositions testables ; liens FUT-MCP-01, FUT-AGENT-01, FUT-OT-01, FUT-EVIDENCE-BRIDGE-01 ; aucun import immédiat |
| FUT-MCP-01 | Investigation agent : source → écriture → gardes → chemins → evidence | MCP lecture seule, traces sourcées et limites, tests stdio et requêtes bornées |
| FUT-AGENT-01 | Benchmark agent contrôlé A=RTL brut, B=index, C=hybride RTLPrep | Questions/références gelées, mêmes conditions, exactitude, abstention, contexte, latence/coût, répétitions ; aucune affirmation de gain avant mesure |
| FUT-DEMO-01 | Démonstration GhostGate / HOST 2027, outil restant généraliste | Scénarios autorisés, résultats reproductibles, limites et validation scientifique ; ne pas présumer règlement/acceptation du concours |

### Phase finale — documentation et publication
- [ ] **FUT-DOC-USER-01 · P2** — Guides pédagogiques par outil/analyseur, concepts/entrées/sorties/exemples exécutés/limites, tutoriel de bout en bout, glossaire et références CLI/MCP/API/schémas. Version et outils épinglés, validation des commandes/liens et revue.
- [ ] **FUT-DOC-ARCHIVE-01 · P2** — README public centré sur objectifs, installation, usages et limites ; déplacer historique des PR hors README vers documentation développement, backlog/CI/rapports/changelog. Aucune perte d'IDs, preuves ou provenance.
- [ ] **FUT-DOC-CODE-01 · P2** — Revoir docstrings/commentaires : remplacer numéros PR inutiles par sémantique/invariants, conserver sécurité, justifications, licences et provenance utile ; aucune modification comportementale, aucune modification du RTL upstream, tests intégraux. Migrations de noms séparées si utiles. Phase H [feuille de route](roadmap-after-pr95.md).

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

### PR #116 — Conversions dynamiques directes (en cours)

- [~] **PR115-CONSTANT-CONVERSION-01 · P0** — #115 fusionnée, 93 sites core/3024 valeurs, ALU32/160, 1995 locaux, CI50/50 PR/main ; conserver l'ancienne entrée et confirmer SHA local. [Validation](https://github.com/Antoine310/scientist_parseur/pull/115#issuecomment-7221307450).
- [~] **PR115-CONVERSION-GENERAL-01 · P0** — Sous-périmètre #116 : audit AST #102 distinct des résiduels, 1 extension CSR hors flat ID attendue, 93 refus dont enum ID314 ; pas de gain résiduel attendu. Conversions imbriquées, signe ambigu, enum, X/Z, compositions et intégration restent ouvertes. [Périmètre](dynamic-conversions-pr116.md).

### PR #117 — Conversions enum directes (en cours)

- [~] **PR115-CONVERSION-GENERAL-01 · P0** — #116 fusionnée, 2025 locaux, CI PR/main50/50, 1 CSR dynamique hors flat, 16 paires +16 zéros. [Validation](https://github.com/Antoine310/scientist_parseur/pull/116#issuecomment-7221658679). #117 vise 92 constantes enum hors flat (318 valeurs) et ID314 (2 paires) après preuve exacte de déclaration/encodage et domaine binaire complet. Enum général, conversions imbriquées, signe ambigu, X/Z, compositions, recouvrements et intégration restent ouverts. [Périmètre](enum-conversions-pr117.md).

- #117 première validation : fixture 4 références enum taguées exclues à tort ; correction bornée par identité et valeur indépendante. Cœur 97 racines attendues, 96 constantes (330 valeurs), 1 dynamique (2 paires), ID314 uniquement dans les résiduels. Dette générale inchangée.

### PR #118 — Conversions 2/4 états (en cours)

- [~] **PR115-CONVERSION-GENERAL-01 · P0** — #117 fusionnée, 2061 locaux, CI PR/main50/50, 96 constantes enum/330 valeurs + ID314/2 paires. #118 : 81/1296 littéraux même largeur ALU/core (160/4022 positions expression), 31 recouvrements #115, 42 refus core attendus. Fixture dynamique et oracle Icarus quatre états distinct de Verilator binaire. Aucune nouvelle arête/ID historique revendiqués. X/Z généralisé, compositions, tailles/signe mixtes, intégration et recouvrements restent ouverts. [Périmètre](state-conversions-pr118.md).

### PR #119 — Composition décodeur d'écriture (en cours)

- [~] **PR115-CONVERSION-GENERAL-01 · P0** — #118 fusionnée, 2099 tests, CI PR/main50/50, Icarus128 checks, 81/1296 expressions ALU/core (160/4022 positions), 31 recouvrements #115, 42 refus core. Dette générale maintenue.
- [~] **PR96-COMPOSE-01 / PR111-LOGICAL-COMPOSE-01 · P0** — #119 64 résiduels core1044–1107 (448 paires attendues), composition extension non signée + égalité lexicale + mux scalaire, 0 ALU, oracle indépendant. PR74-IDX-02 et autres dettes restent ouvertes ; ne pas généraliser composition, X/Z, gardes, appels, boucles, preuve RTL, promotion/intégration historique. [Périmètre](decoder-composition-pr119.md).

### PR #120 — Composition décodeurs CSR (en cours)

- [~] **PR96-COMPOSE-01 / PR111-LOGICAL-COMPOSE-01 · P0** — #119 fusionnée,2138 locaux,CI PR/main50/50,64 IDs1044–1107/448 paires, union rapports79/98 et252/384. #120 cible IDs214–277, 64 sites/864 paires attendues, enum+addition constante+comparaison+AND/inhibition et paramètre largeur. Pas de généralisation, promotion, preuve globale, X/Z ou fermeture des dettes. PR115-CONVERSION-GENERAL-01, PR74-IDX-02, toutes dettes historiques conservées. [Périmètre](csr-composition-pr120.md).

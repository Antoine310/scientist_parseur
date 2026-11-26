# RTLPrep — Registre vivant des limites, optimisations et validations

**Version : 1.12 — 26 novembre 2026 (fusion #77 et chantier #78)**  
**Dépôt :** [Antoine310/scientist_parseur](https://github.com/Antoine310/scientist_parseur)  
**Dernière PR fusionnée confirmée : #77** (`4f894c0f70adf9bd72ed13cc6346f8ef2b305af3`). 47/47 jobs PR sur `331a39c6eaff812f59951df70bba99bf1fbab14f`.
**PR en cours : #78**, inventaire des agrégats et concaténations directes ; validation à effectuer.

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

### PR #78 — Agrégats : inventaire et concaténations directes (en cours)

- [~] **PR78-CONCAT-01 · P1** — Rapport expérimental séparé des graphes historiques : census syntaxique actif, concat LHS continue uniquement, NamedValue de type logic/bit scalaire ou vecteur non signé déclaré et identité sémantique exacte, largeur/état égaux, ordre LSB, cibles distinctes, aucun fallback par nom. Rejet atomique des conversions, sélections, agrégats, NBA et concat imbriquées. Oracle fixture indépendant et simulation 256 vecteurs prévus ; aucun gain officiel déclaré avant mesure.
- [ ] **PR78-CENSUS-01 · P1** — Inventorier MemberAccess LHS/RHS et concat LHS du vrai ALU et cœur, types observés et provenance ; dénominateur AST distinct de 1199, catégories recouvrantes. Clôture : rapports réconciliés et audit des identités/offsets avant extension struct/union. PR76-STRUCT-01, PR36-TYPE-01, PR37-LVALUE-01, PR32-LVALUE-01 et PR75-TYPE-01 restent ouvertes. Aucun layout de membre déduit du texte ou du nom ; aucune modification du graphe historique.

## 4. Feuille de route révisée — propositions de découpage, non engagements de numéros

Le document est introduit par une PR exclusivement documentaire, envisagée #66. Les travaux moteur partent **après fusion effective de #65 et de cette documentation**. Les numéros suivants sont prévisionnels, les IDs de dettes restent permanents.

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

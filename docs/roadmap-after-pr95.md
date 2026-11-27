# RTLPrep — Feuille de route après #95 (27 novembre 2026)

Proposition approuvée pour démarrer #96. Numéros indicatifs, non engagements ; les IDs permanents de dette restent dans [le registre vivant](rtlprep-backlog.md). Les anciennes propositions ne sont pas supprimées. Chaque PR conserve un oracle indépendant, refus explicites, non-régression et validation locale + CI au SHA exact ; pas de fusion sans autorisation. Les omissions P0, budgets et corpus indépendants peuvent avancer à tout moment.

## État de référence
- #95 fusionnée 92fb24f ; 1469 tests, 50 jobs CI, 98/384 résidus plats (ALU/cœur), 381/479 et 815/1199 avec support historique ou récupération liée. 612/3811 occurrences AST ≠ dénominateur bit. 30 occurrences membres, 1481 candidats séparés ; 18 outils MCP. Pas de couverture globale ni preuve générale.
- 31/64 racines Add après conversions, 39/137 lignes contenant Add, 8/150 Equality, 38/44 Multiply : comptes chevauchants, pas de gain garanti.

## A — Arithmétique et expressions (#96–104)
| PR indicative | Travail |
|---|---|
| 96 | Addition et retenues |
| 97 | Soustraction et emprunts |
| 98 | Comparaisons signées/non signées |
| 99 | Logique et réductions |
| 100 | Décalages fixes/dynamiques |
| 101 | Multiplication et dépendances partielles |
| 102 | Conversions largeur/signe/état |
| 103 | Composition arithmétique, mux, sélections |
| 104 | Bilan et audit des résidus |

**Révision après #96 (27/11/2026)** : résultat 0/31 ALU et 0/64 cœur, modèle/fixture validés. Artefact CI #96 : popcnt 31 dans chaque design, incréments CSR32 et adresse1 cœur. #97 sélecteurs lexicaux + zéro-extension popcnt, #98 incréments constants/composition, #99 soustraction proposée ensuite ; autres familles décalées selon résultats. Le tableau initial reste historique, toutes les familles et phases conservées. Aucun gain avant validation.

**Révision après #97** : 31/31 ALU et 31/64 cœur admissibles, 33 incréments cœur à traiter (#98). #99 soustraction proposée ensuite. Phase H ajoutée sur demande utilisateur, voir ci-dessous.

## B — Sémantique SV (#105–113)
105 fonctions et arguments ; 106 branches/appels imbriqués ; 107 boucles bornées ; 108 boucles imbriquées/écritures multiples ; 109 tableaux/register file ; 110 structures imbriquées/unions/identité champs ; 111 conditions complexes/casez/casex/Inside ; 112 inventaire exclusions bit ; 113 réévaluation cœur. Les omissions silencieuses P0 ne doivent pas attendre #112 : avancer les audits lorsque nécessaire.

## C — Temps et hiérarchie (#114–121)
114 connexions bit entre modules ; 115 propagation hiérarchique ; 116 blocking/NBA ; 117 priorité écritures ; 118 reset/enable/hold ; 119 événements/clock gating ; 120 intercycles ; 121 validation temporelle simulation/formel. Ne pas inférer CDC, latence ni faisabilité de chemins.

## D — Simulation CPU (#122–128)
122 banc cœur/mémoires ; 123 reset/boot/arithmétique ; 124 branches/sauts ; 125 load/store ; 126 CSR/exceptions/interruptions ; 127 stalls/multicycle ; 128 oracle ISA indépendant. Traces architecturales, tests négatifs, configurations et limites.

## E — Statique + dynamique + formel (#129–137)
129 VCD borné (FST ultérieurement selon support) ; 130 correspondance signaux ; 131 cycles et phases ; 132 observations liées au graphe ; 133 témoins d'influence par simulation ; 134 vérification formelle des dépendances ; 135 propriétés de sécurité (non-interférence, privilèges, états interdits, verrouillage) ; 136 équivalence et contre-exemples ; 137 MCP et preuves. FUT-EVIDENCE-BRIDGE-01, FUT-FORMAL-01, PR25-EVID-01, PR45-EVID-01. Provenance exacte par configuration, bits, sources, horloges, hypothèses et outils ; distinguer corrélation, observation, preuve, inconclusif. Pas de causalité déduite d'une trace. SBY/Yosys/EQY/Z3 : BMC, cover, preuve, équivalence et mutants réellement exécutés, pas de confusion entre résultats.

**Formel transversal dès #96** : propriétés ciblées et oracles indépendants pour chaque nouvelle famille lorsque pertinent, preuves de modèle distinguées des preuves RTL, hypothèses binaires vs 4 états, contre-exemples et limites ; ne pas attendre #134. Si preuve non exécutée ou inconclusive, le déclarer.

## F — Autres designs (#138–145)
138 variantes CV32E40P ; 139 annotations indépendantes ; 140 sous-modules CVA6 ; 141 cœur CVA6 ; 142 dépendances CVA6 ; 143 IP OpenTitan autonome ; 144 benchmark multi-design ; 145 bilan comparatif. Sources autorisées, épinglées, imports reproductibles, oracles, budgets et exclusions.

## G — Agents et démonstration (#146+)
146 optimisation contexte ; 147 questions gelées indépendantes ; 148 agent RTL brut ; 149 agent RTLPrep ; 150 comparaison précision/abstention/coût/latence, conditions équivalentes et répétitions ; 151+ GhostGate/documentation/reproductibilité. Inclure groupe index seul A/B/C, FUT-AGENT-01 ; pas de gain annoncé sans mesure, pas de garantie concours.

## H — Documentation, pédagogie et publication (phase finale, numéros à fixer)

FUT-DOC-USER-01, FUT-DOC-ARCHIVE-01, FUT-DOC-CODE-01. Après maturité fonctionnelle et benchmark, sans retarder la documentation minimale de chaque PR. Trois chantiers séparés :
- README public : objectifs, public, installation, quickstart reproductible, architecture, CLI/MCP, exemples et limites ; retirer récit par PR, sans perte d'historique. Déplacer vers docs/development/ ou index de liens backlog, ci-history, changelog, rapports et preuves ; conserver IDs, provenance et liens.
- Guides pédagogiques par outil et analyseur : slang/AST, Python/graphes, Verilator/cocotb, VCD/FST, Yosys, SBY, EQY, Z3, CLI/MCP. Concepts, fonctionnement, entrées/sorties, options vérifiées, exemples exécutés, interprétation et limites ; tutoriel complet, glossaire, architecture, API/schémas et méthodologie scientifique. Documenter seulement capacités réelles de la version publiée. Organisation cible docs/getting-started/, tools/, architecture/, science/, reference/, development/, validation/.
- Commentaires et docstrings RTLPrep : remplacer références PR superflues par explications sémantiques/invariants, conserver justification scientifique, hypothèses, provenance utile, sécurité et licences. Pas de modifications RTL upstream. Ne pas supprimer tests/rapports/IDs. Garder noms historiques si stabilité utile, migrations séparées. Revue pédagogique, liens valides, commandes et exemples exécutés sur version épinglée, non-régression intégrale ; aucun changement comportemental dans PR de nettoyage.

## Transversal
P0 omissions, corpus indépendants, budgets/reproductibilité ; P1 provenance preuve, identité champs, sémantique, transitions ; P2 CI/caches/installations, limite des workflows réutilisables, erreurs MCP PR94-ERROR-01 et budgets PR94-GLOBAL-BUDGET-01, profils et optimisation. P3 exécuteur Linux déterministe autorisé via GitHub et machine utilisateur, outils EDA locaux ; aucun contournement quota/service ou exécution libre de contenu non fiable. Historique CI chaque head/attempt et main, temps mur, somme jobs exécutés, échecs/annulations/skips, local séparé. Priorités révisées selon mesures et dettes sans renumérotation.

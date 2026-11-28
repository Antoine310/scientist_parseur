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

**Révision après #98** : #97/#98 union exacte 31/31 ALU et64/64 core Add résiduelles, pas de promotion historique. #99 traite 2 racines Subtract core (offset LSU, masque shift), cinq imbriquées restent dette ; comparaisons ensuite selon résultats. Phase H conservée.

**Révision après #99** : deux racines Subtract core caractérisées, union arithmétique 31 ALU/66 core, 67/318 résidus restants ; #100 égalités et inégalités directes après inspection AST, comparaisons d'ordre signées composées différées. Aucun gain annoncé avant validation. Les familles A–H restent inchangées.

**Révision après #100** : ALU4/core6 égalités/inégalités caractérisées, union exacte 35/72, reste63/312 ; Z3 188 requêtes, CI50/50. #101 cible 4 GreaterThan par design avec bit de signe masqué et contrôle partagé après inspection AST réelle ; autres comparaisons, compositions et omissions restent ouvertes. Aucun gain avant validation.

**Révision après #101** : 4 GreaterThan par design caractérisées, union39/76, reste59/308 ; local1609/1609, CI50/50, simulation131072 et Z3 112. Omission historique Call.arguments détectée, dette PR101-CAPTURE-01 P0 : #102 audit indépendant et traçage des décisions sans changer les dénominateurs, puis correction versionnée selon résultats. Reprendre les autres familles arithmétiques ensuite. Phases A–H conservées.

**Révision après #102** : audit P0 validé ; 13 omissions core (7 appels,5 conditions ternaires,1 pattern), zéro ALU ; 5 cibles CSR non supportées. #103 corrige l'admission en mode opt-in versionné, lignes nouvelles partielles, projection historique exacte ; intégration publique et corpus indépendants ultérieurs. Unions #95–101 inchangées, phases A–H préservées.

**Révision après #103** : admission v2 opt-in validée, core1199→1212, 13 nouvelles lignes partielles, zéro arête et zéro support ajouté, ALU479 inchangé. #104 publication séparée CLI/MCP avec versions explicites, provenance et budgets, corpus indépendants ; historique inchangé. Autres omissions et sémantique restent ouvertes.

**Révision après #104** : publication V1/V2 CLI/MCP validée sur six designs, 1684 tests,50 jobs,43 pages,24 refus attendus. rxuart87 occurrences/16 captures/15 non visitées/2 cibles refusées, contexte Initial selon artefact. #105 audit P0 des arrêts du walker avant extension sémantique ; migration du défaut et présentation erreurs MCP différées. Phases A–H et familles historiques conservées.

**Révision après #105** : audit effectif validé sur six designs, 15 exclusions Initial rxuart (1 avec sélection), 2 cibles concaténées distinctes, aucune inexpliquée dans ce périmètre. #106 cible les NBA scalaires rxuart avec oracle positionnel, simulation fixture et modèle binaire Z3 ; pas de promotion ni preuve temporelle, Initial et 5 cibles CSR restent ouvertes. Phases A–H conservées.

**Révision après #106** : deux cibles concat scalaires rxuart caractérisées,6 records,160 checks fixture et8 Z3 modèle, CI50/50,1731 tests ; 5 cibles CSR restantes. #107 audit du recouvrement PR80/88 et scopes generate. 

**Découpage indicatif convenu après #106, jusqu'au prochain bilan statique cœur :** #107 audit CSR ; #108 concat vectorielles/sélections/alias (correction generate à intercaler si nécessaire) ; #109 Initial ; #110 logique/réductions ; #111 shifts ; #112 multiplication ; #113 conversions largeur/signe/X/Z ; #114 composition ; #115 fonctions/arguments ; #116 branches/appels imbriqués ; #117 boucles bornées ; #118 boucles imbriquées/écritures multiples ; #119 tableaux/register file ; #120 structures/unions/champs ; #121 conditions complexes/casez/casex/Inside ; #122 audit consolidé ; **#123 bilan scientifique cœur complet**. Puis #124–131 hiérarchie/temporalité, #132–138 simulation CPU/oracle ISA. Numéros non contractuels, toutes dettes et phases A–H préservées, P0 avancées si nécessaire. Ne pas assimiler le bilan statique à une simulation du CPU.

**Révision après #107 (fusionnée, 1751 tests et 50 jobs)** : 3/5 refus CSR déjà représentés PR80/88, 2 scopes generate. #108 traite ces deux sites avant les concat vectorielles (PR106-CONCAT-GENERAL-01 reste ouverte). Numéros prévisionnels suivants à décaler selon résultats ; bilan #123 indicatif. Aucune modification des dénominateurs historiques.

**Révision après #108** : 1785 tests,50 jobs, deux cibles generate CSR/33 candidats séparés, simulation768 et Z3 modèle43 ; trois positions membre existantes non recomptées. #109 concat vectorielles et sélection fixe, puis #110 Initial ; corpus plus larges et intégration restent ouverts. Bilan cœur #123 indicatif ou ultérieur.

**Révision après #109** : #109 fusionnée,1815 tests,9 candidats fixture,768 assertions,20 Z3 ; CI50/50,394 s. Initial directes zéro, 13 sites/47 bits rxuart attendus ; paramètres séparés, aucune constante permanente ni preuve globale. Bilan cœur #123 indicatif.

**Révision après #110** : fusionnée1845 tests/50 jobs,13 Initial rxuart/47 bits,2 paramètres partiels. #111 arbres logiques/réductions directes,69 racines résiduelles core dont4 candidats attendus. #112 shifts, #113 multiplication, suite selon backlog ; bilan cœur #123 indicatif.

**Révision après #111** : 1875 tests/50 jobs,4 racines core/11 paires,65 partielles. #112 décalages logiques bornés, deux racines réelles ALU/core, six signées partielles à traiter séparément. Multiplication ensuite selon mesures ; bilan cœur #123 indicatif.

**Révision après #112** : fusionnée1905 tests/50 jobs,2 décalages logiques/1313 paires par design ALU/core. #113 signe conditionnel des six shifts restants, puis multiplication #114 indicative. Les numéros ultérieurs sont décalés à titre indicatif ; jalon cœur #124 ou ultérieur.

**Révision après #113** : 1935 tests/50 jobs, six shifts signés traités, 698 paires par design, 8/8 racines historiques shift avec #112, union indicative88/384. #114 six produits signés pleine largeur, #115 conversions, suite selon backlog ; jalon cœur #124 indicatif.

**Révision après #114** : fusionnée1965 tests/50 jobs,6 produits signés core/2776 paires,38 nested-only par design. #115 conversions constantes directes, 93 sites réels attendus core, 32 ALU. Conversions dynamiques/enum/XZ restent séparées avant composition ; jalon cœur #124 indicatif ou ultérieur.

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

**FUT-MJOLNIR-STUDY-01 · P3** : audit différé de MJOLNIR, [fiche de recherche](research/mjolnir.md). Références utilisateur à vérifier ; aucune étude ou réutilisation immédiate, aucune modification des priorités. Liens FUT-MCP-01, FUT-AGENT-01, FUT-OT-01, FUT-EVIDENCE-BRIDGE-01.

## H — Documentation, pédagogie et publication (phase finale, numéros à fixer)

FUT-DOC-USER-01, FUT-DOC-ARCHIVE-01, FUT-DOC-CODE-01. Après maturité fonctionnelle et benchmark, sans retarder la documentation minimale de chaque PR. Trois chantiers séparés :
- README public : objectifs, public, installation, quickstart reproductible, architecture, CLI/MCP, exemples et limites ; retirer récit par PR, sans perte d'historique. Déplacer vers docs/development/ ou index de liens backlog, ci-history, changelog, rapports et preuves ; conserver IDs, provenance et liens.
- Guides pédagogiques par outil et analyseur : slang/AST, Python/graphes, Verilator/cocotb, VCD/FST, Yosys, SBY, EQY, Z3, CLI/MCP. Concepts, fonctionnement, entrées/sorties, options vérifiées, exemples exécutés, interprétation et limites ; tutoriel complet, glossaire, architecture, API/schémas et méthodologie scientifique. Documenter seulement capacités réelles de la version publiée. Organisation cible docs/getting-started/, tools/, architecture/, science/, reference/, development/, validation/.
- Commentaires et docstrings RTLPrep : remplacer références PR superflues par explications sémantiques/invariants, conserver justification scientifique, hypothèses, provenance utile, sécurité et licences. Pas de modifications RTL upstream. Ne pas supprimer tests/rapports/IDs. Garder noms historiques si stabilité utile, migrations séparées. Revue pédagogique, liens valides, commandes et exemples exécutés sur version épinglée, non-régression intégrale ; aucun changement comportemental dans PR de nettoyage.

## Transversal
P0 omissions, corpus indépendants, budgets/reproductibilité ; P1 provenance preuve, identité champs, sémantique, transitions ; P2 CI/caches/installations, limite des workflows réutilisables, erreurs MCP PR94-ERROR-01 et budgets PR94-GLOBAL-BUDGET-01, profils et optimisation. P3 exécuteur Linux déterministe autorisé via GitHub et machine utilisateur, outils EDA locaux ; aucun contournement quota/service ou exécution libre de contenu non fiable. Historique CI chaque head/attempt et main, temps mur, somme jobs exécutés, échecs/annulations/skips, local séparé. Priorités révisées selon mesures et dettes sans renumérotation.

**Révision après #115** : fusion confirmée, CI PR/main50/50, 1995 tests locaux (SHA non imprimé), 93 sites core/3024 valeurs, ALU32/160, union indicative187/384 et79/98 à recalculer. #116 audit direct dynamique hors résiduels (1 CSR attendu), enum ID314 et conversions imbriquées/ambiguës/XZ restent ouvertes. Jalon cœur indicatif, aucune dette supprimée.

**Révision après #116** : fusion confirmée, CI PR/main50/50, 2025 tests locaux SHA exact, un CSR direct hors flat (16 paires +16 zéros), union historique indicative79/98 et187/384 inchangée. #117 enum direct : 92 constantes hors flat, ID314 candidat dynamique, aucune promotion. X/Z et compositions ensuite selon mesure ; conserver toutes les phases et dettes.

**Révision après #117** : fusion confirmée, CI PR/main50/50,2061 locaux SHA exact,97 sites enum (330 valeurs,2 paires ID314), union indicative79/98 et188/384. #118 conversions bit/logic mêmes largeur/signe ; expression-relative et dynamique fixture séparées, 31 recouvrements #115, aucune augmentation historique. Composition ensuite selon audit, toutes dettes et phases préservées.

**Révision après #118** : fusion et CI PR/main50/50,2099 locaux (SHA non imprimé), ALU81/core1296 expressions, 31 recouvrements #115, union des IDs de rapports79/98 et188/384. #119 composition décodeurs register file, 64 résiduels core attendus, objectif252/384 avant audit final interversions. Fonctions/arguments, branches, boucles, tableaux, structures, case et audit consolidé ensuite selon mesures ; jalon statique indicatif, préserver phases A–H et toutes dettes.

**Révision après #119** : fusion confirmée,CI PR/main50/50,2138 locaux (SHA non imprimé),64 résiduels core/448 paires, union rapports79/98 et252/384. #120 CSR lower/upper 64 sites/864 paires attendues, objectif316/384 conditionnel. Fonctions/arguments, branches, boucles, tableaux, agrégats, case et audit consolidé restent ouverts ; conserver phases A–H, jalon statique indicatif.

**Révision après #120** : fusion confirmée, CI PR/main50/50,2184 locaux SHA exact,64 résiduels core/864 paires, union rapports79/98 et316/384. #121 lane concat 8 ALU/8 core, 8 paires et8 valeurs locales par design, objectif87/98 et324/384 conditionnel. Jalon statique indicatif ; préserver toutes dettes et phases A–H.

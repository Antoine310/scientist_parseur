# PR #77 — CI : inventaire et migration

## Référence avant changement

- Dépôt : Antoine310/scientist_parseur ; main `fa5a797a8044d4680bb8ed216115c7283bfc4fb4`.
- PR #76, head `f0a52453528faa8b1567206329e4447bae940ceb` : 46 runs pull_request et 39 runs push, tous success (85/85). Source : [API Actions, head filtré](https://api.github.com/repos/Antoine310/scientist_parseur/actions/runs?head_sha=f0a52453528faa8b1567206329e4447bae940ceb&per_page=100).
- Fenêtre PR : 09:31:31–09:49:19 UTC le 26/11/2026, 1068 s (17 min 48 s) entre première création et dernière mise à jour ; push : 09:31:26–09:49:03 UTC, 1057 s. Ce sont des durées murales avec attente, pas des temps CPU ni des minutes facturées. Un seul head, pas un benchmark répété.
- Local #76 : 1106/1106 tests en 3,46 s, environnement complet (rapport local communiqué sur la PR).
- 46 fichiers de workflow, dont 45 validations spécialisées et le job Python. Les 39 doubles déclenchements sont observés, non estimés.
- Règles du dépôt : API rulesets vide ; API branch protection 403 pour cette intégration. Le propriétaire doit vérifier les checks requis avant fusion (nouveau nom de check : RTLPrep full validation). Ne pas retirer les anciens checks avant la validation complète de leur remplacement.

## Migration

Le seul déclencheur automatique devient ci.yml : pull_request et push sur main. Les branches sans PR ne lancent plus automatiquement la suite ; ouvrir une PR brouillon ou déclencher manuellement. Aucun filtre de chemins. Les 45 workflows spécialisés restent déclenchables via workflow_dispatch et sont appelés par workflow_call après succès de unit-tests. Les 45 blocs jobs historiques sont conservés octet pour octet ; les permissions, versions, oracles, artefacts et timeouts sont conservés. Le job Python reçoit uniquement un compileall supplémentaire et les trois tests de contrat CI (nouveaux tests). La concurrence est portée par le workflow parent, par ref de PR ; aucun groupe partagé parent/enfant. Les pushes main et exécutions manuelles ont des groupes uniques. Le verdict final exige 46 résultats success ; failed, skipped ou cancelled ne sont pas des succès. Une annulation du run entier n'est pas une validation.

Les anciens checks GitHub changent de contexte/nom en passant en reusable workflows : vérifier les règles avant fusion. Checkout PR historique (commit de merge synthétique) conservé ; distinguer head SHA et SHA réellement checkouté. Les appels manuels ciblés restent des diagnostics, jamais une validation complète. Aucun changement RTL ou moteur.

### Matrice exhaustive : ancien fichier → job appelant

| Workflow d'origine | Job |
|---|---|
| ci.yml | unit-tests |
| analysis-budgets-pr62.yml | analysis-budgets-pr62 |
| analyzer-row-budgets-pr68.yml | analyzer-row-budgets-pr68 |
| annotated-pr56.yml | annotated-pr56 |
| array-pr60.yml | array-pr60 |
| bit-refinement-pr61.yml | bit-refinement-pr61 |
| bit-width-pr69.yml | bit-width-pr69 |
| bit-width-pr70.yml | bit-width-pr70 |
| bitgraph-pr54.yml | bitgraph-pr54 |
| bitwise-pr72.yml | bitwise-pr72 |
| cocotb-simulation.yml | cocotb-simulation |
| complex-pr53.yml | complex-pr53 |
| constant-indices-pr57.yml | constant-indices-pr57 |
| cv32e40p-alu-real.yml | cv32e40p-alu-real |
| cv32e40p-core-pr65.yml | cv32e40p-core-pr65 |
| cv32e40p-diagnostics-pr67.yml | cv32e40p-diagnostics-pr67 |
| cv32e40p-ex-stage-pr64.yml | cv32e40p-ex-stage-pr64 |
| cv32e40p-multi-unit-pr63.yml | cv32e40p-multi-unit-pr63 |
| cv32e40p-popcnt-eqy.yml | cv32e40p-popcnt-eqy |
| cv32e40p-real.yml | cv32e40p-real |
| cva6-cj-verilator-oracle.yml | cva6-cj-verilator-oracle |
| cva6-cli-verilator-oracle.yml | cva6-cli-verilator-oracle |
| cva6-compressed-decoder.yml | cva6-compressed-decoder |
| cva6-compressed-verilator-oracle.yml | cva6-compressed-verilator-oracle |
| cva6-lane-evidence.yml | cva6-lane-evidence |
| cva6-ras.yml | cva6-ras |
| dynamic-pr74.yml | dynamic-pr74 |
| eqy-equivalence.yml | eqy-equivalence |
| function-pr58.yml | function-pr58 |
| hierarchy-pr52.yml | hierarchy-pr52 |
| intercycle-pr51.yml | intercycle-pr51 |
| mcp-stdio.yml | mcp-stdio |
| mux-pr73.yml | mux-pr73 |
| packed-coordinates-pr71.yml | packed-coordinates-pr71 |
| priority-pr47.yml | priority-pr47 |
| reset-formal-pr48.yml | reset-formal-pr48 |
| rtl-benchmark.yml | rtl-benchmark |
| rtl-fixtures.yml | rtl-fixtures |
| rtl-security-lab.yml | rtl-security-lab |
| sby-formal.yml | sby-formal |
| scalability-pr55.yml | scalability-pr55 |
| selector-recovery-pr75.yml | selector-recovery-pr75 |
| slang-integration.yml | slang-integration |
| static-loops-pr59.yml | static-loops-pr59 |
| typed-layout-pr76.yml | typed-layout-pr76 |
| unknown-rtl-validation.yml | unknown-rtl-validation |

## Validation à réaliser avant fusion

1. Vérifier syntaxe YAML / graphe, liste des 46 validations et égalité des blocs jobs spécialisés avec le parent Git.
2. Vérifier les tests Python locaux et le run consolidé du head exact : chaque validation et le verdict final success ; vérifier rapports/artéfacts, y compris simulation, preuve, équivalence et contrôles négatifs.
3. Tester l'annulation sur PR et le gate sur échec contrôlé ; ne pas fusionner un head de test volontairement rouge.
4. Mesurer fenêtre création–fin, jobs réels, attente, durée d'exécution et installations sur plusieurs runs comparables ; distinguer réduction d'événements et gain de temps.
5. Vérifier les checks requis avec le propriétaire et conserver le gate avant fusion.

Les installations EDA restent indépendantes : ne pas partager un cache non vérifié. Mutualisation des recettes et caches avec empreintes/versions et mesures avant/après à traiter dans PR62-CI-01 après validation de cette migration ; ne pas clôturer cette dette sur le seul regroupement. GitHub limite à 50 workflows réutilisables uniques par orchestrateur (45 ici) : prévoir une consolidation par familles avant de dépasser la limite. Source : https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations.

Agent local différé : poursuivre avec GitHub Actions et réévaluer après plusieurs PR, sans API payante, sans contournement des quotas ni exécution arbitraire. Aucun agent local implémenté.

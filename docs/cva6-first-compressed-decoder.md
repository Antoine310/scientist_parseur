# Premier module du vrai CVA6 — compressed decoder (PR #35)

## Objectif

Faire passer un **vrai module de processeur CVA6 OpenHW** dans la
chaîne slang → AST élaboré → index hiérarchique → graphe de
dépendances → traces bornées et rapport de limites.

Il ne s'agit ni d'une analyse de tout le cœur ni d'une preuve de
correction fonctionnelle du décodeur.

## Provenance vérifiable

- Dépôt externe officiel : <https://github.com/openhwfoundation/cva6>
- Commit épinglé : `742dc82a0c706e0a3bfb98b709fd3ee06d50d12a`
- Module : `core/compressed_decoder.sv`
- Configuration issue du dépôt officiel : `core/include/cv32a6_imac_sv32_config_pkg.sv`
- Packages utilisés dans l'ordre : `config_pkg.sv`,
  `cv32a6_imac_sv32_config_pkg.sv`, `riscv_pkg.sv`,
  `build_config_pkg.sv`; puis `compressed_decoder.sv`.
- Wrapper **créé dans RTLPrep**, non repris de l'amont :
  `tests/fixtures/cva6/compressed_decoder_probe.sv`

Ce wrapper passe `build_config_pkg::build_config(cva6_config_pkg::cva6_cfg)`
au paramètre `CVA6Cfg` du décodeur. Il évite de considérer le
`cva6_cfg_empty` par défaut comme une configuration authentique.

Les cinq fichiers du dépôt officiel sont contrôlés par leurs empreintes
**Git blob SHA-1 réelles**, avant et après l'élaboration. Le commit exact
est en plus vérifié lorsqu'il s'agit d'un checkout Git. Les sources RTL
tierces ne sont **pas** vendues avec RTLPrep.

## Reproduire en local

Le dépôt CVA6 doit être à côté des autres sources externes, par exemple
dans `upstream_cva6`. Le clone peut être partiel :

```bash
cd ~/projets/scientist_parseur
git clone --filter=blob:none --no-checkout \
  https://github.com/openhwfoundation/cva6.git upstream_cva6
cd upstream_cva6
git sparse-checkout init --no-cone
git sparse-checkout set \
  core/include/config_pkg.sv \
  core/include/cv32a6_imac_sv32_config_pkg.sv \
  core/include/riscv_pkg.sv \
  core/include/build_config_pkg.sv \
  core/compressed_decoder.sv
git checkout --detach 742dc82a0c706e0a3bfb98b709fd3ee06d50d12a
cd ..
source .venv/bin/activate
source "$HOME/.local/share/rtlprep/toolchains/activate.sh"
python -m pytest -q -rs tests/test_cva6_compressed_decoder.py
python scripts/run_cva6_compressed_decoder.py \
  --source-root upstream_cva6 \
  --out reports/cva6-compressed-decoder \
  --timeout 240
```

Si `upstream_cva6` existe déjà, ne pas refaire le clone : vérifier
l'origine, la révision et les fichiers avant de lancer l'analyse.
Ne jamais modifier les données non suivies de `docs/agent-reports/`.

## Résultat réel de la première CI (slang 12.1)

Le Git checkout officiel à `742dc82` et les cinq blobs ont été
vérifiés. L'élaboration a produit **2 instances**, **12 signaux / nœuds**,
**13 arêtes**, dont **6 de contrôle**, **1 de données**, **1 liaison d'entrée**
et **5 liaisons de sortie**. Le graphe contient **1 avertissement :
`Expression non prise en charge : MemberAccess`**.

Les cinq sorties ont un chemin `fanin` observable jusqu'au port d'entrée
`instr_i`, sans troncature avec le budget de cette expérience. En revanche,
**93 affectations** ont été répertoriées par l'index d'expressions, dont
**57 partielles**. `register_flow` ne capture aucun enregistrement car
son périmètre est l'analyse des `always_ff`, et `bit_accesses` ne capture
aucun enregistrement parce qu'il ne couvre actuellement que les assignations
continues. **Ces zéros ne sont pas des résultats complets !**

Cette disproportion (**13 arêtes pour 93 affectations syntaxiques**) est
un excellent signal de recherche, mais pas un ratio fiable de couverture :
les arêtes sont dédupliquées par signal et une seule arête peut résumer de
multiples affectations. Il n'y a pas d'oracle indépendant exhaustif.
`coverage_assessment=reported_limits` reste donc la seule conclusion
raisonnable.

La prochaine amélioration devrait examiner les membres statiques de
`CVA6Cfg` dans l'AST slang et les 57 expressions partielles pour
augmenter la précision **sans transformer des constantes en signaux
de runtime**, puis élargir le contexte d'analyse des sélections dans
des processus combinatoires.

## Sorties et limitations

Le rapport `cva6_compressed_decoder_report.json` inclut
la révision, la configuration, le statut d'intégrité, les ports,
l'inventaire des instances, les compteurs des arêtes et avertissements,
les analyseurs `expressions`, `register_flow` et `bit_accesses`,
ainsi que des traces `fanin` bornées pour les cinq sorties
(`instr_o`, `illegal_instr_o`, `is_macro_instr_o`,
`is_compressed_o`, `is_zcmt_instr_o`).

En particulier, `observed_input_reachable` est **observé** et non
forcé : une sortie dont le chemin vers `instr_i` manque ne doit
pas être présentée comme complètement analysée. La compilation
ne prouve pas l'exactitude du graphe.

La couverture totale du design reste `not_measured` ;
la correction fonctionnelle reste `not_tested` ;
l'accuracy n'est pas mesurée sans oracle indépendant.
Aucune simulation ni preuve formelle du comportement
des instructions compressées n'est incluse dans cette PR.

La PR suivante pourra corriger les catégories de limites
**réellement révélées** par ce module, puis progresser vers une
seconde IP et vers la hiérarchie du CVA6.

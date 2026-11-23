# PR #42 — Vérification comportementale indépendante du vrai décodeur CVA6 : `c.j`

## Contexte et ordre des PR

Le **23 novembre 2026**, la PR #41 a été fusionnée **dans la branche de la #40**, et non dans `main`. Les PR #39 et #40 sont encore ouvertes en brouillon. La PR #42 est empilée sur **`feat/cva6-unaryop-bit-scope-v1`** (branche de #40) et devra être reciblée après revue et fusion de ses bases.

**Ordre prévu : #39 → #40 (contient déjà #41) → #42.**

Aucune fusion ni modification directe de `main` n'a lieu dans cette PR.

## Ce qui change par rapport à la #41

La #41 simulait **une fixture RTLPrep** mimant certains opérateurs de bits. La #42 compile et simule les **octets officiels de `core/compressed_decoder.sv` de OpenHW CVA6** et ses packages, dans la configuration explicitement épinglée `cv32a6_imac_sv32`.

Le wrapper `tests/fixtures/cva6/compressed_decoder_probe.sv` est le même que pour l'analyse statique. Il ne réimplémente pas le décodeur.

L'empreinte exacte est vérifiée **avant et après** la simulation :

- Dépôt : `openhwfoundation/cva6` ;
- Commit : `742dc82a0c706e0a3bfb98b709fd3ee06d50d12a` ;
- Git SHA-1 blobs : les cinq fichiers épinglés dans `scripts/run_cva6_compressed_decoder.py`, dont `core/compressed_decoder.sv` = `76385e5ea0b9eb0cc2d0e96fe978a90d4e122c19` ;
- Outils CI : **Verilator 5.040**, **cocotb 2.0.1** ;
- Paramètre officiel : `build_config_pkg::build_config(cva6_config_pkg::cva6_cfg)`.

## Quelle portion du vrai CVA6 est vérifiée ?

La branche combinatoire `c.j` (quadrant compressé C1, code opération `101`) :

```systemverilog
// Éléments de la branche c.j officielle, cités à titre de repère :
~instr_i[15]
riscv::OpcodeJal
```

La concaténation 32 bits complète construit un JAL RISC-V. Le bit 7 provient de la **négation** du bit 15 de l'instruction compressée. Dans l'encodage `c.j`, ce bit 15 vaut 1 ; la valeur attendue du bit 7 est donc **0**.

Notre référence `rtlprep/cva6_cj_reference.py` construit la valeur de 32 bits indépendamment de l'AST, du graphe et de `rtlprep.bitaccess`. Il ne calcule aucune réponse à partir du JSON de RTLPrep : les positions de chaque champ sont une spécification testée **séparée**.

La suite `rtlprep/sim_tests/cva6_cj_official.py` compare les sorties réellement simulées aux valeurs de l'oracle : `instr_o` (32 bits), `illegal_instr_o`, `is_macro_instr_o`, `is_compressed_o` et `is_zcmt_instr_o`.

### Stimuli de simulation

| Jeu de tests | Nombre | Ce qu'il couvre |
| --- | ---: | --- |
| Dirigés | 32 | 16 motifs significatifs, 2 valeurs du mot haut |
| Tous les encodages bas `c.j` | **2048** | 11 bits variables `instr_i[12:2]`, mot haut nul |
| Mot haut variable, déterministe | 256 | 256 couples pseudo-aléatoires, graine `0x42C0A6` |
| Total | **2336** | 3 tests cocotb, motifs pouvant se répéter |

Les **2048 possibilités sont exhaustives uniquement pour les 11 bits variables** de l'encodage `c.j` dans le mot bas, lorsque les 16 bits hauts valent zéro. On **ne** couvre **pas** toutes les (2^{32}) entrées possibles. Ce n'est **pas** une simulation à quatre états (`X/Z`).

## Contrôle négatif indispensable

Le script `scripts/run_cva6_cj_oracle.py` crée uniquement dans son répertoire de sortie une **copie de travail générée** avec **une modification exacte** de la branche `c.j` :

```systemverilog
// Comportement officiel : bit 7 inversé
~instr_i[15],

// Mutation unique volontairement incorrecte :
instr_i[15],
```

Le checkout Git OpenHW n'est **jamais modifié** et le dépôt RTLPrep ne contient **aucune copie du RTL tierce**.

Le mutant est compilé et simulé **avec le même wrapper, les mêmes packages, le même oracle et les mêmes vecteurs**. Son échec n'est accepté que si le rapport cocotb XML contient une vraie assertion `PR42_CJ_VALUE_MISMATCH` avec **`bit7_diff=1`**. Un problème de compilation, de checkout, de versions d'outil ou un échec sans rapport doit rester **une défaillance CI**, pas un test négatif réussi.

Deux résultats sont publiés séparément :

- `reports/pr42-cva6-cj-gold/cva6_cj_simulation.result.json` et `simulation_results.xml`.
- `reports/pr42-cva6-cj-mutant/cva6_cj_simulation.result.json` et `simulation_results.xml`.

Les rapports conservent les empreintes, la provenance, le statut réel et les décomptes des tests. Les fichiers sont chargés comme artefacts GitHub Actions même en cas d'échec.

## Différence entre la preuve d'une propriété et le résultat obtenu

Si les résultats CI sont verts, nous pourrons dire :

- que **cette version épinglée du vrai décodeur CVA6** a produit les valeurs prévues pour les **2336 stimuli** `c.j` soumis ;
- que la mutation ciblant `~instr_i[15]` a été détectée sur le bit 7 ;
- que les dépendances positionnelles déclarées par RTLPrep pour ce champ sont cohérentes avec ces observations à deux états.

**Nous ne pourrons pas dire** que le décodeur est entièrement correct, que les autres encodages RISC-V ont été validés, que le modèle temporel entier est couvert, ni que le graphe RTLPrep est exhaustif.

Le rapport conserve donc `design_coverage=not_measured`,
`functional_correctness_of_entire_cva6=not_tested` et
`accuracy=not_measured_without_independent_exhaustive_oracle`.

L'ancienne analyse statique du décodeur (12 nœuds, 13 arêtes, 52/52 segments positionnés syntaxiquement dans ce module) reste une **mesure différente**, validée par son propre workflow slang.

## Reproduire sous Debian / WSL2

```bash
cd ~/projets/scientist_parseur
git status --short
git fetch origin
git switch feat/cva6-real-cj-oracle-pr42
git pull --ff-only
source .venv/bin/activate
source "$HOME/.local/share/rtlprep/toolchains/activate.sh"

python -m pytest -q -rs tests/test_cva6_cj_pr42.py
```

Pour refaire la simulation réelle, il faut **Verilator >= 5.036**, **cocotb 2.0.1** et le sparse checkout Git officiel **exact** sous `upstream_cva6/`. Le dossier est absent sur l'environnement WSL2 précédemment observé : les tests unitaires restent disponibles, mais la simulation réelle exige de préparer ce checkout.

```bash
python -m scripts.run_cva6_cj_oracle \
  --source-root upstream_cva6 \
  --out reports/pr42-cva6-cj-gold \
  --variant gold
```

Pour le mutant, remplacer `gold` par `mutant` et utiliser
`reports/pr42-cva6-cj-mutant` en sortie : **un code de retour 2 est attendu uniquement lorsque la mutation est effectivement détectée** ; un code 1 indique une erreur non validée.

Comme pour les PR précédentes, ne pas modifier ni supprimer le dossier local non suivi `docs/agent-reports/`.

## Étape suivante possible

Un nouveau jeu de vecteurs d'une autre branche de compression CVA6, toujours avec un oracle indépendant, un mutant négatif et le même contrôle de sources Git. La généralisation à la hiérarchie CVA6 complète reste une étape distincte nécessitant davantage de mesure de couverture.

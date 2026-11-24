# PR #43 — Oracle indépendant sur le vrai décodeur OpenHW CVA6 : C.LI

## Progrès mesurable depuis la PR #42

La #42 simulait la branche `c.j` sur les sources officielles CVA6. Pour
`c.j`, le bit `instr_i[15]` était **fixé par le code d'opération** ; enlever
son inversion était détectable, mais ne validait pas la propagation d'un
**bit variable** de l'instruction.

La #43 utilise la branche réellement présente dans le
`core/compressed_decoder.sv` **officiel** :

```systemverilog
riscv::OpcodeC1Li: begin
  // c.li -> addi rd, x0, nzimm
  instr_o = {
    {6{instr_i[12]}},
    instr_i[12],
    instr_i[6:2],
    5'b0,
    3'b0,
    instr_i[11:7],
    riscv::OpcodeOpImm
  };
end
```

L'instruction **C.LI** appartient au quadrant C1 (bits 1:0 égaux à
`01`) avec `funct3=010` (bits 15:13). Elle développe normalement
`addi rd, x0, imm`, où `imm` est l'immédiat **signé sur 6 bits**,
`imm[5]=instr_i[12]`, `imm[4:0]=instr_i[6:2]`, et
`rd=instr_i[11:7]`.

**Attention à l'ISA :** `rd=x0` désigne un code **HINT** dans la
famille des encodages C.LI, **pas une instruction C.LI ordinaire
valide**. La source CVA6 inspectée effectue néanmoins une
conversion `ADDI` et conserve ses drapeaux par défaut pour ces cas.
Le test de ces 64 encodages relève donc seulement du **comportement
de cette implémentation CVA6 à ce commit**, pas de la conformité ISA
universelle de ce traitement.

Référence externe indépendante :
[RISC-V Unprivileged ISA, extension comprimée C, C.LI]
(https://docs.riscv.org/reference/isa/v20240411/_attachments/riscv-unprivileged.pdf).
La spécification ISA sert de contrat à l'oracle pour les
**1 984 encodages `rd!=x0`**. Les HINTs sont explicitement distingués
dans les tests et les rapports.

## Vérification des octets OpenHW

Dépôt `openhwfoundation/cva6`, commit
`742dc82a0c706e0a3bfb98b709fd3ee06d50d12a`, configuration
`cv32a6_imac_sv32`. Le workflow `cva6-cli-verilator-oracle.yml`
effectue un sparse checkout et contrôle le **commit Git et les cinq
empreintes Git de blobs**, dont `core/compressed_decoder.sv` = 
`76385e5ea0b9eb0cc2d0e96fe978a90d4e122c19`.

Le vrai RTL et les quatre packages officiels sont compilés par
**Verilator 5.040** avec le wrapper d'analyse existant
`tests/fixtures/cva6/compressed_decoder_probe.sv`. Le test utilise
**cocotb 2.0.1**. Le rapport n'est pas une simulation d'une copie
recréée ou simplifiée du décodeur.

Le répertoire `upstream_cva6/` reste **intact**. Le mutant est écrit
dans `reports/pr43-cva6-cli-mutant/generated/compressed_decoder.sv`
et son empreinte SHA-256 est comparée à celle de l'original.
Après chaque exécution, la source OpenHW est de nouveau vérifiée.

## Référence indépendante

`rtlprep/cva6_cli_reference.py` est un modèle entier pur, sans
imports de slang, `bitaccess.py`, graphe ou simulateur. Il construit
l'ADDI à partir des champs du format CI :

```text
imm6 = {instr_i[12], instr_i[6:2]}
imm12 = sign_extension_12(imm6)
instr_o = (imm12 << 20) | (rd << 7) | 0x13
rs1 = x0, funct3 = 000, opcode = 0x13
```

L'oracle cocotb `rtlprep/sim_tests/cva6_cli_official.py` compare le
mot de sortie complet **32 bits** et les quatre drapeaux
`illegal_instr_o`, `is_macro_instr_o`, `is_compressed_o` et
`is_zcmt_instr_o`.

### Périmètre des 2 336 stimuli par version du circuit

| Ensemble | Nombre | Signification |
| --- | ---: | --- |
| Dirigés | 32 | 16 valeurs de champs avec 2 mots hauts |
| Exhaustif sur le demi-mot bas C.LI/HINT | **2 048** | Tous les 11 bits variables `instr_i[12:2]`, mot haut nul |
| Aléatoire reproductible sur le mot haut | **256** | Champ variable + upper16, graine `0x43C0A6` |
| **Total** | **2 336** | 3 tests cocotb, possibles répétitions |

Dans le balayage à demi-mot haut nul :

- `rd != x0` : **31 × 64 = 1 984 instructions C.LI ordinaires**.
- `rd = x0` : **64 encodages HINT**, vérifiés comme comportement
  observé de CVA6 seulement.
- `instr_i[6]`, `instr_i[12]` et `instr_i[11:7]` prennent
  chacun les valeurs possibles dans leurs positions.

**Exhaustivité limitée :** il s'agit des **2 048 demi-mots bas
de cette famille avec le mot haut nul**, pas de toutes les
possibilités 32 bits, de toutes les instructions CVA6, des états
`X/Z`, ni des configurations possibles du processeur.

## Contrôle négatif sur un **bit d'immédiat variable**

La mutation n'utilise pas un bit fixé par l'opcode.
Elle remplace **une occurrence exacte dans la branche C.LI** :

```systemverilog
// Référence OpenHW, imm[4:0] :
instr_i[6:2],

// Mutant généré hors du checkout, même largeur 5 bits :
{~instr_i[6], instr_i[5:2]},
```

Le **bit6 d'entrée** varie entre 0 et 1 sur le balayage exhaustif.
Il est normalement utilisé comme le **bit24 de l'instruction ADDI**
(`imm[4]`), et le mutant inverse précisément cette correspondance.

Si la mutation est effectivement détectée, **au moins une
assertion sur une instruction C.LI ordinaire (`class=valid_cli`,
`rd != x0`)** doit indiquer `PR43_CLI_VALUE_MISMATCH` et
**`bit24_diff=1`** dans le XML xUnit cocotb.
Un échec limité aux HINTs (`class=hint_rd_zero`), une erreur de
compilation, un faux échec générique ou un XML absent **ne valide
pas le mutant**.
Le workflow contrôle aussi l'absence d'exception du simulateur
et la différence des empreintes.

## Vérifications et limites

- Tests unitaires hermétiques du modèle, des 2 048 encodages, des
  64 HINTs, de l'extension de signe et des erreurs interdites.
- Vérification d'une **mutation unique par correspondance exacte**
  : aucun autre morceau de RTL officiel n'est modifié.
- Simulations **positive et négative** du vrai décodeur CVA6 par
  les outils EDA épinglés, avec rapports JSON et XML archivés.
- Les anciens workflows de la #42 et d'analyse slang continuent
  de tourner pour empêcher toute régression.

`design_coverage=not_measured`,
`functional_correctness_of_entire_cva6=not_tested`,
`accuracy=not_measured_without_independent_exhaustive_oracle`.

Une réussite de simulation sur une instruction valide ne démontre
ni la correction de toute la famille ISA, ni celle du décodeur
complet. Une mutation détectée est un contrôle de qualité du test,
pas une démonstration de couverture exhaustive.

## Reproduire sur WSL2 / Debian

```bash
cd ~/projets/scientist_parseur
git status --short
git fetch origin
git switch feat/cva6-real-cli-oracle-pr43
git pull --ff-only
source .venv/bin/activate
source "$HOME/.local/share/rtlprep/toolchains/activate.sh"

python -m pytest -q -rs tests/test_cva6_cli_pr43.py
```

Pour simuler le **vrai** CVA6 localement, installer
`cocotb==2.0.1` et Verilator >= 5.036, et disposer du checkout
Git `upstream_cva6` sur le commit **exact** et les cinq blobs
épinglés. Le test n'exécute aucun RTL tiers non vérifié.

```bash
python -m scripts.run_cva6_cli_oracle \
  --source-root upstream_cva6 \
  --out reports/pr43-cva6-cli-gold --variant gold
```

Le contrôle négatif utilise `--variant mutant` avec
`--out reports/pr43-cva6-cli-mutant`. Il doit sortir avec
**code 2** uniquement si la mutation a vraiment déclenché
l'assertion prévue sur le bit24 ; **code 1** signale un échec
non validé.

Ne pas supprimer ni modifier `docs/agent-reports/` non suivi.

## Suite

La PR #44 pourra enrichir le catalogue d'instructions testées
en conservant le même principe : un oracle indépendant,
un cas négatif, une version OpenHW épinglée et des limites
de couverture explicites.

# PR #38 — Accès de bits dans les processus SystemVerilog

## But et périmètre

Avant la PR #38, `rtlprep.bitaccess` ne visitait que les
`ContinuousAssign`. Des écritures comme

```systemverilog
always_ff @(posedge clk) begin
    if (enable)
        q[3:0] <= data[7:4];
end
```

étaient donc **absentes de l'index des correspondances de bits**,
même si le graphe de dépendances connaissait `q` et `data`.

La PR #38 parcourt les procédures `AlwaysFF`, `AlwaysComb`,
`AlwaysLatch`, `Always` et recherche les affectations contenant
des sélections ou concaténations. Le parcours est borné par
`MAX_PROC_DEPTH=40`, `MAX_PROC_STATEMENTS=8192`,
`MAX_PROC_GUARDS=16` et `MAX_PROC_EVENTS=16`,
en plus des budgets de l'index `bit_accesses` déjà existants.

Les blocs `Initial` sont exclus ; les instructions inconnues,
les procédures ignorées et les troncatures sont comptabilisées et
remontent dans le rapport `coverage`.

## Métadonnées produites

Les enregistrements procéduraux ajoutent aux positions de segments
existantes :

- `assignment_kind=procedural`, `procedure_kind` et `nonblocking` ;
- `guards` : suite de branches `if` ou `case` et formes des conditions
  telles qu'identifiées par slang ; **aucune valeur booléenne ni
  prédicat équivalent n'est calculé** ;
- `events` : signaux d'événement explicites résolus par leur identité
  sémantique et sens `PosEdge`/`NegEdge` ;
- `timing_scope` : par exemple `explicit_event_syntax` ou
  `implicit_not_expanded`, sans recréer des sensibilités implicites.

Le contenu `target_selection`, `source_segments`, `rhs_width` et
la classification `explicit_target_lanes`, `rhs_lanes_only`,
`partial` restent les mêmes **preuves syntaxiques bornées** que pour
une affectation continue.

**Une correspondance syntaxique `explicit_target_lanes` n'est pas
une preuve de propagation de valeurs, de maintien, de priorité des
écritures non bloquantes ou de comportement au cycle près.**

La largeur de source non justifiée, les conversions, les opérations
arithmétiques non positionnelles, les index dynamiques et les champs
`MemberAccess` sans offset restent **partiels/exclus**. Un contrôle
malformé produit `partial` avec
`reason=unsupported_procedural_context`, même si les positions des
opérandes semblent statiques.

## Validation par le vrai slang

La fixture de RTLPrep
[`tests/fixtures/procedural_bit_pr38.sv`](../tests/fixtures/procedural_bit_pr38.sv)
emploie deux processus :

- un `always_ff` avec horloge et reset, une garde `if` et
  `reg_q[3:0] <= din[7:4]` ;
- un `always_comb` avec une lecture de plage et des écritures de
  sous-plages protégées par un `case`.

La CI utilise le **binaire slang v12.1 épinglé** pour élaborer cette
source, pas un substitut Python ; les tests vérifient des positions
et métadonnées présentes dans le JSON réel. Les tests hermétiques
complémentaires couvrent les identités sémantiques erronées, les
gardes et événements inconnus, les conversions, les sélections
dynamiques et les limites de récursion.

## Vrai CVA6 : évolution des constats (et non de l'accuracy)

Le même `compressed_decoder` du vrai
`openhwfoundation/cva6`, commit
`742dc82a0c706e0a3bfb98b709fd3ee06d50d12a`,
configuration `cv32a6_imac_sv32`, est réélaboré en CI.

| Mesure observée | Avant #38 | Avec #38 |
| --- | ---: | ---: |
| Affectations inspectées par `bit_accesses` | 0 (hors périmètre) | **93** |
| Enregistrements de sélections dans `bit_accesses` | 0 | **52** |
| Correspondances syntaxiques précises | 0 | **0** |
| Enregistrements partiels | 0 | **52** |
| Avertissements du graphe | 0 | **0** |
| Nœuds / arêtes | 12 / 13 | **12 / 13** |

Ces **52 enregistrements** sont explicitement classés `partial` :
**42** `source_width_unknown`, **9**
`unsupported_rhs_Replication` et **1**
`unsupported_rhs_Conversion`. Autrement dit, cette PR **expose
52 cas précédemment ignorés**, elle ne prouve pas avoir résolu leur
correspondance bit-à-bit.

`coverage_assessment` devient `reported_limits` dans ce scénario ;
`design_coverage` reste `not_measured` et
`accuracy` reste `not_measured_without_independent_exhaustive_oracle`.
L'absence d'avertissements au niveau du graphe signal entier ne
contredit pas les limites du nouvel index de bits.

## Seconde observation externe : récepteur UART ZipCPU

Sur le véritable `rxuart.v` de `ZipCPU/wbuart32`, au blob Git
`1506e563944a2da1c1b01be6c1a953ad92fdff7d` déjà épinglé
par la validation RTL externe, la CI de non-régression observe :

- **72 affectations inspectées** par `bit_accesses` ;
- **16 enregistrements de bits**, dont **11 positionnements
  syntaxiques pris en charge** et **5 partiels**, contre 8 enregistrements
  et 1 partiel avec l'ancien périmètre ;
- **15 blocs procéduraux analysés**, **15 autres exclus**
  et **2 cibles non résolues**.

Ces statistiques reflètent seulement les formes que l'analyseur
rencontre et classe, et ne constituent **ni un taux de rappel,
ni un taux de précision, ni une preuve que 11 affectations
produisent les bonnes valeurs en simulation**.

## Reproduire sur Debian / WSL2

```bash
cd ~/projets/scientist_parseur
git fetch origin
git switch feat/procedural-bit-access-v1
git pull --ff-only
source .venv/bin/activate
source "$HOME/.local/share/rtlprep/toolchains/activate.sh"

python -m pytest -q -rs \
  tests/test_procedural_bitaccess_pr38.py \
  tests/test_bit_accesses.py \
  tests/test_member_lvalue_pr37.py \
  tests/test_cva6_compressed_decoder.py
```

Le nouveau test de fixture utilise `tests/fixtures/` et n'exige
pas de clone externe. Le test d'intégration du vrai CVA6 est ignoré
localement si `upstream_cva6` est absent, mais il tourne avec un
checkout externe dont les blobs sont vérifiés par SHA Git en CI.

Ne pas modifier les fichiers locaux non suivis
`docs/agent-reports/`.

## Après cette PR

Le prochain travail à mesurer sur de vrais RTL est la reconstruction
**justifiée** de segments de concaténations dont les largeurs sont
déjà établies par le type élaboré, et l'étude indépendante des
opérations non positionnelles et des champs `packed`.
Aucune nouvelle précision ne doit être déduite uniquement de
la présence d'une valeur `constant` dans l'AST.

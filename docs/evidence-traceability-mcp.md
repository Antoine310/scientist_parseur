# PR #25 — RTL ↔ hypothèses ↔ simulations ↔ preuves (MCP lecture seule)

## Portée

La PR #25 ajoute l'outil `rtl_evidence(signal=None, limit=20, offset=0)`.
Il assemble **des rapports JSON stockés** et les provenances AST existantes,
sans lancer slang, cocotb, Verilator, Yosys, SBY ou EQY.

La relation automatique maximale est **au niveau du design et de son
snapshot**. Une simulation passée, un banc formel prouvé ou une paire
EQY équivalente **ne prouvent jamais automatiquement une propriété
sur le signal demandé**. Cette PR n'introduit pas de matrice de preuves
par assertion, ni de signature attestant l'authenticité des rapports.

La sortie comprend :

- `top`, `signal`, `source_snapshot_status` ;
- `rtl_anchors` : localisation AST (fichier de source autorisé, ligne,
  analyseur, statut syntaxique), uniquement pour une cible **exacte** ;
- `hypotheses` : textes déclarés dans le rapport formel approuvé,
  libellés `reported_not_validated` et accompagnés de leur relation
  au snapshot, jamais supposés vérifiés ;
- `items` : au maximum trois types de validation, avec
  `available`, `relation`, `role`, `result`,
  `usable_for_current_snapshot` et `association`.
  Résultats paginés (`limit` entre 1 et 100).
- `origin=stored_reports_not_reexecuted`.

La liste contient une entrée explicite `no_report` quand aucun fichier
correspondant n'est présent, afin de **ne pas confondre « non exécuté »
et « passé »**.

## Association par empreinte

Les fichiers reconnus sont exclusivement ceux déjà autorisés par
`--reports-dir` :

| Rapport | Champs vérifiés | Critères de sortie positive |
| --- | --- | --- |
| `simulation.result.json` | `top` et `source_fingerprint` | `status=passed`, au moins 1 test, tous les tests passés, zéro échec/skip |
| `formal.result.json` | `top` et `source_fingerprint` | `status=passed` et les deux tâches `proof` / `cover` avec `status=passed` et `sby_status=PASS` |
| `equivalence.result.json` | `top_gold` / `top_gate` et `gold_fingerprint` / `gate_fingerprint` | `status=passed`, `equivalent=true`, `eqy_verdict=PASS`, au moins une partition |

Une paire EQY est reliée uniquement en tant que rôle `gold`, `gate`
ou `both_sides`. Même pour un rôle retrouvé, cela reste une validation
**de la paire RTL**, pas du comportement isolé d'un signal.

Les `relation` possibles comprennent :

- `matches_current_sources` : rapport + top + empreinte concordent et
  les sources du manifeste correspondent encore au snapshot ;
- `matches_artifacts_only` : même rapport/empreinte, mais sans manifeste
  permettant de revérifier les sources présentes ;
- `stale_current_sources` / `unavailable_current_sources` :
  les sources ont changé ou sont inaccessibles ;
- `different_artifact`, `different_top`,
  `different_design_or_role`, `unverifiable` : la relation
  n'est pas suffisamment établie ;
- `no_report` : aucune pièce de ce type n'est disponible.

`usable_for_current_snapshot=true` nécessite **à la fois** un rapport
avec les critères de résultat attendus et la relation
`matches_current_sources`. Ce booléen signifie **rapport réutilisable
pour ce snapshot**, pas résultat cryptographiquement authentifié ni
propriété prouvée sur un signal particulier.

Les sources des annotations d'AST sont restreintes aux fichiers du
manifeste lorsque fourni. Aucun chemin de log, VCD, instruction de
commande, secret ni champ libre du rapport n'est renvoyé par ce nouvel
outil. Les hypothèses sont limitées à 16 textes de 160 caractères,
et les annotations RTL à 16.

## Exemples WSL

Pour générer **plusieurs types de rapports sur le même snapshot**
du compteur (outils EDA installés localement), les exécuter dans le
même dossier autorisé :

```bash
cd ~/projets/scientist_parseur
git fetch origin
git switch feat/rtl-evidence-traceability-mcp
source .venv/bin/activate
python -m pytest -q tests/test_evidence.py

python -m rtlprep deps examples/counter/design.json --out reports/mcp-counter
python -m rtlprep simulate examples/counter/design.json --out reports/mcp-counter
python -m rtlprep formal examples/counter/design.json --out reports/mcp-counter
```

Les deux dernières commandes exigent Verilator/cocotb et SBY/Yosys/Z3
et peuvent retourner un statut non `passed` : ce statut doit rester
visible, **jamais maquillé**. Aucun de ces appels n'est réalisé par MCP.

Avant Codex, vérifier `codex mcp get rtlprep-counter` : ses options
`--graph`, `--index` et `--reports-dir` doivent toutes viser
`reports/mcp-counter`. **Redémarrer Codex** après régénération des
rapports, car le processus MCP garde le snapshot chargé au démarrage.

Mission proposée :

> Utilise uniquement `rtlprep-counter`. Appelle
> `rtl_capabilities`, `rtl_evidence()` et
> `rtl_evidence(signal="counter.count")`.
> Vérifie `source_snapshot_status=matching`, distingue les hypothèses
> déclarées, le résultat cocotb et les deux tâches SBY. Indique
> explicitement les statuts manquants, partiels ou incompatibles.
> Ne déduis **aucune preuve par signal** de rapports au niveau du design ;
> ne lis pas directement les RTL, ne relance aucun EDA et ne modifie rien.

### EQY

L'outil EQY est volontairement séparé :

```bash
python -m rtlprep eqy examples/security_csr/design.json \
  --gate examples/security_csr/refactored_design.json \
  --out reports/security-eqy
```

Un rapport EQY présent dans un autre répertoire **n'est pas chargé**
automatiquement. Pour l'inclure, l'opérateur doit choisir explicitement
le dossier de rapports autorisé approprié. Un rapport EQY qui ne
correspond pas aux empreintes et au top analysés est marqué
`different_design_or_role` au lieu d'être utilisé comme preuve.

## Limites de sécurité et scientifique

L'outil ne construit aucune nouvelle propriété, ne parse pas les VCD
et ne prétend pas que les hypothèses formelles couvrent tous les états
du circuit. Les empreintes assurent une **cohérence de contenu**,
pas une attestation de la provenance humaine ou de la CI. Un résultat
`passed` sans détails cohérents ou sans empreinte concordante reste
insuffisant pour être déclaré réutilisable sur le snapshot courant.

Les tests valident les statuts contradictoires, top/empreinte différente,
sources modifiées, rapports manquants, rôles EQY, caractères non fiables,
pagination, SDK MCP réel et vrai AST slang.

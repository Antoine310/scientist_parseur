# PR #82 — Champs locaux packed multidimensionnels

Artefact #81 15123545136, Pmp_t : typedef direct dans InstanceBody cv32e40p_cs_registers, type exact adresse + module.Pmp_t. Champ pmpaddr 512 bits offset 256, pmpcfg_packed 128 offset 128, pmpcfg 128 offset 0. Cinq sites exacts : 910–912 écritures zéro local, 1125–1126 lectures directes. Les coordonnées suivent l'ordre LSB cartésien, dernière dimension varie le plus vite. Les offsets du struct sont distincts des indices déclarés. Pas de preuve de liaison indépendante du champ (token observé uniquement), ni d'influence fonctionnelle, de priorité ou de temporalité ; constantes locales sans arêtes. Corps référencés, unions, types signés, tableaux unpacked, conversions, autres expressions refusés. Oracle officiel attendu : 640 arêtes, 768 positions constantes, 5 sites ; fixture 12/12 positions, simulation exhaustive 4096 vecteurs/12288 checks.

```bash
python -m pytest -q tests/test_local_packed_members_pr82.py
python -m pytest -q
python -m scripts.run_local_packed_members_pr82 --out reports/pr82
```

CI : référence fraîche PR80 réutilisée dans le même job, sans supprimer les étapes #80/#81. Le runner local régénère par défaut la référence. Aucun ajout au dénominateur historique. Résultats à mesurer.

## Correction après première CI

Head 3d8a06a, run [45837398777](https://github.com/Antoine310/scientist_parseur/actions/runs/45837398777) : 48/50, Python 1198/1198 local, fixture 2/4 sites et 12 arêtes, 0 constante. Artefact CI 15126866660 : slang exporte les zéros fixture en `8'd0` et `4'b0`, et ceux du cœur en `512'h0` et `128'h0`. Le moteur n'acceptait que le dernier radix. Correction bornée aux trois graphies exactes b/d/h, largeur et type identiques, tag constant éventuel concordant. Pas de modification de l'oracle, ni du RTL. Tests positifs sur chaque radix et sur dimension ascendante, refus largeur erronée, valeur non nulle, X/Z, signed, octal, graphies non canoniques et valeur non textuelle. Nouvelle validation requise.

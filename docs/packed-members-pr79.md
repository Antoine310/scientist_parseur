# PR #79 — Candidats de positions de champs packed

Le rapport expérimental reste indépendant du graphe historique. L'artefact #78 montre que les 30 sites du cœur sont dans les CSR : Status_t, Dcsr_t, Pmp_t. Les typedef de package exposent une liste ordonnée dans TypeAlias.target. L'ordre inverse des champs donne l'offset LSB ; les indices déclarés sont conservés en métadonnées. Le membre doit avoir un nom unique dans le type exact, le type d'expression identique et un token observé cohérent. Attention : la déclaration du champ n'a pas d'adresse exportée dans cette représentation, donc la liaison adresse/champ n'est pas prouvée indépendamment. Aucun addr brut publié. Ne pas confondre offset compact Status_t et position architecturale CSR.

Seules les copies directes de NamedValue ou MemberAccess simples, continues ou AlwaysComb, sont proposées ; width/state égaux, assignment type exact, aucun cast, tableau multidimensionnel, union, sélection, littéral, NBA, garde ou priorité interprétés. Pas de preuve fonctionnelle, temporelle ni de conservation globale du registre. Les autres sites restent partiels. Aucun ajout aux anciens graphes ni au 815/1199. Oracle officiel attendu : sept sites (10 candidats) ; fixture quatre sites (16 candidats) et 256 vecteurs /768 checks Verilator. Les résultats sont à mesurer.

```bash
python -m pytest -q tests/test_packed_members_pr79.py
python -m pytest -q
python -m scripts.run_packed_members_pr79 --out reports/pr79
```

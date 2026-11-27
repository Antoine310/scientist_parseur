# Concaténations vectorielles NBA (#109)

Extension séparée PR106-CONCAT-GENERAL-01, uniquement cibles concaténées historiquement refusées. Concat plate de 2–32 opérandes de chaque côté, signaux scalaires/vecteurs logic/reg descendants non signés, largeur par opérande ≤32, totale ≤64, sélections fixes ElementSelect ou RangeSelect Simple dont le type conserve exactement les bornes (correctif #108), identité exacte, destination Variable, largeur RHS/LHS/Assignment égale. NBA simple Always/AlwaysFF. Parcours LSB-first, positions déclarées, pas de fusion par nom. Détection de chevauchement exact (signal,bit) sur destination ; slices disjointes d'un même signal autorisées, répétitions source autorisées. Refus : imbriquées, constantes dans concat, conversions, indices dynamiques, alias non modélisés, états/signes/layouts ambigus, autres contextes. Pas de garantie d'absence d'alias physiques entre déclarations distinctes. Budgets 20k sites/32768 records. Réexécuter PR106 d'abord ; si couvert, compter comme existant sans nouvel enregistrement. Aucun nouvel ID plat ni promotion graphe. 

Fixture : {word_q[5:2],flag_q} <= {data[7:5],data[1:0]} et {split_q[3:2],split_q[1:0]} <= {data[4],data[7:5]}. Deux sites/9 records, oracle exact séparé. Simulation 256 entrées binaires ×3 sorties =768 assertions. Z3 20 requêtes :2 UNSAT équivalences modèles,7 UNSAT noninterférences,9 SAT sensibilités,2 SAT mutants. Modèles binaires, pas preuve RTL/temporalité. Six designs ; core 5 autres cibles (3 PR80/88,2 PR108), rxuart2 sites/6 records PR106 déjà existants, ALU/axis/encoder0. Aucun nouveau site vectoriel attendu dans les corpus réels épinglés actuels ; gain démontré sur fixture seulement, corpus externe vectoriel additionnel à prévoir. Pas de modification upstream ni de dénominateur #95. 30 tests ciblés attendus/1815 suite. Garder les dettes générales, Initial ensuite, jalon cœur #123 indicatif.

```bash
python -m pytest -q tests/test_vector_concat_nba_pr109.py
python -m pytest -q
python -m scripts.run_vector_concat_pr109 --out reports/pr109
python -m scripts.prove_vector_concat_pr109 --out reports/pr109-formal
```

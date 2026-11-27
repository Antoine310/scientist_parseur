# Cibles concaténées NBA scalaires — #106

Artefact #105 [15198817914](https://github.com/Antoine310/scientist_parseur/actions/runs/46002222588/artifacts/15198817914), rxuart AST réel : deux cibles refusées lignes179/181, Always, isNonBlocking=true, lhs Concatenation logic[2:0] de NamedValue reg ck_uart/qq_uart/q_uart. RHS ligne179 Conversion logic[2:0] de IntegerLiteral bit[2:0] value/constant 3'b0 ; ligne181 Concatenation logic[2:0] de qq_uart,q_uart,i_uart_rx (reg,reg,logic). Déclarations exactes par adresse/instance, pas par ligne. Cinq autres cibles refusées CSR (3 MemberAccess,2 NamedValue) restent distinctes.

Canal séparé : seulement sites historiquement refusés, NBA direct Always/AlwaysFF, concaténation plate de 2–32 scalaires reg/logic distincts en destination, index Variable exact, RHS concat de scalaires reg/logic ou zéro binaire exact de même largeur (conversion bit→logic autorisée uniquement pour zéro). Ordre LSB-first, coordonnées bit0 ; source/destination communes possibles comme échantillonnage RHS, alias destination refusés. Refus vecteurs, sélections, nested, inconnues X/Z littérales, changements largeur/signe, autres expressions et contextes. Ni preuve quatre états générale ni dominance/guards/horloge/reset/CDC/transition globale. Aucun ID plat inventé, aucune promotion du graphe V1/V2, aucune addition aux résidus #95–101. Budgets PR105/102, 20k sites/32768 records. 2 sites/6 records (3 échantillonnés,3 zéros) attendus chacun fixture et rxuart ; autres corpus 0 concat, 5 cibles CSR restent hors famille. Simulation fixture indépendante : 32 transitions binaires (8 états préchargés ×2 reset×2 input),128 vérifications de préparation,160 tuples vérifiés. Z3 modèle binaire séparé : 2 UNSAT équivalence modèle,3 SAT sensibilité,3 SAT mutants ; pas preuve RTL. Aucun résultat avant exécution. Les initialisations, vecteurs, concat imbriquées, et migration publique restent ouverts.

```bash
python -m pytest -q tests/test_concat_nba_pr106.py
python -m pytest -q
python -m scripts.run_concat_nba_pr106 --out reports/pr106
python -m scripts.prove_concat_nba_pr106 --out reports/pr106-formal
```

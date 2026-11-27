# PR #96 — Addition modulaire et retenues

Rapport séparé, sans modification des graphes historiques ni promotion dans CLI/MCP. Exact replay #95, union IDs historique, census racines Add après conversions (31 ALU /64 cœur attendues). Domaine initial : assignment blocking simple continu/AlwaysComb, Add direct sans conversion, deux opérandes signal/sélection packed fixe littérale, type explicite non signé logic/bit, identité exacte déclaration + type concordant, mêmes largeur et état (1–64), pas de recouvrement des opérandes. Sélection et coordonnées vérifiées par primitives #71, pas de flatten implicite, cas hors domaine explicitement refusés. Aucun gain réel annoncé avant exécution.

Pour n bits, S_i peut dépendre de A[0..i] et B[0..i] en ordre LSB de déclaration. Encodage compact deux listes de coordonnées et préfixes 1..n (n(n+1) paires potentielles, O(n) stockage). Aucun bit supérieur ne peut affecter un bit inférieur dans le modèle modulo 2^n à entrées binaires définies indépendantes. Ne pas extrapoler au X/Z, alias corrélés, gardes, priorité, valeur globale ou timing.

Validation : oracle Python indépendant par toggles exhaustifs largeur1–4 ; cas négatifs et mutant de préfixe ; fixture slang + Verilator/cocotb 256 couples 4 bits +8 cas 32 bits, oracle modulaire, 1076 paires attendues (20+1056). SMT-LIB Z3 dans job formel existant, modèle abstrait indépendant de l'extracteur : largeur4 et32, non-interférence des bits supérieurs (4+32 UNSAT), témoins de chaque paire incluse (20+1056 SAT), mutant XOR distinguable (2 SAT). Pas de preuve RTL de la fixture ni du cœur par ces requêtes, aucune généralisation aux 4 états. Logs et modèles conservés. Si solveur absent/unknown/timeout, validation non réussie. Pas de promesse sur nombre de cas RTL réel admis ; mesurer refus.

```bash
python -m pytest -q tests/test_addition_pr96.py
python -m pytest -q
python -m scripts.run_addition_pr96 --out reports/pr96
python -m scripts.prove_addition_pr96 --out reports/pr96-formal
```

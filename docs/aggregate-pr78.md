# PR #78 — Agrégats : inventaire et candidats de concaténation

Le recensement historique bit à bit exclut les cibles MemberAccess et Concatenation ; un nouveau dénominateur syntaxique est donc indispensable. Ce chantier ajoute un rapport expérimental, pas un nouveau canal du graphe. Les graphes, oracles gelés et rapports historiques restent inchangés.

Le module `rtlprep.aggregate_layout` énumère les occurrences d'affectation dans les processus et assignations continues actives, hors déclarations/initialiseurs et fonctions. Les catégories lhs_concat, lhs_member, rhs_member se recouvrent. Les sites ont un ID local au rapport, un contexte, une instance, une localisation lorsqu'elle est exportée et les types observés. Les adresses d'élaboration ne sont pas des identités persistantes. Les types longs sont explicitement marqués clippés.

Sous-périmètre de preuve positionnelle : affectation continue simple, cible concat de NamedValue de type logic ou bit non signé scalaire/vecteur unidimensionnel. Adresse et nom doivent correspondre à la déclaration de la même instance, type indexé identique au type de l'expression. Les concaténations sont parcourues du dernier opérande au premier, chaque vecteur du LSB vers le MSB (y compris bornes ascendantes). États et largeurs doivent être égaux ; toute position cible dupliquée est rejetée. Pas de conversion, membre, sélection, tableau, concat imbriquée, écriture procédurale, ni preuve de valeur, influence ou temporalité. Les limites de scan, lignes et arêtes produisent un échec explicite, jamais un faux rapport complet.

Fixture : pair_t struct packed high[2:0] et low[4:0], union packed word[7:0]/parts, lecture de champs, écriture union.word, concat de deux sorties. Oracle concat indépendant : data[7:5] vers concat_hi, data[4:0] vers concat_lo, 8 candidats. Simulation Verilator/cocotb : les 256 entrées binaires et 5 sorties par entrée (1280 vérifications), pas une preuve quatre états ni preuve de layout généralisée. Les membres restent partiels jusqu'à démonstration de leur identité et de leur offset.

```bash
python -m pytest -q tests/test_aggregate_pr78.py
python -m pytest -q
python -m scripts.run_aggregate_pr78 --out reports/pr78
```

Le dernier script requiert slang v12.1, Verilator compatible (CI 5.040), cocotb 2.0.1 et les fixtures officielles épinglées (`python scripts/rtlprep_env.py --install-rtl-fixtures`). Il génère un run unique, vérifie l'oracle fixture, le recensement ALU/cœur contre #67 et conserve les références historiques. Les statuts, compteurs, localisations et types observés doivent être consultés avant de choisir la prochaine extension. Aucun résultat officiel #78 n'est supposé à l'avance.

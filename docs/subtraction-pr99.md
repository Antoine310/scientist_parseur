# Soustraction modulaire et masque de décalage

Artefact CI #98 15186144129, rapport #95 : ALU 0 racine Subtract ; core 2 racines (IDs observés 918,1198) +5 lignes avec Subtract imbriqué. Inspection AST par groupe/localisation, jamais identité de production par ligne : exact replay commun #95–98 pour tous les candidats. Deux familles : wdata_offset = data_addr_int[1:0] - data_reg_offset_ex_i[1:0] ; imm_clip_type = (32'd1 << instr[24:20]) - 32'd1. Les cinq imbriquées restent dette. Rapport isolé ; aucun changement des graphes historiques.

Soustraction modulo 2^n, deux opérandes directs (sélections fixes prouvées), unsigned logic/bit de même largeur/état, 1–64, coordonnées disjointes, blocking continu/AlwaysComb. Le bit i dépend potentiellement des deux préfixes jusqu'à i via emprunt. Modèle indépendant binaire seulement.

Masque strictement 32 bits, décalage logique gauche par une feuille 5 bits unsigned, deux littéraux 1 prouvés (conversion unique autorisée), aucune généralisation aux autres shifts. Bit i<31 vaut (k>i). Pour le seuil t=i+1, seuls les bits d'offset j>=v2(t) peuvent traverser le seuil (v2 = nombre de zéros de poids faible de t). Bit31 constant0. 129 paires (et non 155), 37 coordonnées ; direct 2 bits 6 paires/6 coordonnées ; ensemble core2 lignes/135 paires/43 coordonnées. Union exacte avec #97/#98 66 lignes arithmétiques core, 31 ALU ; 318/67 résidus restants du census #95. Pas une couverture globale, pas de promotion.

Oracle exhaustif Python par toggles pour soustraction 1–4 et masque tous 32 k ; mutants emprunt absent et surapproximation du masque. Fixture proper subranges pour rester dans census, 16 couples 2 bits et 32 valeurs k simulées. Z3 indépendant : soustraction 2/4/32 (38 UNSAT non-interférence,1082 SAT témoins,3 SAT mutant), masque (32 UNSAT non-interférence,129 SAT témoins,1 UNSAT table entière,1 UNSAT bit31,1 SAT mutant). Total 1287 requêtes. Aucun résultat avant exécution ; preuve du modèle seulement, non équivalence RTL/4 états/temps.

```bash
python -m pytest -q tests/test_subtraction_pr99.py
python -m pytest -q
python -m scripts.run_subtraction_pr99 --out reports/pr99
python -m scripts.prove_subtraction_pr99 --out reports/pr99-formal
```

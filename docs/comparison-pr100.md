# Comparaisons d'égalité directes

Périmètre proposé après lecture de l'artefact #99 [15187058271](https://github.com/Antoine310/scientist_parseur/actions/runs/45976244510/artifacts/15187058271) : 8 racines ALU, 10 core. Quatre Equality ALU/core par octet aux indices élaborés; quatre GreaterThan ALU/core avec $signed, concaténation et AND sur le signe (refus explicites); core supplémentaire : instr_i[1:0] != 2'b11 et status_cnt_q == FIFO_DEPTH[ADDR_DEPTH:0]. Union des lignes contenant ces opérateurs : 12/155, pas un dénominateur de couverture globale.

Modèle binaire défini : pour deux vecteurs indépendants de même largeur, chaque coordonnée peut modifier le résultat scalaire d'égalité ou inégalité, avec les autres bits fixés. Pour un vecteur et une constante définie, même propriété pour chaque bit du vecteur. Pas de copie de bit. Identité de signal et coordonnées vérifiées, recouvrement refusé, largeur et état identiques pour les opérandes après élaboration, aucune conversion dynamique ; littéral borné évalué sans faire confiance au tag, ou tranche basse exacte d'un int unsigned lexical identifié (valeurs bornées par constant_indices). Pas de X/Z, signedness, ordre, appels, compositions, faisabilité ou priorité ; refus explicites. Aucun ajout aux graphes historiques, aucun changement CLI/MCP.

Oracle indépendant par toggles exhaustifs sur petites largeurs, contrôle négatif des alias, X/Z, conversions, constantes non prouvées et opérations composées. Oracle de coordonnées gelé : ALU4/8, core6/10 candidats attendus, 64/68 paires, 68/74 coordonnées; union disjointe prévue 35/72 IDs, reste 63/312. Ces chiffres sont des attentes, pas des résultats d'exécution. Fixture 2336 checks attendus, SMT QF_BV modèles 2/8/32 bits et constantes 2/3, témoins et mutants. Modèles abstraits uniquement.

```bash
python -m pytest -q tests/test_comparison_pr100.py
python -m pytest -q
python -m scripts.run_comparison_pr100 --out reports/pr100
python -m scripts.prove_comparison_pr100 --out reports/pr100-formal
```

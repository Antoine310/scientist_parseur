# PR #97 — Additions de l'arbre popcnt

Artefact CI #96 run 45970503888, artifact 15184771945 inspecté : ALU 31 racines Add toutes popcnt (16/8/4/2/1 lignes source 38/44/50/56/60) ; cœur mêmes 31 et 32 incréments CSR ligne1387, un incrément adresse ligne138. Correspondance de groupes source dans artefact, pas d'identité exacte par ligne seule. Les genvar sont sérialisées en Parameter locaux ; sélecteurs l, 2*l, 2*l+1 etc. Deux concaténations avec zéro MSB, largeur n+1. #97 cible cette famille, #98 incrément constant et composition, soustraction ensuite. Aucune modification RTL amont.

Réutilise replay/capture #95/#96 avec constantes lexicales attachées à chaque affectation, evaluate #57/#75 (Power non activé), jamais tag constant seul, résolution exacte et types/coordonnées #71. Domaine : deux opérandes concat {zéro littéral 1 bit, signal/sélection fixe n bits}, résultat n+1, largeur résultat <=64, même état unsigned logic/bit pour feuilles et résultat, pas de chevauchement des coordonnées, pas de conversion RHS ni runtime ni X/Z. Chaque sélecteur garde sa provenance. Candidats préfixes min(i+1,n), 2*sum(prefixes) paires, extension zéro sans source et retenue finale non constante. Aucun ajout au graphe historique ni au canal #96 ; rapport séparé. Oracles exacts de coordonnées sur popcnt, 31 lignes/312 paires/202 coordonnées attendues par design, 33 autres racines cœur restent partielles. Aucun gain affirmé avant tests. Deux designs séparés.

Oracle Python exhaustif n1..5 ; modèle Z3 indépendant 20 UNSAT, 100 SAT témoins, 5 SAT mutant perte retenue, pas de preuve RTL ; Verilator/cocotb sur snapshot officiel popcnt inchangé, 196 entrées avec oracle bit_count. Pas d'équivalence formelle RTL ni preuve globale, X/Z, priorité, timing, faisabilité. 
```bash
python -m pytest -q tests/test_zero_extended_addition_pr97.py
python -m pytest -q
python -m scripts.run_zero_extended_addition_pr97 --out reports/pr97
python -m scripts.prove_zero_extended_addition_pr97 --out reports/pr97-formal
```

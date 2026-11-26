# PR #84 — Setters NBA et littéraux concat

AST officiel #83 (15128720344). Ligne 1223 : pattern Status_t NBA dans AlwaysFF, toutes les entrées explicitement identifiées via tokens concordants et types exacts. Deux candidats de valeurs RHS échantillonnées, cinq constantes locales. Ce ne sont ni des copies combinatoires ni une preuve de transition globale, de garde, de priorité ou de domaine d'horloge. L'identité indépendante des déclarations de champs reste non prouvée. Fixture : maintien avant front, mise à jour après front, 32 vecteurs/65 checks. Ligne 467 : 22 bits littéraux, aucun doublon avec les sept positions #83, trois bits conditionnels non modélisés (13,14,31). Pas de pliage par tags constant seuls. Rapport distinct, aucun ajout au graphe historique. Objectif : 29 sites sur 30 au niveau candidat local et un site partiel. Résultats à mesurer.

```bash
python -m pytest -q tests/test_member_patterns_pr84.py
python -m pytest -q
python -m scripts.run_member_patterns_pr84 --out reports/pr84
```

CI réutilise la référence fraîche du job #80 et conserve toutes les validations.

# PR #85 — Constantes conditionnelles spécifiques à la configuration

Artefact #84 15128767123 : ligne 467, deux ConditionalOp (1 et 2 bits). Les paramètres FPU/ZFINX du CSR sont liés par adresse exacte aux déclarations de l'instance parente, initialisées par Conversion d'IntegerLiteral int 0. Évaluation bornée des chaînes de paramètres 0/1, type logic signed[31:0], noms/adresses et scopes exacts, valeurs de déclaration et tags éventuels concordants ; refus des références runtime et des gardes inconnues. Les deux conditions sont fausses dans cette configuration. Vérification indépendante de la branche sélectionnée : littéral converti 1'b0 ou EnumValue FS_OFF (2'b0). Pas de généralisation à FPU activé ; pas de pliage par tag seul. Oracle de partition 32 bits : 7 positions #83, 22 littéraux #84, 3 conditionnels #85. La fixture vérifie les deux configurations, refuse la branche runtime lorsque activée. Aucune preuve globale de valeur, priorité, temporalité, reachability ou identité indépendante des champs. Les résultats restent distincts des graphes historiques. 

```bash
python -m pytest -q tests/test_conditional_member_concat_pr85.py
python -m pytest -q
python -m scripts.run_conditional_member_concat_pr85 --out reports/pr85
```

CI : référence fraîche du job #80, toutes étapes précédentes conservées. Résultats à mesurer.

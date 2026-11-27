# Initialisations directes à zéro (#110)

PR105-INITIAL-01 : audit du réel AST rxuart (artefact #105 15198817914, rxuart.walker-exclusions.json et elaborated_ast.json). 15 affectations Initial directes ; 13 zéro littéral ou conversions de zéro (11 scalaires + chg_counter[27:0] + o_data[7:0] =47 bits), deux références à paramètres (ligne262 INITIAL_SETUP[29:0] et ligne298 RXU_RESET_IDLE) explicitement partielles. Identité par AST pointer/instance/déclaration exacte. Pas de généralisation aux déclarations initialisées, blocs, conditions, délais, NBA, concurrence, priorités, valeurs non nulles, X/Z, paramètres, synthèse ou état global au démarrage. Zéro défini invariant sous les conversions intégrales bornées autorisées ; type/largeur exacts sur affectation et destination ; formes AST réelles int 0 -> logic signed[31:0] -> reg[27:0], bit[0:0] 1'b0 -> reg, bit[7:0] 8'd0 -> reg[7:0]. Aucune constante permanente, aucune nouvelle arête historique, aucun nouvel ID plat. Replay #105 exact et partition nonvisited ; budgets 20k sites/32768 records, conversion ≤4, largeur ≤32. Les valeurs calculées restent des candidats locaux, pas une preuve de scheduling.

Fixture : trois Initial directes à zéro (scalaire, vecteur non zéro-based 4 bits, 8 bits), deux partielles (nonzero et param), puis mises à jour NBA ; 5 Initial/3 supportées/13 bits. Simulation fixture : 3 assertions après démarrage avant horloge, 256 entrées ×3 sorties =771 assertions. Z3 12 requêtes (4 UNSAT modèles zéro tronqué 32->1/4/8/28, 4 SAT mutants nonzero, 4 SAT témoins que l'état suivant libre peut différer ; ces derniers ne prouvent pas une transition RTL). 30 tests ciblés attendus, suite1845, six designs ; rxuart13/15,47 bits attendus, autres corpus zéro Initial recensée. Aucun gain sur cœur CV32E40P attendu. Conserver PR105-INITIAL-01 globale ouverte. #109 fusionnée, CI50/50,394 s, commit d6db176da58a722881a6f669a271779078e6debe. Branche de préparation réalignée sur main (arbre #109 identique) avant ouverture.

```bash
python -m pytest -q tests/test_initial_zero_pr110.py
python -m pytest -q
python -m scripts.run_initial_zero_pr110 --out reports/pr110
python -m scripts.prove_initial_zero_pr110 --out reports/pr110-formal
```

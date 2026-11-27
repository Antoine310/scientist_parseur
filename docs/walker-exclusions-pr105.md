# Audit P0 des décisions d'exclusion du walker (#105)

Artefact CI #104 [15199185312](https://github.com/Antoine310/scientist_parseur/actions/runs/46001134740/artifacts/15199185312), rapport rxuart.selection-census.json : 87 occurrences,16 capturées,54 sans sélection,15 non visitées,2 cibles refusées. Les 15 sites sont en contexte Initial, lignes174,175,176,197,216,236,250,262,298,408,438,461,462,487,522 ; seule ligne262 contient une sélection de plage. Les deux cibles refusées sont des concaténations lignes179/181. Le walker historique exclut explicitement les procédures hors AlwaysFF/AlwaysComb/AlwaysLatch/Always ; le filtre de cible n'accepte pas la concaténation. Le rapport #104 donne le contexte, pas encore la décision réelle.

#105 trace opt-in les arrêts effectifs : procédure exclue, instruction opaque, expression-statement non affectation, frontière de l'expression d'affectation directe. Réconciliation par identité d'objet + instance + ancêtre JSON pointer, pas par numéro de ligne ; refus des doublons et ambiguïtés, non expliqué reste explicite. Les sites non visités et les cibles refusées restent distincts. Aucun parcours nouveau par le moteur historique, aucune modification de graphe ou de CLI/MCP. Replay exact bit_accesses et bit_dependency_graph, validation du nombre de procédures exclues, budgets PR102, trace20k, profondeur pointeur128, longueur4096. Un arrêt constaté explique l'exclusion, ne démontre pas la sémantique initiale ou temporelle.

Fixture attendue : 5 occurrences dont 1 capture, 2 Initial (dont 1 sélection), 1 RepeatLoop avec sélection, 1 sans sélection. 6 designs : fixture, ALU, cœur, axis_register, priority_encoder, rxuart. Oracle indépendant PR67, pins et SHA256 conservés, attendu rxuart15 exclusions Initial et2 concaténations ; vérifier les lignes du pin sans les utiliser comme identité. Aucun gain annoncé avant exécution. La modélisation Initial, les instructions opaques, cibles concaténées et erreurs MCP restent des chantiers distincts. Pas de nouvelle simulation/formel pour cet audit syntaxique.

```bash
python -m pytest -q tests/test_walker_exclusions_pr105.py
python -m pytest -q
python -m scripts.run_walker_exclusions_pr105 --out reports/pr105
```

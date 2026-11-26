# PR #91 — Bilan scientifique #78–90

## Dénominateurs et progression (résultats historiques validés)

| Jalon | Inventaire local |
|---|---|
| #78 | 30 sites membres sur cœur, 0 ALU ; concat LHS supportée en fixture |
| #79–80 | 17 sites, 13 positions, 7 constantes |
| #81–82 | 26 sites, 653 positions, 783 constantes |
| #83–85 | 30 sites, 660 positions, 6 références, 2 NBA, 813 constantes |
| #86–87 | 56 lignes producteur, 30 occurrences, 1481 records distincts |
| #88–90 | 660 positions + 814 combinatoires + 7 NBA, trois canaux Python opt-in |

Les 3811 occurrences syntaxiques cœur, 1199 lignes plat et 30 occurrences membres ne sont pas le même dénominateur. Le minimum historique 815/1199 (531 plat +284 IDs récupérés uniques) et 381/479 ALU est recalculé par union d'IDs, sans addition des 30 membres. Les 384/98 lignes sans support lié ne constituent pas un inventaire exhaustif du RTL non compris. Histogramme par raison historique, non une preuve d'exhaustivité. Aucun recouvrement interunivers établi. 39 TP/8 TN/0 FP/FN seulement sur annotations signal historiques. 1481/1481 est une conservation de records, pas un score de précision ni une preuve fonctionnelle.

## Protocole apparié

Même AST/index frais de diagnostic, empreintes SHA256 avant/après, 3 paires par design (2–10 autorisées), processus Linux neufs, ordre baseline/all puis all/baseline. Temps mur et CPU autour du seul build, RSS high-water après build incluant chargement AST/index ; taille JSON compact ASCII trié, temps sérialisation et RSS après sérialisation mesurés distinctement. Vérification scientifique après mesure ; pas de cache forcé ni d'isolation matérielle, pas de seuil de performance arbitraire. Min/médiane/max et différences appariées, valeurs brutes, environnement et métriques publication. Empreintes déterministes sur même AST par mode, comparaison historique hors analysis_limits, source_fingerprint et nouveaux canaux. Ces tailles ne sont pas les fichiers indentés historiques. Ces RSS ne sont pas comparables directement aux pics des anciens workers. Aucune mesure de slang ni coût complet du pipeline dans ce benchmark.

## Limites et suite

Les champs restent liés conditionnellement à la sérialisation slang, pas par déclaration indépendante. Pas de preuve de priorité, gardes, événements, influence, reachability, X/Z, union générale ou multi-config. Conserver les oracles SBY/EQY/simulation antérieurs. Exposition CLI/MCP lecture seule à préparer (activation explicite, budgets, provenance et catégories distinctes), optimisation des collectes et réconciliation des expressions arithmétiques résiduelles. Les numéros historiques du backlog ne sont pas renumérotés. FUT-EVIDENCE-BRIDGE-01 demeure différé.

```bash
python -m pytest -q tests/test_member_benchmark_pr91.py
python -m pytest -q
python -m scripts.run_member_benchmark_pr91 --out reports/pr91 --repeats 3
```

Résultats à mesurer. CI conserve 50 jobs, référence fraîche partagée, aucune modification moteur.

# Comparaison d'ordre signée à contrôle partagé

Artefact #100 [15190255669](https://github.com/Antoine310/scientist_parseur/actions/runs/45981303365/artifacts/15190255669), quatre GreaterThan résiduels dans chaque design : ALU IDs 186–189, core 508–511 (locaux à cet artefact). AST réel : Call $signed, logic signed[8:0], concat logic[8:0], BinaryAnd du MSB de la tranche et du même bit cmp_signed[i], RangeSelect logic[8i+7:8i]. Vérification de l'identité par replay exact #95, pas par ligne ou nom.

Pour des entrées définies, c=0 : comparaison unsigned ; c=1 : comparaison signed. Le MSB répété n'est pas une deuxième coordonnée source ; le contrôle partagé n'est compté qu'une fois. Chaque bit des deux données et le contrôle ont un témoin de sensibilité (17 paires par octet). Refuser alias entre sources, cible et source, contrôle différent, MSB incorrect, appel non exact, largeur/signedness/état non prouvés, contexte non supporté. Périmètre borné 2–32 bits, logique quatre états interprétée seulement sur entrées binaires définies. Pas de X/Z, autres ordres ni compositions.

Oracle Python exhaustif n=2,3,4 ; fixture SV 8 bits tous 131072 triplets a,b,c ; oracle entier signé indépendant ; Z3 n=2,4,8,32 équivalence de modèle avec comparaison signed/unsigned sélectionnée, témoins de chaque source et trois mutants par largeur. Attentes : fixture1/1,17 paires,18 coordonnées ; ALU/core4/4,68 paires,72 coordonnées. Union exacte #97–101 attendue 39/76, reste59/308, univers séparés. Aucune promotion historique, pas de preuve RTL ni influence globale.

```bash
python -m pytest -q tests/test_signed_order_pr101.py
python -m pytest -q
python -m scripts.run_signed_order_pr101 --out reports/pr101
python -m scripts.prove_signed_order_pr101 --out reports/pr101-formal
```

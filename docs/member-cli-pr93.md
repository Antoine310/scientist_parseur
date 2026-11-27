# PR #93 — CLI des candidats membres

```bash
python -m rtlprep deps design.json --out reports/members --member-all
python -m rtlprep member-evidence reports/members/rtl_dependencies.json --category nba_sampled --signal cv32e40p_core.cs_registers_i.mstatus_q --limit 20
```

Options individuelles : --member-positions, --member-combinational, --member-sequential. Sans option, graphe historique inchangé. --member-all active les trois, sans fusion des catégories. deps.result.json indique les canaux publiés. La commande member-evidence lit un graphe déjà calculé, sans outil EDA ni modification du fichier ; filtrage exact source ou cible et catégorie, page max100, offset et next_offset. Un canal absent signifie non publié, pas zéro occurrence. Scope, caveat, provenance, type/coordonnées, constantes, payload original et fingerprint conservés. Lecture bornée 64 Mio, gate structure JSON, limites de records, vérifications de structure et de comptage ; ce n'est pas une authentification ni une revalidation des preuves. Pas de preuve fonctionnelle, next-state global, causalité ni couverture exhaustive. Aucun changement MCP dans cette PR ; plafond actuel 32 Mio à revoir en #94 pour graphes indentés. 

Validation : huit combinaisons d'options fixture NBA, ALU et cœur tous canaux, CLI vs API sur mêmes AST/index, graphe historique identique, pagination et oracle #90. Tests négatifs. Résultats à confirmer.

```bash
python -m pytest -q tests/test_member_cli_pr93.py
python -m pytest -q
python -m scripts.run_member_cli_pr93 --out reports/pr93
```

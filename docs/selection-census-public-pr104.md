# Publication du census V1/V2 (#104)

Le graphe historique reste V1 par défaut. Nouveau rapport séparé (schéma public 1, deux versions de census) construit depuis un dossier deps déjà produit par slang. Export explicite, pas de remplacement de fichier, SHA256 AST/index/graphe, empreinte source et top concordants, replay et projection exacts. Un identifiant de ligne est local à un AST et à sa version ; chemin JSON + instance pour la correspondance. Les empreintes identifient les octets, ne certifient ni le producteur ni les includes transitifs.

```bash
python -m rtlprep deps examples/hierarchy/design.json --out reports/census-demo
python -m rtlprep selection-census-build reports/census-demo --out reports/census-demo/selection-census.json
python -m rtlprep selection-census reports/census-demo/selection-census.json --version 1 --limit 20
python -m rtlprep selection-census reports/census-demo/selection-census.json --version 2 --classification captured --limit 20
python -m rtlprep mcp --selection-census reports/census-demo/selection-census.json
```

Le serveur MCP ajoute rtl_selection_census seulement si le fichier est explicitement sélectionné au démarrage (19 outils avec census, 18 sinon). Version obligatoire, filtres exacts classification/instance, pagination 1–100, offset>=0 ; pas de chemin fourni aux appels, aucun recalcul EDA, aucun accès en écriture. Rapport seul possible ; si index/graphe fournis, top/empreinte et SHA256 exacts exigés. Aucun rapport != rapport vide. Le snapshot conserve les octets déjà admis ; les fichiers d'entrée restent inchangés. Données non authentifiées : validation de structure, identités, partition, compteurs et assertions de non-promotion ; le chargement ne revalide pas le RTL. Limites : 16 Mio rapport,12 Mio index,64 Mio graphe, admission AST existante,20k occurrences,256 Kio JSON compact par page, refus sans troncature silencieuse. Pas de quota global CPU/RSS. Pas d'influence fonctionnelle ni couverture globale.

Validation réelle : fixture PR102 (3/1/2), ALU612/479/479, core3811/1199/1212 (AST/V1/V2), 3 modules externes épinglés déjà dans la suite indépendante : axis_register et priority_encoder (verilog-axis 48ff7a7), rxuart (wbuart32 f43a6b8), aucune modification upstream, empreintes et oracle syntaxique PR67 par occurrence, comptes externes à mesurer, non anticipés. CLI et SDK MCP stdio réels, pages et erreurs, 50 jobs historiques. Aucun nouveau modèle fonctionnel, donc pas de nouvelle simulation ou preuve Z3. Autres omissions, cinq cibles CSR, migration éventuelle du défaut V1, corpus plus larges restent des dettes séparées.

# Produits signés pleine largeur (#114)

Artefact #105 15198817914 : jointure exacte core.residuals.json et core.capture-audit.json par ID plat vers AST. Six racines Multiply : IDs805–808 (cv32e40p_mult.sv lignes266–269, quatre dot_char_mul[0..3], opérandes dot_char_op_a/b de 9 bits), IDs817–818 (lignes299–300, deux dot_short_mul[0..1], 17 bits, A du second est dot_short_op_a_1_neg direct). Conversion externe logic[2n-1:0], BinaryOp Multiply logic signed[2n-1:0], deux Conversion signées 2n de Call $signed logic signed[n-1:0] chacun sur un mot packed fixe ou NamedValue direct. Ne pas composer la négation amont. ALU zéro racine, 38 nested-only ALU/core, aucun traitement de ces compositions. 

Périmètre n=4/9/17, 2n bits résultat entier, état logic, déclaration exacte via endpoint #97/packed_coordinates.selected, mot 2D descendant à sélecteur littéral int, indices packed conservés, direct 1D, coordonnées distinctes. Refus des conversions autres que celles observées, largeurs inégales, troncatures, alias, X/Z, indices dynamiques, contextes non validés. Par sortie i, préfixe original min(i+1,n) de chaque source. Noninterférence des bits supérieurs par arithmétique modulo 2^j ; témoins de sensibilité simultanés aux sorties i>=j : basculer source de 0 à 2^j, multiplier par -1 pour j<n-1, +1 pour j=n-1 (poids négatif). Produit = -2^j, toutes les sorties i>=j passent à1. Paire distincte par affectation, 3n²+n :252 (9),884 (17), total2776 ; 280 coordonnées stockées. ALU0, fixture4/1240/136. Union indicative core94/384, ALU47/98, à recalculer. Aucun nouvel ID ni arête historique, replay exact, empreintes inchangées. 

Fixture deux produits 4 bits packed (exhaustif256 paires×2 assertions=512), produits9/17 bits 12×12 valeurs limites chacun (288 assertions), total800. 30 tests ciblés attendus /1965 suite. Z3 123 requêtes :3 UNSAT équivalences encodage extension native vs répétition MSB,54 UNSAT noninterférences préfixes,60 SAT témoins concrets simultanés (2n par largeur),6 SAT mutants (zero-extension et résultat tronqué). Les équivalences vérifient encodage de l'extension, pas deux algorithmes de multiplication indépendants ; oracle Python signé indépendant en simulation et exhaustivité des sensibilités 4 bits. Modèles binaires seulement, pas preuve RTL/temporelle. Budgets2000 lignes/32768 coordonnées ; trois designs spécialisés, 50 jobs historiques. Dette générique multiplication et compositions reste ouverte ; conversions #115 ensuite, jalon cœur #124 indicatif.

```bash
python -m pytest -q tests/test_signed_multiply_pr114.py
python -m pytest -q
python -m scripts.run_signed_multiply_pr114 --out reports/pr114
python -m scripts.prove_signed_multiply_pr114 --out reports/pr114-formal
```

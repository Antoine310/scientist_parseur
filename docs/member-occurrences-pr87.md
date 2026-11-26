# PR #87 — Identité d'occurrence locale et audit des recouvrements

Chaque producteur peut émettre un ordinal du parcours complet assignment_sites avant filtrage ; le format historique reste inchangé par défaut. Les identifiants sont locaux au même AST et à cette version du parcours, non persistants entre élaborations. Liaison fraîche, contrôle des métadonnées et du census PR79 ; jamais de rapprochement par fichier/ligne seule. Fixture réelle : deux assign sur la même ligne, deux occurrences distinctes. Groupes de doublons exacts par occurrence/catégorie/payload hors site_id ; originaux conservés. Diagnostic des recouvrements et désaccords candidats, pas une preuve fonctionnelle ; coordonnées packed et indices producteur séparés, références logiques multiples admises. Oracle core 56 lignes → 30 occurrences, 1481 records distincts, zéro doublon/recouvrement/désaccord/mixte attendu, partitions CSR et NBA vérifiées. Aucun changement graphe historique, aucun ajout au dénominateur. L'identité indépendante des champs reste ouverte. 

```bash
python -m pytest -q tests/test_member_occurrences_pr87.py
python -m pytest -q
python -m scripts.run_member_occurrences_pr87 --out reports/pr87
```

CI référence fraîche du job #80, validations précédentes conservées. Résultats à mesurer.

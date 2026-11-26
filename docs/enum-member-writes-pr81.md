# PR #81 — Écritures de constantes enum dans champs packed

Cas réels observés dans artefact #80 15115756390 : quatre affectations de PRIV_LVL_M dans dcsr_n.prv et mstatus_n.mpp. Le typedef de package est lié par token exact à l'EnumType, et l'EnumValue porte son identité propre. Le moteur vérifie nom/adresse, type, base logic unsigned descending, initializer Conversion de IntegerLiteral bit de même largeur, valeur binaire et accord des tags éventuels. Le champ conserve les limites #79 (adresse de déclaration de champ non exportée). Pas de preuve temporelle ou fonctionnelle, ni de valeur globale de registre. Aucun ajout aux graphes historiques. Candidats constants distincts des arêtes. Quatre sites/8 bits constants attendus ; fixture deux valeurs binaires différentes, deux sites/4 bits, 4 vecteurs.

```bash
python -m pytest -q tests/test_enum_member_writes_pr81.py
python -m pytest -q
python -m scripts.run_enum_member_writes_pr81 --out reports/pr81
```

CI : le job #80 conserve toutes ses étapes et appelle ensuite le runner #81 avec la référence fraîche de la même extraction, sans nouvel appel réutilisable. L'option --reference est réservée à une extraction fraîche du checkout validé ; par défaut le runner régénère la référence. Mesurer les durées et conserver les échecs.

# PR #94 — Consultation MCP des candidats membres

SDK MCP officiel 2.3.0, serveur local stdio existant. Générer le graphe explicitement :

```bash
python -m rtlprep deps design.json --out reports/members --member-all
python -m rtlprep mcp --index reports/members/rtl_index.json --graph reports/members/rtl_dependencies.json --manifest design.json
```

Le serveur attend le client MCP sur stdin ; le terminal n'est pas une interface interactive de requête. Redémarrer le client après régénération du graphe. Outil `rtl_member_evidence(category="nba_sampled", signal="cv32e40p_core.cs_registers_i.mstatus_q", limit=20, offset=0)`. Catégories identiques CLI ; signal exact source ou destination. Les six catégories ne sont pas fusionnées. Un canal absent n'est pas un zéro publié. `rtl_capabilities` annonce disponibilité, statuts et budgets. Les payloads, coordonnées, identifiants, provenance et caveats sont conservés. Statut matching/stale/unverifiable/unavailable selon manifeste et empreinte existants (pas authentification ni hash des includes transitifs). Aucun nouveau calcul, aucun chemin choisi par agent, aucune écriture, aucune commande EDA. Un signal n'est pas une preuve ; pas de liaison automatique formal/VCD.

Admission graphe 64 Mio (ancien 32 Mio, core #93 35378741 octets), lecture bornée, gate JSON 5 millions valeurs et profondeur128 ; validation structure membre. Page max100, réponse structurée JSON compact ASCII max256 Kio hors framing SDK, refus si dépassement, réduire limit ; même un enregistrement trop volumineux est refusé, jamais tronqué. Ces bornes ne sont pas un quota global mémoire/CPU ; les anciens outils gardent leurs limites propres, pas de nouveau plafond octets pour leurs réponses. Tests réels SDK stdio sur 4 snapshots frais, comparaison à query_members, empreintes entrées inchangées et anciennes intégrations préservées. Résultats à confirmer.

```bash
python -m pip install -e '.[mcp]'
python -m pytest -q tests/test_member_mcp_pr94.py
python -m pytest -q
python -m scripts.run_member_mcp_pr94 --out reports/pr94
```

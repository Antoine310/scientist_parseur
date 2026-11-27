# MJOLNIR — référence de recherche différée

**FUT-MJOLNIR-STUDY-01 · P3 — statut : identifié, non audité.**

Référence fournie par l'utilisateur, à vérifier lors de l'audit : MacDonald et al., *MJOLNIR: Finding and Reproducing Vulnerabilities in Root-of-Trust Firmware and RTL with Project-Grounded Agents*, novembre 2026, [arXiv:2611.27567v1](https://arxiv.org/abs/2611.27567v1), [dépôt](https://github.com/chipsalliance/mjolnir). Apache 2.0, Python, Google ADK, Verilator, OpenTitan : indications non encore vérifiées.

[Décision permanente #99](https://github.com/Antoine310/scientist_parseur/pull/99#issuecomment-7215409163). Étude différée phase G ; aucune copie de code, dépendance, modification des priorités ou intégration maintenant.

À étudier : navigation RTL, algorithmes, instructions des agents, modèles de menace, validation de résultats et tests, contexte, orchestration multi-agents, OpenTitan. Liens FUT-MCP-01, FUT-AGENT-01, FUT-OT-01, FUT-EVIDENCE-BRIDGE-01. Garder le moteur RTLPrep autonome, déterministe, sans LLM/API payante.

Avant réutilisation : épingler une révision, vérifier licences effectives, dépendances, provenance, compatibilité, règles PI de l'établissement, licence RTLPrep (aucun fichier LICENSE à la racine de main observé au commit 164a16e ; cela ne tranche pas le statut juridique). Respecter copyright, texte de licence, signalement des modifications, NOTICE applicable et attribution scientifique. Distinguer contributions originales et adaptations.

Clôture : audit documenté, inventaire, comparaison fonctionnelle, provenance/licences vérifiées et propositions testables. Ne pas anticiper sauf besoin technique précis.

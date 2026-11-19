# Feuille de route RTLPrep

## v0.1 : socle (cette PR)
- CLI Python : doctor, analyze, lint, synth, all.
- Manifestes de design, logs et JSON reproductibles.
- Exemple compteur 8 bits.
- Tests unitaires Python et CI sans EDA installé.

## v0.2 : navigation SystemVerilog
- Vérifier la sortie AST slang sur plusieurs exemples réels.
- Indexer hiérarchie, signaux, types et provenance fichier/ligne.
- Exposer des requêtes ciblées sur les signaux, sans demander au LLM de reconstruire l'AST.
- Tester sur un sous-module CV32E40P, pas directement sur le cœur entier.

## v0.3 : bancs de simulation
- Verilator + cocotb pour les modules de test autorisés.
- Rapports de couverture et de résultats réutilisables.
- Timeouts et sandbox systématiques.

## v0.4 : formel et PPA
- SBY/EQY, propriétés explicites et gestion des limites de preuve.
- Synthèse Yosys et mesures de surface contrôlées.
- OpenROAD seulement si les tests justifient son coût.

## v0.5 : agent
- Connecteur LLM/API/MCP optionnel et interchangeable.
- Outils en lecture / validation d'abord.
- Historique d'expériences avec budget et limite d'itérations.
- Benchmarks entre RTL brut, résumé structurel et stratégie hybride.

Ne jamais présenter un test absent comme réussi ; maintenir une chaîne totalement opérationnelle sans compte payant.

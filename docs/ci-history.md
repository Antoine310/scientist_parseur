# Historique des CI RTLPrep

Les durées murales sont création→dernière mise à jour d'un run terminé (UTC), ou fenêtre de l'ensemble des runs PR pour les anciens workflows. Somme jobs = somme started_at→completed_at, pas minutes facturées ; fenêtres spécialisées incluent les attentes entre jobs. Mesures ponctuelles, charge GitHub variable. Aucun run en cours compté comme terminé.

| PR | Événement | SHA | Run | Succès/jobs | Mural (s) | Python (s) | Fenêtre spécialisée (s) | Verdict (s) | Somme jobs (s) | Job le plus long |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---|
| 76 | PR intermédiaire | c8086e4 | 46 runs | 0/46 (32 échecs,14 annulations) | 1156 | — | — | — | — | — |
| 76 | PR intermédiaire | be3b3a0 | 46 runs | 28/46 (4 échecs,14 annulations) | 1021 | — | — | — | — | — |
| 76 | PR finale | f0a5245 | 46 PR +39 push | 46/46 PR | 1068 | — | — | — | — | — |
| 77 | PR | 331a39c | [45799218988](https://github.com/Antoine310/scientist_parseur/actions/runs/45799218988) | 47/47 | 227 | 10 | 202 | 4 | 2299 | bit-width-pr69 202 s |
| 77 | main | 4f894c0 | [45799854470](https://github.com/Antoine310/scientist_parseur/actions/runs/45799854470) | 47/47 | 351 | 22 | 306 | 3 | 3077 | bit-width-pr70 223 s |
| 78 | PR | a6c6975 | [45800487135](https://github.com/Antoine310/scientist_parseur/actions/runs/45800487135) | 48/48 | 219 | 15 | 192 | 3 | 2453 | priority-pr47 161 s |
| 78 | main | 945c19d | [45802746737](https://github.com/Antoine310/scientist_parseur/actions/runs/45802746737) | 48/48 | 237 | 12 | 212 | 3 | 2394 | constant-indices-pr57 211 s |
| 79 | PR (head actuel) | cc5c677 | [45803933566](https://github.com/Antoine310/scientist_parseur/actions/runs/45803933566) | 49/49 | 208 | 17 | 180 | 2 | 2404 | array-pr60 104 s |

#79 : 10:43:14→10:46:42 UTC, une tentative, nouveau job 103 s, pas de fusion ni validation locale confirmée. #80 empilée sur ce head ; renseigner toutes ses tentatives et les runs après retarget/fusion.

#76 : seuls trois derniers heads recensés (20 commits au total), pas historique exhaustif. 85 runs sur head final, 39 push supplémentaires. #77 et #78 : un head et une tentative chacun. #78 : nouveau job 39 s sur PR, local 16 ciblés/1125 suite 3,46 s ; ouverture→fusion 14 min 28 s, distinct de la CI. #77 : PR 10:12:56→10:16:43, main 10:16:57→10:22:48 ; #78 PR 10:20:59→10:24:38, main 10:35:27→10:39:24 (26/11/2026 UTC). Voir [commentaire permanent #78](https://github.com/Antoine310/scientist_parseur/pull/78#issuecomment-7189611119). Compléter ici chaque head et tentative des prochaines PR à la validation et au chantier suivant.

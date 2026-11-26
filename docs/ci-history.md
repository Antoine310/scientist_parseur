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
| 79 | PR finale | cc5c677 | [45803933566](https://github.com/Antoine310/scientist_parseur/actions/runs/45803933566) | 49/49 | 208 | 17 | 180 | 2 | 2404 | array-pr60 104 s |
| 80 | PR finale (base #79) | 698da07 | [45815365575](https://github.com/Antoine310/scientist_parseur/actions/runs/45815365575) | 50/50 | 179 | 21 | 143 | 4 | 2074 | bit-width-pr70 86 s |
| 79 | main | 292fb83 | [45832194530](https://github.com/Antoine310/scientist_parseur/actions/runs/45832194530) | 49/49 | 289 | 13 | 253 | 2 | 1971 | bit-width-pr70 85 s |
| 80 | main | 9b01304 | [45832255988](https://github.com/Antoine310/scientist_parseur/actions/runs/45832255988) | 50/50 | 330 | 24 | 274 | 4 | 1954 | bitwise-pr72 90 s |
| 81 | PR | fc82e3e | [45832617457](https://github.com/Antoine310/scientist_parseur/actions/runs/45832617457) | 50/50 | 237 | 11 | 210 | 2 | 2107 | packed-members-pr79 84 s |
| 81 | main | b8e79f6 | [45837014585](https://github.com/Antoine310/scientist_parseur/actions/runs/45837014585) | 50/50 | 205 | 14 | 165 | 3 | 2340 | typed-layout-pr76 108 s |
| 82 | PR intermédiaire (échec) | 3d8a06a | [45837398777](https://github.com/Antoine310/scientist_parseur/actions/runs/45837398777) | 48/50 (2 échecs) | 201 | 19 | 171 | 3 | 2360 | cva6-lane-evidence 88 s |
| 82 | PR finale | 5bb98e8 | [45838435614](https://github.com/Antoine310/scientist_parseur/actions/runs/45838435614) | 50/50 | 167 | 12 | 141 | 4 | 2075 | cva6-lane-evidence 89 s |

#82 finale : 14:22:58→14:25:45 UTC, tentative 1 sur deuxième head, job partagé 77 s, 1210/1210 local 5,63 s, oracle passed. Deux runs cumulés 368 s ; fenêtre premier départ→fin finale 535 s. Fusion 951e006, main à relever. #83 ajoute validation au même job (50 jobs attendus).

#82 : premier head 14:16:50→14:20:11 UTC, tentative 1, job partagé 82 s (échec fixture #82), verdict final échec 3 s. Local 1198/1198 en 6,40 s, rapport fixture failed (2/4 sites, 12 arêtes, 0 constante). Artefact 15126866660 : correction du format zéro, nouvelle CI réussie (voir tableau). #81 main 14:14:36→14:18:01 UTC, 50/50, job partagé 46 s.

#81 : 13:47:46→13:51:43 UTC, une tentative, job partagé #80/#81 36 s, local 1175/1175 6,21 s, fusion b8e79f6 ; [main 45837014585](https://github.com/Antoine310/scientist_parseur/actions/runs/45837014585) réussi (voir tableau). #79 main 13:45:09→13:49:58, #80 main 13:45:30→13:51:00 UTC ; chevauchement, pas de causalité déduite. #82 réutilise le même job, 50 jobs attendus.

#79 : 10:43:14→10:46:42 UTC, une tentative, nouveau job 103 s, local 1140/1140 6,90 s, fusion 292fb83 ; [main 45832194530](https://github.com/Antoine310/scientist_parseur/actions/runs/45832194530) réussi (voir tableau). #80 : 11:58:39→12:01:38 UTC, une tentative, nouveau job 36 s, local 1156/1156 5,85 s, retarget main sans nouvelle CI PR observée, arbre base identique, fusion 9b01304. Run main réussi (voir tableau). #81 : ajout au job #80 et réutilisation de son extraction fraîche, pas de nouveau workflow ; mesurer toutes les tentatives.

#76 : seuls trois derniers heads recensés (20 commits au total), pas historique exhaustif. 85 runs sur head final, 39 push supplémentaires. #77 et #78 : un head et une tentative chacun. #78 : nouveau job 39 s sur PR, local 16 ciblés/1125 suite 3,46 s ; ouverture→fusion 14 min 28 s, distinct de la CI. #77 : PR 10:12:56→10:16:43, main 10:16:57→10:22:48 ; #78 PR 10:20:59→10:24:38, main 10:35:27→10:39:24 (26/11/2026 UTC). Voir [commentaire permanent #78](https://github.com/Antoine310/scientist_parseur/pull/78#issuecomment-7189611119). Compléter ici chaque head et tentative des prochaines PR à la validation et au chantier suivant.

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
| 82 | main | 951e006 | [45840400411](https://github.com/Antoine310/scientist_parseur/actions/runs/45840400411) | 50/50 | 173 | 13 | 145 | 3 | 1942 | bitwise-pr72 82 s |
| 83 | PR | 21b7675 | [45840761119](https://github.com/Antoine310/scientist_parseur/actions/runs/45840761119) | 50/50 | 184 | 11 | 162 | 2 | 2138 | packed-coordinates-pr71 87 s |
| 83 | main | e4389dc | [45842233390](https://github.com/Antoine310/scientist_parseur/actions/runs/45842233390) | 50/50 | 182 | 10 | 145 | 2 | 2042 | rtl-security-lab 86 s |
| 84 | PR | 6401827 | [45842554660](https://github.com/Antoine310/scientist_parseur/actions/runs/45842554660) | 50/50 | 209 | 12 | 183 | 4 | 2054 | rtl-security-lab 105 s |
| 84 | main | d26fc18 | [45844465723](https://github.com/Antoine310/scientist_parseur/actions/runs/45844465723) | 50/50 | 241 | 19 | 159 | 4 | 2166 | member-writes-pr80 91 s |
| 85 | PR | 3a5077a | [45844844996](https://github.com/Antoine310/scientist_parseur/actions/runs/45844844996) | 50/50 | 195 | 11 | 170 | 3 | 2142 | typed-layout-pr76 86 s |
| 85 | main | fdba646 | [45861088191](https://github.com/Antoine310/scientist_parseur/actions/runs/45861088191) | 50/50 | 199 | 15 | 167 | 3 | 2167 | packed-coordinates-pr71 96 s |
| 86 | PR | bfc663b | [45861326731](https://github.com/Antoine310/scientist_parseur/actions/runs/45861326731) | 50/50 | 201 | 17 | 153 | 4 | 2016 | member-writes-pr80 82 s |
| 86 | main | c70d6b8 | [45874597929](https://github.com/Antoine310/scientist_parseur/actions/runs/45874597929) | 50/50 | 203 | 11 | 165 | 3 | 2279 | constant-indices-pr57 130 s |
| 87 | PR | ce4a09c | [45874841914](https://github.com/Antoine310/scientist_parseur/actions/runs/45874841914) | 50/50 | 220 | 15 | 191 | 4 | 2208 | member-writes-pr80 100 s |
| 87 | main | 2da8fba | [45880196870](https://github.com/Antoine310/scientist_parseur/actions/runs/45880196870) | 50/50 | 200 | 17 | 160 | 3 | 2223 | rtl-security-lab 88 s |
| 88 | PR | ee48ab7 | [45880493273](https://github.com/Antoine310/scientist_parseur/actions/runs/45880493273) | 50/50 | 244 | 10 | 222 | 2 | 2371 | cv32e40p-popcnt-eqy 213 s |
| 88 | main | a8da596 | [45882156720](https://github.com/Antoine310/scientist_parseur/actions/runs/45882156720) | 50/50 | 170 | 11 | 141 | 3 | 2070 | rtl-security-lab 95 s |
| 89 | PR | be59162 | [45882398138](https://github.com/Antoine310/scientist_parseur/actions/runs/45882398138) | 50/50 | 217 | 17 | 187 | 3 | 2212 | aggregate-pr78 184 s |
| 89 | main | e7048c2 | [45895349274](https://github.com/Antoine310/scientist_parseur/actions/runs/45895349274) | 50/50 | 207 | 12 | 163 | 3 | 2206 | member-writes-pr80 94 s |
| 90 | PR | fe5718c | [45895500052](https://github.com/Antoine310/scientist_parseur/actions/runs/45895500052) | 50/50 | 330 | 11 | 291 | 2 | 2241 | bitgraph-pr54 196 s |
| 90 | main | cb3cd2a | [45899905282](https://github.com/Antoine310/scientist_parseur/actions/runs/45899905282) | 50/50 | 181 | 14 | 154 | 2 | 2100 | member-writes-pr80 114 s |
| 91 | PR initial | 2f0480d | [45900116043](https://github.com/Antoine310/scientist_parseur/actions/runs/45900116043) | 50/50 | 245 | 23 | 210 | 2 | 1908 | member-writes-pr80 145 s |
| 91 | PR finale | 00daf57 | [45901030741](https://github.com/Antoine310/scientist_parseur/actions/runs/45901030741) | 50/50 | 215 | 11 | 191 | 4 | 2045 | member-writes-pr80 120 s |

#91 finale : 21:52:08→21:55:43 UTC, tentative1, partagé120 s, local1398/1398 7,70 s, RSS corrigé et scientifique passed ; deux heads cumul460 s, fenêtre714 s, aucun échec/relance. Fusion 11cd261, main à relever. #92 conserve 50 jobs attendus.

#91 initial : 21:43:49→21:47:54 UTC, tentative1, partagé145 s, local1390/1390 6,65 s, scientifique passed ; RSS identique 261420 Kio non interprétable, correction volontaire avant fusion. #90 main 21:41:54→21:44:55 UTC, partagé114 s. #91 correctif réussi (voir tableau).

#90 : 21:04:03→21:09:33 UTC, tentative 1, partagé 113 s, local 1368/1368 6,57 s, fusion cb3cd2a, main réussi (voir tableau). #89 main 21:02:46→21:06:13 UTC, partagé 94 s. #91 conserve 50 jobs attendus.

#89 : 19:16:25→19:20:02 UTC, tentative 1, partagé 68 s, local 1345/1345 6,98 s, fusion e7048c2, main réussi (voir tableau). #88 main 19:14:33→19:17:23 UTC, partagé 73 s. #90 conserve 50 jobs attendus.

#88 : 19:01:41→19:05:45 UTC, tentative 1, partagé 104 s, local 1327/1327 6,25 s, fusion a8da596, main réussi (voir tableau). #87 main 18:59:29→19:02:49 UTC, partagé 74 s. #89 conserve 50 jobs attendus.

#87 : 18:18:18→18:21:58 UTC, tentative 1, partagé 100 s, local 1311/1311 8,72 s, fusion 2da8fba, main réussi (voir tableau). #86 main 18:16:30→18:19:53 UTC, partagé 57 s. #88 conserve 50 jobs attendus.

#86 : 16:43:08→16:46:29 UTC, tentative 1, partagé 82 s, local 1295/1295 6,64 s, fusion c70d6b8, main réussi (voir tableau). #85 main 16:41:31→16:44:50 UTC, partagé 64 s. #87 conserve 50 jobs attendus.

#85 : 15:01:23→15:04:38 UTC, une tentative, partagé 63 s, local 1270/1270 6,79 s, fusion fdba646, main réussi (voir tableau). #84 main 14:59:10→15:03:11 UTC, partagé 91 s. #86 conserve 50 jobs attendus.

#84 : 14:47:34→14:51:03 UTC, une tentative, job partagé 86 s, 1250/1250 local 7,14 s ; fusion d26fc18, main réussi (voir tableau). #83 main 14:45:39→14:48:41 UTC, partagé 53 s. #85 conserve 50 jobs attendus.

#83 : 14:36:44→14:39:48 UTC, une tentative, job partagé 65 s, local 1226/1226 6,31 s, fusion e4389dc ; main réussi (voir tableau). #82 main 14:34:37→14:37:30 UTC, 50/50, job partagé 79 s. #84 conserve 50 jobs attendus.

#82 finale : 14:22:58→14:25:45 UTC, tentative 1 sur deuxième head, job partagé 77 s, 1210/1210 local 5,63 s, oracle passed. Deux runs cumulés 368 s ; fenêtre premier départ→fin finale 535 s. Fusion 951e006, main réussi (voir tableau). #83 ajoute validation au même job (50 jobs attendus).

#82 : premier head 14:16:50→14:20:11 UTC, tentative 1, job partagé 82 s (échec fixture #82), verdict final échec 3 s. Local 1198/1198 en 6,40 s, rapport fixture failed (2/4 sites, 12 arêtes, 0 constante). Artefact 15126866660 : correction du format zéro, nouvelle CI réussie (voir tableau). #81 main 14:14:36→14:18:01 UTC, 50/50, job partagé 46 s.

#81 : 13:47:46→13:51:43 UTC, une tentative, job partagé #80/#81 36 s, local 1175/1175 6,21 s, fusion b8e79f6 ; [main 45837014585](https://github.com/Antoine310/scientist_parseur/actions/runs/45837014585) réussi (voir tableau). #79 main 13:45:09→13:49:58, #80 main 13:45:30→13:51:00 UTC ; chevauchement, pas de causalité déduite. #82 réutilise le même job, 50 jobs attendus.

#79 : 10:43:14→10:46:42 UTC, une tentative, nouveau job 103 s, local 1140/1140 6,90 s, fusion 292fb83 ; [main 45832194530](https://github.com/Antoine310/scientist_parseur/actions/runs/45832194530) réussi (voir tableau). #80 : 11:58:39→12:01:38 UTC, une tentative, nouveau job 36 s, local 1156/1156 5,85 s, retarget main sans nouvelle CI PR observée, arbre base identique, fusion 9b01304. Run main réussi (voir tableau). #81 : ajout au job #80 et réutilisation de son extraction fraîche, pas de nouveau workflow ; mesurer toutes les tentatives.

#76 : seuls trois derniers heads recensés (20 commits au total), pas historique exhaustif. 85 runs sur head final, 39 push supplémentaires. #77 et #78 : un head et une tentative chacun. #78 : nouveau job 39 s sur PR, local 16 ciblés/1125 suite 3,46 s ; ouverture→fusion 14 min 28 s, distinct de la CI. #77 : PR 10:12:56→10:16:43, main 10:16:57→10:22:48 ; #78 PR 10:20:59→10:24:38, main 10:35:27→10:39:24 (26/11/2026 UTC). Voir [commentaire permanent #78](https://github.com/Antoine310/scientist_parseur/pull/78#issuecomment-7189611119). Compléter ici chaque head et tentative des prochaines PR à la validation et au chantier suivant.

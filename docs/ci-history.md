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
| 91 | main | 11cd261 | [45904603287](https://github.com/Antoine310/scientist_parseur/actions/runs/45904603287) | 50/50 | 225 | 15 | 197 | 4 | 2050 | member-writes-pr80 119 s |
| 92 | PR | 2ed2e0d | [45904793862](https://github.com/Antoine310/scientist_parseur/actions/runs/45904793862) | 50/50 | 265 | 13 | 240 | 3 | 2144 | member-writes-pr80 160 s |
| 92 | main | ea19b3e | [45963571553](https://github.com/Antoine310/scientist_parseur/actions/runs/45963571553) | 50/50 | 256 | 12 | 210 | 3 | 2065 | member-writes-pr80 155 s |
| 93 | PR | e67a6ab | [45963846881](https://github.com/Antoine310/scientist_parseur/actions/runs/45963846881) | 50/50 | 216 | 20 | 181 | 5 | 2165 | member-writes-pr80 161 s |
| 93 | main | 4bf25f9 | [45964479371](https://github.com/Antoine310/scientist_parseur/actions/runs/45964479371) | 50/50 | 251 | 14 | 187 | 4 | 2461 | member-writes-pr80 187 s |
| 94 | PR | 8aabc00 | [45964685033](https://github.com/Antoine310/scientist_parseur/actions/runs/45964685033) | 50/50 | 268 | 14 | 233 | 3 | 2487 | member-writes-pr80 196 s |
| 94 | main | 5331a85 | [45966309480](https://github.com/Antoine310/scientist_parseur/actions/runs/45966309480) | 50/50 | 224 | 19 | 192 | 4 | 2332 | member-writes-pr80 191 s |
| 95 | PR initiale | 1382878 | [45966588446](https://github.com/Antoine310/scientist_parseur/actions/runs/45966588446) | 2 échecs,48 ignorés | 21 | 12 | — | 2 | 14 | aucun spécialisé exécuté |
| 95 | PR finale | 6dd33c5 | [45967267888](https://github.com/Antoine310/scientist_parseur/actions/runs/45967267888) | 50/50 | 202 | 13 | 177 | 2 | 2326 | member-writes-pr80 176 s |
| 95 | main | 92fb24f | [45968843293](https://github.com/Antoine310/scientist_parseur/actions/runs/45968843293) | 50/50 | 217 | 18 | 186 | 2 | 2111 | member-writes-pr80 185 s |
| 96 | PR | 07d0937 | [45970503888](https://github.com/Antoine310/scientist_parseur/actions/runs/45970503888) | 50/50 | 235 | 13 | 209 | 3 | 2443 | member-writes-pr80 175 s |
| 96 | main | 519df7e | [45972213920](https://github.com/Antoine310/scientist_parseur/actions/runs/45972213920) | 50/50 | 209 | 20 | 177 | 2 | 2543 | member-writes-pr80 176 s |
| 97 | PR | c9249d3 | [45972681195](https://github.com/Antoine310/scientist_parseur/actions/runs/45972681195) | 50/50 | 230 | 17 | 200 | 3 | 2335 | member-writes-pr80 176 s |
| 97 | main | 43a8ff1 | [45973651373](https://github.com/Antoine310/scientist_parseur/actions/runs/45973651373) | 50/50 | 261 | 15 | 200 | 3 | 2403 | member-writes-pr80 199 s |
| 98 | PR initiale | bc1dfc3 | [45974019754](https://github.com/Antoine310/scientist_parseur/actions/runs/45974019754) | 48/50,2 échecs | 265 | 14 | 237 | 4 | 2340 | member-writes-pr80 167 s |
| 98 | PR finale | 371dc57 | [45974697416](https://github.com/Antoine310/scientist_parseur/actions/runs/45974697416) | 50/50 | 296 | 13 | 270 | 2 | 2193 | member-writes-pr80 203 s |
| 98 | main | 36e6ca3 | [45975861034](https://github.com/Antoine310/scientist_parseur/actions/runs/45975861034) | 50/50 | 237 | 14 | 206 | 3 | 2336 | member-writes-pr80 205 s |
| 99 | PR finale | 42ff60a | [45976244510](https://github.com/Antoine310/scientist_parseur/actions/runs/45976244510) | 50/50 | 226 | 16 | 197 | 3 | 2279 | member-writes-pr80 196 s |
| 99 | main | 164a16e | [45979353778](https://github.com/Antoine310/scientist_parseur/actions/runs/45979353778) | 50/50 | 245 | 22 | 211 | 3 | 2107 | member-writes-pr80 184 s |
| 100 | PR finale | bb2c5f2 | [45981303365](https://github.com/Antoine310/scientist_parseur/actions/runs/45981303365) | 50/50 | 255 | 15 | 227 | 2 | 2148 | member-writes-pr80 200 s |
| 100 | main | ecab557 | [45982695597](https://github.com/Antoine310/scientist_parseur/actions/runs/45982695597) | 50/50 | 216 | 16 | 182 | 2 | 2476 | member-writes-pr80 181 s |
| 101 | PR initiale | ef11507 | [45983021121](https://github.com/Antoine310/scientist_parseur/actions/runs/45983021121) | 47/50 (3 échecs) | 339 | 10 | 317 | 3 | 2151 | member-writes-pr80 240 s |
| 101 | PR finale | 1c5d268 | [45984186742](https://github.com/Antoine310/scientist_parseur/actions/runs/45984186742) | 50/50 | 253 | 15 | 225 | 4 | 2061 | member-writes-pr80 194 s |
| 101 | main | a84d885 | [45985374733](https://github.com/Antoine310/scientist_parseur/actions/runs/45985374733) | 50/50 | 269 | 13 | 244 | 3 | 2180 | member-writes-pr80 194 s |
| 102 | PR finale | 35290a8 | [45985670286](https://github.com/Antoine310/scientist_parseur/actions/runs/45985670286) | 50/50 | 321 | 14 | 290 | 5 | 2282 | member-writes-pr80 216 s |
| 102 | main | b75c9ec | [45999143379](https://github.com/Antoine310/scientist_parseur/actions/runs/45999143379) | 50/50 | 246 | 13 | 221 | 2 | 2336 | member-writes-pr80 221 s |
| 103 | PR finale | 25efa53 | [45999411060](https://github.com/Antoine310/scientist_parseur/actions/runs/45999411060) | 50/50 | 256 | 14 | 227 | 4 | 2254 | member-writes-pr80 197 s |
| 103 | main | e34bdc2 | [46000762608](https://github.com/Antoine310/scientist_parseur/actions/runs/46000762608) | 50/50 | 296 | 11 | 273 | 2 | 2282 | member-writes-pr80 232 s |
| 104 | PR finale | e622dbc | [46001134740](https://github.com/Antoine310/scientist_parseur/actions/runs/46001134740) | 50/50 | 258 | 12 | 234 | 3 | 2207 | member-writes-pr80 216 s |
| 104 | main | cfce52c | [46001942369](https://github.com/Antoine310/scientist_parseur/actions/runs/46001942369) | 50/50 | 241 | 14 | 214 | 4 | 2159 | member-writes-pr80 213 s |
| 105 | PR finale | 7819aa8 | [46002222588](https://github.com/Antoine310/scientist_parseur/actions/runs/46002222588) | 50/50 | 330 | 22 | 297 | 3 | 2207 | member-writes-pr80 219 s |
| 105 | main | 4ec7d64 | [46003055540](https://github.com/Antoine310/scientist_parseur/actions/runs/46003055540) | 50/50 | 246 | 12 | 223 | 2 | 2186 | member-writes-pr80 221 s |
| 106 | PR finale | 54ff17d | [46003318041](https://github.com/Antoine310/scientist_parseur/actions/runs/46003318041) | 50/50 | 337 | 20 | 304 | 3 | 2464 | member-writes-pr80 231 s |
| 106 | main | 04f2f51 | [46004218559](https://github.com/Antoine310/scientist_parseur/actions/runs/46004218559) | 50/50 | 362 | 24 | 315 | 3 | 2491 | member-writes-pr80 233 s |
| 107 | PR initiale annulée | 991264c | [46004556434](https://github.com/Antoine310/scientist_parseur/actions/runs/46004556434) | 40 succès/9 annulés/1 échec | 165 | 16 | 136 | 4 | 2008 | member-writes-pr80 annulé 105 s |
| 107 | PR corrigée | 7fc0569 | [46004890321](https://github.com/Antoine310/scientist_parseur/actions/runs/46004890321) | 50/50 | 363 | 15 | 311 | 3 | 2298 | member-writes-pr80 278 s |
| 107 | main | 3fe7421 | [46005890496](https://github.com/Antoine310/scientist_parseur/actions/runs/46005890496) | 50/50 | 265 | 13 | 237 | 5 | 2053 | member-writes-pr80 236 s |
| 108 | PR initiale annulée | fcb93ef | [46005993731](https://github.com/Antoine310/scientist_parseur/actions/runs/46005993731) | 37 succès/12 annulés/1 échec | 189 | 14 | 151 | 3 | 1729 | member-writes-pr80 annulé 140 s |
| 108 | PR intermédiaire annulée | f2781eb | [46006403133](https://github.com/Antoine310/scientist_parseur/actions/runs/46006403133) | 1 annulé/48 skipped/1 échec | 35 | 7 annulé | — | 3 | 9 | non exécuté |
| 108 | PR corrigée | a272b4c | [46006458773](https://github.com/Antoine310/scientist_parseur/actions/runs/46006458773) | 50/50 | 353 | 16 | 313 | 2 | 2319 | member-writes-pr80 278 s |
| 108 | main | e2a65ba | [46007356091](https://github.com/Antoine310/scientist_parseur/actions/runs/46007356091) | 50/50 | 216 | 12 | 185 | 3 | 2248 | member-writes-pr80 184 s |
| 109 | PR finale | fbb047a | [46007579883](https://github.com/Antoine310/scientist_parseur/actions/runs/46007579883) | 50/50 | 394 | 12 | 368 | 4 | 2465 | member-writes-pr80 289 s |
| 109 | main | d6db176 | [46008659658](https://github.com/Antoine310/scientist_parseur/actions/runs/46008659658) | 50/50 | 275 | 21 | 241 | 4 | 2339 | member-writes-pr80 240 s |
| 110 | PR finale | c8bd55c | [46008811902](https://github.com/Antoine310/scientist_parseur/actions/runs/46008811902) | 50/50 | 355 | 18 | 293 | 2 | 2069 | member-writes-pr80 230 s |
| 110 | main | 89f677c | [46009676138](https://github.com/Antoine310/scientist_parseur/actions/runs/46009676138) | 50/50 | 278 | 22 | 244 | 2 | 2049 | member-writes-pr80 242 s |
| 111 | PR finale | 4c88251 | [46010300159](https://github.com/Antoine310/scientist_parseur/actions/runs/46010300159) | 50/50 | 347 | 14 | 320 | 3 | 2232 | member-writes-pr80 269 s |
| 111 | main | 3645a8c | [46011169232](https://github.com/Antoine310/scientist_parseur/actions/runs/46011169232) | 50/50 | 369 | 15 | 340 | 3 | 2148 | member-writes-pr80 281 s |
| 112 | PR initiale | 3f0f7c6 | [46011686011](https://github.com/Antoine310/scientist_parseur/actions/runs/46011686011) | 2 échecs/48 skipped | 20 | 9 | — | 4 | — | non exécuté |
| 112 | PR corrigée | f4d83fb | [46012298406](https://github.com/Antoine310/scientist_parseur/actions/runs/46012298406) | 50/50 | 309 | 17 | 281 | 3 | 2381 | member-writes-pr80 255 s |
| 112 | main | 6015ecf | [46013114651](https://github.com/Antoine310/scientist_parseur/actions/runs/46013114651) | 50/50 | 380 | 21 | 344 | 4 | 2379 | member-writes-pr80 243 s |
| 113 | PR finale | 151e286 | [46013653129](https://github.com/Antoine310/scientist_parseur/actions/runs/46013653129) | 50/50 | 296 | 24 | 260 | 2 | 2393 | member-writes-pr80 232 s |
| 113 | main | bb7d0c9 | [46014474297](https://github.com/Antoine310/scientist_parseur/actions/runs/46014474297) | 50/50 | 335 | 14 | 293 | 2 | 2299 | member-writes-pr80 270 s |
| 114 | PR finale | 8b87ec2 | [46015075056](https://github.com/Antoine310/scientist_parseur/actions/runs/46015075056) | 50/50 | 302 | 16 | 274 | 3 | 2189 | member-writes-pr80 208 s |

#99 : tentative1, 09:44:38–09:48:24 UTC, head 42ff60aae36a637b9fa09d758a8a4ae2a97745b8, formel38 s ; local 22/22 ciblés 0,16 s, 1548/1548 6,76 s ; [preuve](https://github.com/Antoine310/scientist_parseur/pull/99#issuecomment-7215490068). Main tentative1 10:07:00–10:11:05 UTC, SHA 164a16e4829045b6b822ca721df926570b349747, 50/50, gate Python job 22 s (étape pytest 3 s), fenêtre spécialisée 10:07:28–10:10:59 UTC, verdict 10:11:01–10:11:04, formel35 s ; somme des durées des 50 jobs 2107 s. #98 main tentative1 09:41:53–09:45:50 UTC, formel39 s. Aucun retry ni échec signalé pour #99. #100 conserve les 50 jobs attendus.

#98 initiale : 09:28:36→09:33:01 UTC tentative1, partagé167 s échec étape27 fixture, gate échec, formel35 s réussi. Finale 09:33:27→09:38:23 UTC tentative1, partagé203 s, formel41 s, local1526/1526 6,48 s, cumul deux heads561 s fenêtre587 s sans retry/annulation. Fusion36e6ca3, main à relever. #99 conserve 50 jobs attendus.

#97 main : 09:25:54→09:30:15 UTC tentative1, partagé199 s, formel39 s. #98 initiale [45974019754](https://github.com/Antoine310/scientist_parseur/actions/runs/45974019754) terminée en échec (voir tableau) ; local20/20 ciblés,1524/1524,2659 requêtes Z3 réussies, runner failed sur census fixture, corrigé au head final.

#97 : 09:19:00→09:22:50 UTC tentative1, local1504/1504 6,48 s, partagé176 s, formel36 s, fusion43a8ff1, main réussi (voir tableau). #96 main09:15:36→09:19:05 UTC tentative1, partagé176 s, formel37 s. Aucun échec/retry. #98 conserve 50 jobs attendus.

#96 : 09:03:19→09:07:14 UTC tentative1, local1488/1488 6,89 s, partagé175 s, formel38 s, fusion519df7e, [main 45972213920](https://github.com/Antoine310/scientist_parseur/actions/runs/45972213920) réussi (voir tableau). Aucun échec/retry. #97 conserve 50 jobs attendus.

#95 finale : 08:38:44→08:42:06 UTC tentative1, local1469/1469 6,40 s, partagé176 s, deux heads cumul223 s fenêtre520 s, fusion92fb24f. Main 08:50:48→08:54:25 UTC tentative1, partagé185 s. Aucun retry. #96 conserve 50 jobs attendus.

#95 initiale : 08:33:26→08:33:47 UTC tentative1, Python et verdict en échec, 48 ignorés (timestamps non interprétables, exclus du cumul jobs exécutés 14 s), local 13/15 ciblés,1465/1467 suite ; runner réel passed, fixture incorrecte guards/events absents. Correctif validé (voir #95 finale). #94 main 08:31:16→08:35:00 UTC tentative1, 50/50, partagé191 s. Aucun retry. 

#94 : 08:18:45→08:23:13 UTC tentative1, partagé196 s, local1452/1452 6,26 s, fusion 5331a85, main réussi (voir tableau). #93 main 08:17:07→08:21:18 UTC, partagé187 s. Aucun échec/relance. #95 conserve 50 jobs attendus.

#93 : 08:12:06→08:15:42 UTC tentative1, partagé161 s, local1436/1436 4,37 s, fusion 4bf25f9, main réussi (voir tableau). #92 main 08:09:57→08:14:13 UTC, partagé155 s. Aucun échec/relance. #94 conserve 50 jobs attendus.

#92 : 22:26:20→22:30:45 UTC tentative1, partagé160 s, local1409/1409 7,74 s, fusion ea19b3e, main réussi (voir tableau). #91 main 22:24:34→22:28:19 UTC, partagé119 s. Aucun échec/relance. #93 conserve 50 jobs attendus.

#91 finale : 21:52:08→21:55:43 UTC, tentative1, partagé120 s, local1398/1398 7,70 s, RSS corrigé et scientifique passed ; deux heads cumul460 s, fenêtre714 s, aucun échec/relance. Fusion 11cd261, main réussi (voir tableau). #92 conserve 50 jobs attendus.

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

#100 finale : 10:20:43–10:24:58 UTC, tentative1, head bb2c5f2a95f358bafa107340325a98fb84049b58, formel40 s, pytest5 s, local39/39 0,11 s et1587/1587 6,47 s après correction PATH ; deux échecs EDA locaux conservés. [Preuve](https://github.com/Antoine310/scientist_parseur/pull/100#issuecomment-7215937244). Main #100 : [45982695597](https://github.com/Antoine310/scientist_parseur/actions/runs/45982695597), 50/50, tentative1, 216 s. #101 conserve 50 jobs.

#100 main : 10:30:39–10:34:15 UTC, tentative1, SHA ecab557bb5a8bdbfbcc409f88175a9e70f7a7b8a, 50/50, formel41 s. #101 initiale : 10:32:56–10:38:35 UTC, tentative1, head ef11507e8058379f0035188b9da73a22ad2399d1, 47/50, formel44 s et étape PR101 Z3 réussie ; bitwise-pr72 curl HTTP403 sur slang, member-writes-pr80 fixture 0 résidu, verdict final échec. Local 22/22 en0,10 s,1609/1609 en7,27 s, fixture échec, simulation/formel non atteints. Artefact 15189859595 : omission historique Call.arguments ; correction fixture, dette PR101-CAPTURE-01. Ne pas effacer les rapports ni les tentatives.

#101 finale : 10:41:16–10:45:29 UTC, tentative1, head 1c5d2688776746607859c9d028767e4417634951, formel40 s, pytest5 s, étapes PR101 6 s/1 s, local22/22 0,09 s et1609/1609 7,12 s, simulation131072, Z3 112 ; deux heads cumul592 s, fenêtre753 s. [Preuve](https://github.com/Antoine310/scientist_parseur/pull/101#issuecomment-7216325288). Fusion a84d885, main [45985374733](https://github.com/Antoine310/scientist_parseur/actions/runs/45985374733) à relever après achèvement. #102 conserve 50 jobs.

#101 main : 10:49:46–10:54:15 UTC, tentative1,50/50, formel37 s. #102 finale : 10:51:54–10:57:15 UTC, tentative1, head 35290a8632a6d47547ba0e9ea11e8926be78a433, formel36 s, étape PR102 2 s, local21/21 0,12 s et1630/1630 6,96 s, audit exact. [Preuve](https://github.com/Antoine310/scientist_parseur/pull/102#issuecomment-7218313125). Fusion b75c9ec, main [45999143379](https://github.com/Antoine310/scientist_parseur/actions/runs/45999143379) à relever après achèvement. #103 conserve 50 jobs.

#102 main : 12:30:04–12:34:10 UTC, tentative1,50/50, formel35 s. #103 finale : 12:31:52–12:36:08 UTC, tentative1, head 25efa5372b642de2e285c45628cdd12468168efc, formel35 s, étape PR103 3 s, local25/25 0,10 s et1655/1655 6,92 s, projection exacte. [Preuve](https://github.com/Antoine310/scientist_parseur/pull/103#issuecomment-7218489812). Fusion e34bdc2, main [46000762608](https://github.com/Antoine310/scientist_parseur/actions/runs/46000762608) à relever après achèvement. #104 conserve 50 jobs.

#103 main : 12:41:34–12:46:30 UTC, tentative1,50/50, formel39 s. #104 finale : 12:44:12–12:48:30 UTC, tentative1, head e622dbc3faa91f81b43c8396b631c8f2e43449e2, formel38 s, étape PR104 12 s, local29/29 0,21 s et1684/1684 7,34 s, 6 cas,43 pages,24 refus attendus. [Preuve](https://github.com/Antoine310/scientist_parseur/pull/104#issuecomment-7218707415). Fusion cfce52c, main [46001942369](https://github.com/Antoine310/scientist_parseur/actions/runs/46001942369) à relever après achèvement. #105 conserve 50 jobs.

#104 main : 12:49:59–12:54:00 UTC, tentative1,50/50, formel40 s. #105 finale : 12:52:01–12:57:31 UTC, tentative1, head 7819aa8bce55f5e585e1b987fe7a2a3af971b643, formel31 s, étape PR105 2 s, local19/19 0,12 s et1703/1703 7,27 s, six cas, 0 inexpliquée. [Preuve](https://github.com/Antoine310/scientist_parseur/pull/105#issuecomment-7218894883). Fusion 4ec7d64, main [46003055540](https://github.com/Antoine310/scientist_parseur/actions/runs/46003055540) à relever après achèvement. #106 conserve 50 jobs.

#105 main : 12:58:11–13:02:17 UTC, tentative1,50/50, formel36 s. #106 finale : 13:00:08–13:05:45 UTC, tentative1, head 54ff17d1827b415dd275030c3b155e7b47816516, formel44 s, étape PR106 4 s, local28/28 0,09 s et1731/1731 7,04 s, fixture160 tuples/8 Z3 modèle. [Preuve](https://github.com/Antoine310/scientist_parseur/pull/106#issuecomment-7219057869). Fusion 04f2f51, main [46004218559](https://github.com/Antoine310/scientist_parseur/actions/runs/46004218559) à relever après achèvement. #107 conserve 50 jobs.

#106 main : 13:06:16–13:12:18 UTC, tentative1,50/50, formel39 s. #107 initiale : 13:08:38–13:11:23 UTC, tentative1, annulée, formel31 s, étape PR107 skipped, échec du verdict final. Local initial1750/1750 puis top erroné ; corrigé20/20,1751/1751,6 cas. [Preuve](https://github.com/Antoine310/scientist_parseur/pull/107#issuecomment-7219231710). CI corrigée [46004890321](https://github.com/Antoine310/scientist_parseur/actions/runs/46004890321) : 13:10:57–13:17:00 UTC, tentative1,50/50,363 s, formel45 s, étape PR107 4 s ; somme2298 s, non murale/non facturée. Artefact15200552325 ; [verdict](https://github.com/Antoine310/scientist_parseur/pull/107#issuecomment-7219299483). Fusion 3fe7421eee587fd3669bfa7b603832fc807c7aa0, main [46005890496](https://github.com/Antoine310/scientist_parseur/actions/runs/46005890496) à relever. #108 conserve 50 jobs.

#107 main :13:17:53–13:22:18 UTC, tentative1,50/50, formel48 s. #108 initiale13:18:36–13:21:45, formel44 s, PR108 simulation skipped, Z3 success ; intermédiaire13:21:26–13:22:01 ; finale13:21:49–13:27:42 UTC, tentative1,50/50, formel42 s, étape PR108 simulation6 s, Z3 <1 s arrondi0, local34/34 0,20 s,1785/1785 6,89 s,768 tuples et43 modèles. [Verdict](https://github.com/Antoine310/scientist_parseur/pull/108#issuecomment-7219510930). Fusion e2a65ba1d1a8b15e26619d75663637d1669b4633, main [46007356091](https://github.com/Antoine310/scientist_parseur/actions/runs/46007356091) à relever. #109 conserve50 jobs.

#108 main :13:28:07–13:31:43 UTC, tentative1,50/50, formel41 s. #109 finale13:29:46–13:36:20 UTC, tentative1,50/50, head fbb047a6be1a1cb2f836a00c29f61e0fc279fd8d, formel44 s, étape PR109 simulation5 s, Z3 <1 s arrondi0 ; local30/30 0,23 s,1815/1815 7,14 s,768 assertions/20 Z3 modèle. Somme jobs non murale/non facturée. Artefacts15202329074/15200784680, [verdict](https://github.com/Antoine310/scientist_parseur/pull/109#issuecomment-7219716884). Fusion d6db176da58a722881a6f669a271779078e6debe, CI main à relever. #110 conserve50 jobs.

#109 main13:37:02–13:41:37 UTC, tentative1,50/50, formel49 s. #110 finale13:38:06–13:44:01 UTC, tentative1,50/50,355 s, formel43 s, étape PR110 4 s, Z3 <1 s arrondi0, local30/30 0,18 s,1845/1845 7,16 s,771 assertions/12 modèles. Artefacts15204070536/15201999973, [verdict](https://github.com/Antoine310/scientist_parseur/pull/110#issuecomment-7219932050). Fusion opérateur 89f677c3e095d02e54b59fac575b0199fbceaef9, main [46009676138](https://github.com/Antoine310/scientist_parseur/actions/runs/46009676138) à relever. #111 conserve50 jobs.

#110 main13:44:15–13:48:53 UTC, tentative1,50/50, formel36 s. #111 finale13:48:34–13:54:21 UTC, tentative1,50/50,347 s, formel33 s, étape PR111 3 s, Z3 <1 s arrondi0 ; local30/30 0,33 s,1875/1875 8,09 s,1536 assertions/60 modèles. Artefacts15203393162/15203831763, [verdict](https://github.com/Antoine310/scientist_parseur/pull/111#issuecomment-7220131694). Fusion opérateur 3645a8c4ac74ceffd028bff80f7af104e077f5cc, main [46011169232](https://github.com/Antoine310/scientist_parseur/actions/runs/46011169232) à relever. #112 conserve50 jobs.

#111 main13:54:36–14:00:45 UTC, tentative1,50/50, formel33 s. #112 initiale13:58:15–13:58:35 UTC, tentative1,29/30 local SyntaxError ; corrigée14:02:23–14:07:32 UTC, tentative1,50/50, formel46 s, étape PR112 3 s, Z3 <1 s arrondi0, local30/30 0,17 s,1905/1905 7,42 s,32768 assertions/10 modèles. Artefacts15205235098/15203064492, [verdict](https://github.com/Antoine310/scientist_parseur/pull/112#issuecomment-7220417875). Fusion opérateur 6015ecf35da85e5c141d33da8129c7a9306f1e7f, main [46013114651](https://github.com/Antoine310/scientist_parseur/actions/runs/46013114651) à relever. #113 conserve50 jobs.

#112 main14:07:47–14:14:07 UTC, tentative1,50/50, formel43 s. #113 finale14:11:25–14:16:21 UTC, tentative1,50/50,296 s, formel48 s, étape PR113 2 s, Z3 <1 s arrondi0, local30/30 0,18 s,1935/1935 7,63 s,8192 assertions/469 modèles. Artefacts15205611277/15206090433, [verdict](https://github.com/Antoine310/scientist_parseur/pull/113#issuecomment-7220606930). Fusion opérateur bb7d0c98b3804809d0d1ea7e82e2b0333740830f, CI main à relever. #114 conserve50 jobs.

#113 main14:16:46–14:22:21 UTC, tentative1,50/50, formel41 s. #114 finale14:20:41–14:25:43 UTC, tentative1,50/50,302 s, formel44 s, étape PR114 2 s, Z3 1 s ; local30/30 0,19 s,1965/1965 7,55 s,800 assertions/123 modèles. Artefacts15205932538/15206286747, [verdict](https://github.com/Antoine310/scientist_parseur/pull/114#issuecomment-7220812727). Fusion opérateur 1254826e67d5c4da8853d1e979876be4c335687d, CI main à relever. #115 conserve50 jobs.

#114 main [46015875762](https://github.com/Antoine310/scientist_parseur/actions/runs/46015875762) 50/50, 290 s selon transmission, jobs intégralement vérifiés à la reprise. #115 finale [46016614971](https://github.com/Antoine310/scientist_parseur/actions/runs/46016614971) head 0a08990fa8bb3f4f97ec0df44f2088e235310c40, 14:30:55–14:36:20 UTC, 50/50,325 s, Python16 s, partagé261 s, formel39 s. Local30/30 (0,19 s),1995/1995 (7,52 s),48 assertions,38 modèles ; SHA local absent de l'extrait. [Archivage](https://github.com/Antoine310/scientist_parseur/pull/115#issuecomment-7221307450). Main 91d705f573181079f4f0cff484a3ca0a6d802860, [46019497533](https://github.com/Antoine310/scientist_parseur/actions/runs/46019497533),14:50:19–14:56:38 UTC,50/50,379 s, Python20 s, partagé329 s, formel44 s. #116 conserve50 jobs.

#116 finale [46021175475](https://github.com/Antoine310/scientist_parseur/actions/runs/46021175475), head 8396184a1b50eba1cf639d5356ff8b784fe84a37, 15:01:39–15:07:37 UTC,50/50,358 s, Python14 s, partagé253 s, formel52 s. Local30/30 (0,13 s),2025/2025 (7,75 s),768 checks,8 modèles, SHA conforme. [Archivage](https://github.com/Antoine310/scientist_parseur/pull/116#issuecomment-7221658679). Main fc6be0b2dcc1be06ed1f9c9b353fa1020790f68f, [46022325474](https://github.com/Antoine310/scientist_parseur/actions/runs/46022325474),15:09:16–15:14:05 UTC,50/50,289 s, Python16 s, partagé259 s, formel47 s. #117 conserve50 jobs.

#117 première CI [46040780404](https://github.com/Antoine310/scientist_parseur/actions/runs/46040780404) head 3eb4f27c1b4321ce446fe126ab72f2e764b1cb14 : 48/50 réussis, member-writes et verdict final échec, artefact 15221060390. Local 2054/2054 en 5,42 s, oracle fixture échoué (1/5 racines), simulation/Z3 non atteints localement. Correction des tags enum et nouveau head à valider.

#117 second CI [46042051944](https://github.com/Antoine310/scientist_parseur/actions/runs/46042051944), head 88a4c27be4017c4ec51a8da5daf9d34d6601195b, 48/50, member-writes and global verdict failure. Artifact 15220187972 fixture counts now exact 5/5,14 values,2 pairs; KeyError 'items' in independent oracle. Restore detailed rows, add two report contract regressions. No new local execution log supplied. New head pending.

#117 finale [46048820784](https://github.com/Antoine310/scientist_parseur/actions/runs/46048820784), head b5e6e5a450e4a047f926d41949b721ca19993de7, 50/50,411 s, Python13 s, partagé320 s, formel44 s. Local36/36 (0,16 s),2061/2061 (7,92 s),768 checks,30 Z3, SHA exact. [Archivage](https://github.com/Antoine310/scientist_parseur/pull/117#issuecomment-7225563300). Main bef7404312ca5f4e71d151493fc3f34e3f124ebe [46050228332](https://github.com/Antoine310/scientist_parseur/actions/runs/46050228332),50/50,422 s, Python16 s, partagé319 s, formel42 s. #118 conserve50 jobs.

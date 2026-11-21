# PR #15 — Interroger RTLPrep depuis Codex grâce au protocole MCP

> **Premier jalon de la phase F.** Un serveur local MCP permet à Codex ou
> à tout client MCP compatible de lire les **résultats réellement déjà
> produits** par RTLPrep. Le serveur ne lance aucun simulateur, aucune
> compilation, aucune vérification formelle et **ne modifie aucun fichier**.
> Son objectif est d'apporter des *données vérifiables* à un agent.

## 1. Architecture : Codex consulte, RTLPrep produit les preuves

```text
                    (phase de préparation explicite)
   SystemVerilog ──► slang ──► rtl_index.json + rtl_dependencies.json
                   Verilator ─► simulation.result.json
                   SBY/EQY ───► formal.result.json / equivalence.result.json

                       (consultation)
   Codex ou client MCP ── stdio ──► RTLPrep MCP en lecture seule
                                       │
                                       ├─ Modules, instances et ports
                                       ├─ Signaux et provenance
                                       ├─ fan-in / fan-out bornés
                                       ├─ Avertissements du graphe
                                       └─ Statuts de validation déjà enregistrés
```

**La compilation et les tests sont séparés de l'interface MCP.**
C'est une décision de sécurité : le contenu d'un fichier RTL, d'un
rapport, d'un commentaire ou d'une réponse d'un modèle de langage
ne devient jamais une autorisation d'exécuter une commande EDA.

L'intégration repose sur le **SDK officiel Python MCP v2.3.0**
(`mcp.server.MCPServer`) et le transport local **stdio**. Nous
ne réinventons ni le protocole ni le système de validation de schéma.

## 2. Installer les dépendances (Python 3.11+)

Dans un environnement Python **3.11 ou plus récent** :

```bash
python -m pip install -e '.[dev,mcp]'
python -c 'from mcp.server import MCPServer; print("MCP disponible")'
```

Le SDK MCP est **facultatif** : les autres commandes RTLPrep
restent utilisables sur les environnements sans ce paquet.
Aucune clé API ni aucun compte LLM n'est requis pour que
le serveur fournisse les rapports locaux.

Référence du SDK :
[serveurs Python MCP v2](https://py.sdk.modelcontextprotocol.io/)
et [transport stdio](https://py.sdk.modelcontextprotocol.io/run/).

## 3. Produire les artefacts avec le vrai compilateur

Avec slang v12.1 installé :

```bash
python -m rtlprep deps examples/hierarchy/design.json \
    --out reports/hierarchy
```

La commande `deps` produit notamment :

```text
reports/hierarchy/
├── rtl_index.json
├── rtl_dependencies.json
├── index.result.json
├── analyze.result.json
└── deps.result.json
```

Les fichiers source sont spécifiés par
`examples/hierarchy/design.json` et sont soumis aux
mêmes règles d'autorisation que la commande
`rtlprep source`.

Cette étape est exécutée **hors MCP**, à l'initiative de
la personne responsable du projet. Elle peut être lourde
sur des designs complexes.

## 4. Démarrer le serveur MCP en mode local

```bash
python -m rtlprep mcp \
  --index reports/hierarchy/rtl_index.json \
  --graph reports/hierarchy/rtl_dependencies.json \
  --manifest examples/hierarchy/design.json \
  --reports-dir reports/hierarchy
```

Cette commande ne doit **rien afficher** : elle attend
sur **stdin** les messages MCP, et réserve **stdout**
aux réponses du protocole. C'est normal.

Les quatre chemins sont fixés **au démarrage**.
Il est possible d'en omettre certains : les outils
qui en dépendent renverront une erreur. Au moins
`--index`, `--graph` ou `--reports-dir` est requis.

**Important :** le serveur conserve un **snapshot**
des fichiers JSON chargés au démarrage.
Pour consulter un nouveau résultat d'EDA, il faut
régénérer les rapports **puis redémarrer le serveur**.
Le code SystemVerilog demandé par `rtl_source`
est lu uniquement depuis les sources du manifeste.

## 5. Le connecter à Codex

La CLI Codex prend en charge les serveurs locaux MCP
avec `codex mcp add`. À partir d'un environnement
dans lequel RTLPrep est installé, **utiliser des chemins absolus**
pour que la commande fonctionne même si Codex est lancé
depuis un autre dossier :

```bash
codex mcp add rtlprep -- \
  /CHEMIN/ABSOLU/.venv/bin/python -m rtlprep mcp \
  --index /CHEMIN/ABSOLU/reports/hierarchy/rtl_index.json \
  --graph /CHEMIN/ABSOLU/reports/hierarchy/rtl_dependencies.json \
  --manifest /CHEMIN/ABSOLU/examples/hierarchy/design.json \
  --reports-dir /CHEMIN/ABSOLU/reports/hierarchy

codex mcp list
```

**Adapter** les chemins à votre machine ; ils sont
des exemples, pas des chemins qui existent chez vous.
Si Python est installé globalement, utiliser son
chemin absolu plutôt que `.venv/bin/python`.

L'alternative est de déclarer le serveur dans
`~/.codex/config.toml` :

```toml
[mcp_servers.rtlprep]
command = "/CHEMIN/ABSOLU/.venv/bin/python"
args = [
  "-m", "rtlprep", "mcp",
  "--index", "/CHEMIN/ABSOLU/reports/hierarchy/rtl_index.json",
  "--graph", "/CHEMIN/ABSOLU/reports/hierarchy/rtl_dependencies.json",
  "--manifest", "/CHEMIN/ABSOLU/examples/hierarchy/design.json",
  "--reports-dir", "/CHEMIN/ABSOLU/reports/hierarchy",
]
```

Documentation de Codex :
[configuration MCP officielle](https://learn.chatgpt.com/docs/extend/mcp).

**Cette PR teste un véritable client MCP officiel en CI**, mais
n'installe **pas** de configuration Codex dans votre compte
ou votre machine. La connexion effective à Codex exige
votre installation explicite.

## 6. Les onze outils disponibles

| Outil MCP | Contenu / résultat |
| --- | --- |
| `rtl_capabilities` | Top, artefacts configurés, limites et mode lecture seule |
| `rtl_modules` | Liste paginée des définitions de modules |
| `rtl_instances` | Liste paginée des chemins d'instances |
| `rtl_module` | Module demandé et occurrences paginées |
| `rtl_instance` | Ports et provenance d'une instance |
| `rtl_signal` | Informations sur une déclaration et ses ports |
| `rtl_find_signals` | Recherche paginée, insensible à la casse, dans les noms de signaux et ports (1–80 caractères) |
| `rtl_trace` | Chemins `fanin` / `fanout` bornés |
| `rtl_warnings` | Avertissements du graphe, paginés |
| `rtl_source` | Quelques lignes de source **autorisé** |
| `rtl_validations` | Statuts provenant de rapports préexistants |

Ces outils délèguent aux fonctions Python qui existaient
déjà : `list_modules()`, `get_instance()`,
`get_signal_info()`, `trace_dependencies()`,
`get_source_context()`, etc. Nous ne fabriquons pas
de dépendances à partir de noms similaires ou
de conclusions proposées par un modèle.

Par exemple, Codex pourrait demander :

> « Sur le module `hierarchy_top`, montre-moi les occurrences
> de `leaf` et les dépendances possibles de `status`.
> Donne les avertissements et les fichiers RTL correspondant
> aux informations disponibles. »

Les outils renverront les données enregistrées,
avec la provenance lorsque slang l'a fournie.
Un chemin de dépendance du graphe n'est **pas**
une preuve de causalité à l'exécution.

## 7. Contrats de lecture et sécurité

### 7.1 Aucun accès libre au système de fichiers

La liste des rapports est fixée **par un répertoire choisi
au démarrage** et une liste stricte de noms de rapports
RTLPrep, comme `formal.result.json` ou
`simulation.result.json`.

L'argument `filename` de `rtl_source` est limité
au **nom d'un fichier source du manifeste**. Un appel
`rtl_source(filename="../.git/config", ...)`
est explicitement rejeté, tout comme `/etc/passwd`
et les autres chemins arbitraires.

L'opérateur qui lance le serveur doit néanmoins
choisir des manifestes et des rapports **de confiance** :
l'agent n'est pas autorisé à sélectionner à sa place
des chemins supplémentaires.

### 7.2 Limites de taille et pagination

- Index JSON : jusqu'à **12 Mio**.
- Graphe JSON : jusqu'à **32 Mio**.
- Rapport JSON individuel : jusqu'à **1 Mio**.
- Liste paginée : **1 à 100 éléments** par requête.
- `rtl_trace` : profondeur **0 à 6**, au plus **100 arêtes**.
- Extrait de source : rayon **0 à 10 lignes**.
- Les avertissements ne sont pas recopiés **en bloc**
  dans chaque `rtl_trace` : un compteur est fourni,
  puis `rtl_warnings` permet de les lire par pages.

Ces valeurs sont volontairement basses pour un premier
serveur local et doivent être réévaluées sur de gros SoC.

### 7.3 Résultats de validation ≠ preuve nouvelle

`rtl_validations` retourne uniquement les champs pertinents
des rapports existants, avec un marqueur explicite :

```json
{
  "origin": "stored_report_not_reexecuted"
}
```

Un rapport contenant `"status": "passed"` est
**le résultat historique d'une exécution antérieure**.
Cela ne signifie ni que la source courante a été
réexécutée, ni qu'un CPU entier est correct.

Si `rtl_capabilities` ou `rtl_warnings` rapporte
des avertissements, ils doivent être présentés,
et non supprimés de la réponse par un agent.

### 7.4 Empreintes et fraîcheur des sources (PR #18)

À l'ouverture, le serveur rejette désormais deux artefacts `rtl_index.json`
et `rtl_dependencies.json` ayant des `source_fingerprint` contradictoires.
Quand un manifeste est fourni, `rtl_capabilities.source_snapshot_status`
compare l'empreinte des sources **actuellement déclarées** à celle
des artefacts. Valeurs : `matching`, `stale`, `unavailable` ou
`unverifiable`. Ce contrôle est recalculé quand l'agent consulte les
capacités, une trace, ou demande un extrait.

Si l'empreinte a changé depuis la génération du graphe, `rtl_source`
refuse de lire un extrait qui risquerait d'être associé à un graphe périmé.
`rtl_validations[].source_relation` distingue `matches_current_sources`,
`stale_current_sources`, `different_artifact`,
`matches_artifacts_only` et `unverifiable`.
L'absence d'empreinte est explicitement **inconclusive**, jamais un accord
implicite. Même `matching` ne remplace pas une preuve : les en-têtes
`include` transitifs non déclarés ne sont pas tous incorporés dans
l'empreinte actuelle, et une CI compromise pourrait produire un rapport
mensonger. Le MCP reste un snapshot et nécessite un redémarrage après
régénération des fichiers.

La recherche `rtl_find_signals(query, limit=20, offset=0)` retourne des
noms de signaux/ports et leur provenance lorsqu'elle est connue. Elle
ne cherche ni les affectations ni les expressions logiques. Les résultats
sont paginés et ne constituent pas une découverte de vulnérabilité.

### 7.5 Limites de sécurité encore ouvertes

Ce MVP ne propose que le transport **stdio local** :
pas de serveur HTTP accessible au réseau ni d'authentification
à développer pour un service distant.

Il n'offre pas une **sandbox multi-utilisateurs**
ni une protection complète contre des fichiers locaux
malveillants ou des compromis du processus hôte.
**Ne pas** l'utiliser pour servir un projet confidentiel
à un client non autorisé.

## 8. Tester le protocole réel (pas un faux client)

La CI installe le **SDK officiel MCP 2.3.0**, puis
le vrai compilateur **slang 12.1**. Elle génère les fichiers
d'index et de graphe de l'exemple hiérarchique.

Ensuite, le script
[`scripts/test_mcp_stdio.py`](../scripts/test_mcp_stdio.py)
lance **`python -m rtlprep mcp` comme sous-processus**,
connecte le client officiel `mcp.Client` via **stdio**,
puis vérifie :

- la découverte des **11 outils** avec `tools/list` ;
- les appels réels `tools/call` ;
- les modules, instances, ports, signal et fan-in ;
- l'extraction d'une ligne RTL autorisée ;
- la lecture des rapports, sans faux résultat récent ;
- le refus des tentatives de traversal de chemin ;
- le rejet des limites déraisonnables de pagination
  ou de profondeur.

Les tests unitaires
[`tests/test_mcp_data.py`](../tests/test_mcp_data.py)
vérifient aussi les règles d'accès **sans installer
MCP ni les exécutables EDA**.

Le workflow dédié se trouve dans
[`.github/workflows/mcp-stdio.yml`](../.github/workflows/mcp-stdio.yml).

## 9. Premier test Codex sous Debian WSL

Un parcours de connexion pas à pas, avec environnement virtuel Python,
vrai slang, lancement des artefacts et commandes `codex mcp add`, est
disponible dans [le tutoriel Codex WSL](codex-wsl-premier-agent.md).
La connexion sur une machine utilisateur **n'est pas** faite automatiquement
par l'ouverture de cette PR.

## 10. Ce qui vient ensuite

Après ce premier accès **à des résultats pré-calculés**,
on pourra ajouter, avec des autorisations explicites :

1. des liens entre provenance source et arêtes du graphe,
   pour expliquer pourquoi une influence a été retenue ;
2. une analyse bit à bit et des appels de fonctions
   avec réduction mesurée des avertissements ;
3. une interface avec **confirmation humaine**
   pour demander un nouveau test EDA ;
4. des benchmarks avec et sans MCP, évaluant précision,
   temps de réponse et taille de contexte.

**Aucune API LLM payante n'est nécessaire au serveur MCP** :
il expose des preuves et données que l'on peut auditer
indépendamment du modèle qui pose les questions.

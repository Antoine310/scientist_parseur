# Premier agent Codex avec RTLPrep sur Debian WSL (PR #18)

Ce guide est destiné à un environnement **Debian sous WSL 2** ou Ubuntu
Linux ; il ne configure pas le PC à distance et ne nécessite aucune
clé d'API payante pour le premier usage interactif de Codex.

## 1. Préparer le dépôt

Dans le terminal **Debian**, depuis un dépôt propre (vérifier que
`git status --short` est vide) :

```bash
cd ~/projets/scientist_parseur
git status --short
git fetch origin
git switch feat/agent-mcp-provenance-search
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev,mcp]'
```

Si `venv` n'est pas disponible, installer le paquet
`python3-venv` adapté à votre distribution. Ne pas écraser les
modifications locales et ne pas modifier le Python système.

## 2. Préparer de véritables résultats avec slang

Vérifier d'abord :

```bash
slang --version
python -m rtlprep doctor
```

Si `slang` est absent, se référer au
[guide d'installation slang](slang-environnement.md).
**Ne pas inventer de rapports à la place de l'exécutable.**

Une fois le vrai compilateur disponible :

```bash
python -m rtlprep deps examples/hierarchy/design.json --out reports/hierarchy
test -s reports/hierarchy/rtl_index.json
test -s reports/hierarchy/rtl_dependencies.json
```

Les fichiers `reports/` sont des artefacts locaux et ne doivent pas être
committés. Une source changée implique une régénération des rapports.

## 3. Enregistrer le serveur MCP dans Codex

**Dans le même WSL où Codex est installé**, et toujours depuis la racine
du dépôt :

```bash
ROOT="$(pwd)"
codex mcp add rtlprep -- "$ROOT/.venv/bin/python" -m rtlprep mcp \
  --index "$ROOT/reports/hierarchy/rtl_index.json" \
  --graph "$ROOT/reports/hierarchy/rtl_dependencies.json" \
  --manifest "$ROOT/examples/hierarchy/design.json" \
  --reports-dir "$ROOT/reports/hierarchy"
codex mcp list
```

Le serveur MCP est lancé par Codex en `stdio` : il ne faut pas
démarrer manuellement un deuxième serveur pour cette configuration.
Les chemins absolus évitent les erreurs liées au répertoire courant.

Si une ancienne configuration `rtlprep` existe, consulter
`codex mcp list` et la supprimer volontairement avec
`codex mcp remove rtlprep` avant de l'ajouter de nouveau.

## 4. Première vraie interrogation de l'agent

```bash
codex
```

Exemple de consigne :

> Utilise seulement les outils MCP de RTLPrep pour afficher
> `rtl_capabilities`, trouver les signaux contenant `status` via
> `rtl_find_signals`, puis explorer le fan-in du signal
> `hierarchy_top.status`. Affiche le champ `source_snapshot_status`
> et les avertissements ; cite les fichiers RTL uniquement si la
> provenance est disponible. Ne modifie rien, ne lance pas de nouveau
> test, et ne déduis pas l'équivalence des circuits depuis le graphe.

Le test automatisé `scripts/test_mcp_stdio.py` utilise le vrai client MCP
en CI, mais ce n'est **pas** un benchmark de compréhension d'un LLM.
Codex reste capable de lire ou de modifier directement des fichiers via
d'autres outils : ne pas confondre la lecture seule du **serveur MCP**
avec les autorisations générales accordées à **Codex**.

## 5. Fraîcheur, limites et suite

`rtl_capabilities.source_snapshot_status` peut valoir :

- `matching` : même empreinte sur les **sources déclarées** ;
- `stale` : des sources ont changé ;
- `unavailable` : vérification impossible à cause de fichiers absents ;
- `unverifiable` : empreinte ou manifeste manquant.

Si `stale`, relancer `rtlprep deps` puis redémarrer le serveur MCP
(en pratique, redémarrer la session Codex pour charger un nouveau
snapshot). Les résultats d'une analyse ne garantissent pas la prise en
compte des inclusions SystemVerilog transitives non déclarées.

Prochaine étape technique distincte : capturer les **expressions logiques
et conditions d'activation** depuis l'AST slang (pas par regex sur le
texte source), puis mesurer les réponses d'agents sur des circuits
d'entraînement inconnus. Aucune compatibilité GhostGate 2027 n'est
revendiquée tant que son interface officielle n'a pas été vérifiée.

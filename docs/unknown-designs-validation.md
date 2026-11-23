# PR #28 — Campagne sur des RTL externes (validation « inconnu »)

## Objectif et périmètre

Cette campagne complète [le benchmark annoté des exemples RTLPrep](benchmark-phase-g.md)
avec de **nouveaux fichiers provenant de projets tiers**. Elle répond à une
question plus difficile : la chaîne *slang réel → index RTLPrep → graphe →
requêtes de dépendances → rapport d'incertitude* continue-t-elle à fonctionner
sur des modules qui ne font pas partie de nos petites fixtures ?

**Important :** ces cas sont externes au corpus de développement initial,
mais sélectionnés par les auteurs de RTLPrep. Il ne s'agit **ni** d'un
échantillon statistiquement aléatoire, **ni** d'une évaluation aveugle
préenregistrée, **ni** d'une mesure de la précision de Codex. Le code n'utilise
aucun service LLM.

## Corpus externe v1 et provenance

Le manifeste [benchmarks/unknown_designs_v1.json](../benchmarks/unknown_designs_v1.json)
enregistre, pour chaque cas, le dépôt, la révision Git **complète** et
l'empreinte Git blob de chaque source, contrôlée **avant l'analyse** :

| Cas | Dépôt tiers | Fonction observée |
| --- | --- | --- |
| axis_register | alexforencich/verilog-axis | Registre de flux AXI-Stream (paramètres, handshake) |
| priority_encoder | alexforencich/verilog-axis | Encodeur de priorité, boucles generate |
| rxuart | ZipCPU/wbuart32 | Récepteur UART avec logique séquentielle |

Les deux dépôts sont importés par `actions/checkout` à des commits
**épinglés**, en mode sparse-checkout. Le workflow vérifie le SHA Git du
checkout et chaque hash blob ; le script Python re-vérifie les hashes avec
l'algorithme `git hash-object`. Il ne recopie pas ces fichiers tiers dans
le dépôt RTLPrep et ne télécharge pas de version « latest » non reproductible.

Ces trois cas ne permettent pas de conclure à une robustesse universelle ;
une filelist propriétaire, un SoC avec macros étendues ou des constructions
SystemVerilog non prises en charge peuvent échouer.

## Reproduction sur Debian / WSL

À partir de la branche PR #28, avec [l'installateur](dependencies-bootstrap.md)
et slang disponibles :

```bash
cd ~/projets/scientist_parseur
source .venv/bin/activate
source "$HOME/.local/share/rtlprep/toolchains/activate.sh"

mkdir -p upstream_unknown

git clone https://github.com/alexforencich/verilog-axis.git \
  upstream_unknown/verilog-axis
git -C upstream_unknown/verilog-axis checkout \
  48ff7a7e2ef782cf778d47910cf85835c64b1bce

git clone https://github.com/ZipCPU/wbuart32.git \
  upstream_unknown/wbuart32
git -C upstream_unknown/wbuart32 checkout \
  f43a6b83c3a70fb2ac0696a45c5545b233fb860b

python -m pytest -q tests/test_field_validation.py
python scripts/validate_unknown_rtl.py \
  --sources-root upstream_unknown \
  --out reports/unknown-validation
```

La racine `upstream_unknown` contient les deux checkouts. Vérifie qu'elle
reste non suivie par Git ; ne verse pas de code tiers dans une PR. La CI
utilise le checkout léger sparse à la place de deux clones complets.

Pour rejouer un seul cas :

```bash
python scripts/validate_unknown_rtl.py \
  --sources-root upstream_unknown \
  --out reports/unknown-validation \
  --case rxuart
```

La commande renvoie un code non nul si slang est absent, si une empreinte
est différente, si une élaboration échoue ou si un signal demandé n'existe
pas. En cas de compilation échouée, un rapport `validation.case.json`
et les journaux `analyze.stderr.log` permettent le diagnostic. **Un
rapport d'échec n'est jamais remplacé par un score réussi.**

## Métriques et critères de passage

Le bilan `reports/unknown-validation/unknown_validation_report.json` et
ses fichiers `<cas>/validation.case.json` contiennent :

- `source_integrity=verified_pinned_git_blobs` : intégrité des sources
  sélectionnées (non attestation cryptographique du producteur).
- `execution=passed` : slang et la chaîne d'indexation ont réellement
  terminé avec succès ; les artefacts sont alors contrôlés par top, schéma
  et `source_fingerprint` (vérifié également après exécution).
- `status=observed_within_reported_scope` : aucune limitation rapportée
  pour les analyseurs *observés* ; ne veut pas dire design couvert.
- `status=compiled_but_no_dependency_edges` : **slang a compilé**, mais
  RTLPrep ne fournit aucune arête de dépendance. Ce n'est **pas une
  réponse structurelle exploitable** ; le succès de compilation ne
  masque pas cette lacune.
- `status=observed_with_reported_limits` : avertissements, exclusions,
  analyse partielle ou traces tronquées et/ou cibles manquantes. Ce statut
  **n'est pas un échec de compilation**, mais il limite l'interprétation.
- `status=eda_or_analysis_failed` / `invalid_or_unverifiable` :
  exécution impossible, artefacts invalides ou sources incompatibles.
- Par cible `fanin`, trois budgets de requêtes
  (`max_edges=5,100,1000`) et les nombres d'arêtes, nœuds visités,
  et `truncated`. Une trace non tronquée à six niveaux n'est **pas**
  une preuve que toutes les influences du circuit sont atteintes.
- `coverage_scope=observed_analyzer_records_only` et
  `design_coverage=not_measured`, les comptes par analyseur, leurs
  exclusions, avertissements et statuts partiels.
- Les compteurs `all_elaborated`, `all_probes_present`,
  `failed_cases`, `reported_limit_cases`, `zero_edge_graph_cases`,
  `probes_without_observed_edges` et
  `all_probes_have_dependency_context` résument **uniquement les
  trois cas de cette campagne**. Un signal reconnu par l'index n'implique
  pas qu'une seule arête de son fan-in soit accessible.
  
**Première exécution réelle CI (23 novembre 2026) :** les trois sources
ont été élaborées ; `axis_register` donne **0 arête et 22 avertissements**
(notamment des registres internes non reconnus), `priority_encoder`
**8 arêtes et 2 avertissements**, `rxuart` **83 arêtes et 4 avertissements**.
Les trois cas sont **partiels**, et l'encodeur comme l'UART ont des parcours
tronqués sous le petit budget de 5 arêtes. Cette mesure est un constat
de limitation du graphe actuel, **pas trois validations structurelles
complètes**.

**Critère CI :** les 3 designs compilent et s'indexent réellement,
les empreintes correspondent, les 6 cibles de recherche existent et
les drapeaux de limites sont présents. Les avertissements, graphes vides
et troncatures ne sont pas artificiellement ignorés ni fixés à zéro :
la CI exige qu'ils soient **rapportés**, pas que l'analyse prétende
être parfaite. Elle ne valide **pas** l'utilité du graphe AXI-Stream
tant que ce dernier est vide.

Un statut `passed` ici ne signifie pas une simulation correcte, une
preuve formelle ou une compréhension exhaustive du RTL. Nous ne
publions **aucun pourcentage de précision/rappel** sur ces sources
externes, en l'absence d'un oracle indépendant vérifiant les arêtes.

## Expérimentation agent éventuelle (hors campagne)

Les futurs tests « Codex seul vs Codex + RTLPrep » doivent utiliser les
**mêmes questions** sur les **mêmes sources**, une annotation indépendante
et aveugle, des budgets et versions de modèle comparables, plusieurs
répétitions et des critères d'abstention lorsque les graphes sont
partiels. Cette PR **ne mesure pas** ces résultats et ne revendique
aucun gain d'exactitude ni de tokens.

La PR ajoute seulement une campagne de **fiabilité de la chaîne d'analyse**,
pas une mesure de bénéfice d'un LLM.

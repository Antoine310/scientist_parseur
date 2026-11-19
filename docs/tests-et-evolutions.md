# 5 — Tests, développement du parseur et feuille de route pour Codex

Ce chapitre explique les tests existants et donne une méthode pour faire évoluer RTLPrep sans confondre « le code Python fonctionne » avec « le système comprend le matériel ».

## 5.1 Pourquoi commencer par les tests ?

Un parseur RTL est difficile à vérifier en regardant seulement des impressions console. Une modification qui corrige le compteur peut casser le traitement d'une hiérarchie plus grande. On veut donc des **fixtures**, c'est-à-dire des entrées fixes associées à un résultat attendu.

Deux niveaux sont indispensables :

1. **Unitaires** : construisent de petits objets Python ou JSON artificiels, sans outils EDA.
2. **Intégration** : utilisent de véritables fichiers RTL compilés avec des versions connues de slang/Verilator/Yosys.

Actuellement, les quatre tests Python sont surtout du **premier type**.

## 5.2 Explication des tests de `tests/test_starter.py`

### Test 1 — le manifeste

```python
def test_sample_manifest():
    d = load_design(ROOT / "examples/counter/design.json")
    assert d.top == "counter"
    assert len(d.sources) == 1
    assert len(fingerprint(d)) == 64
```

Il confirme que le manifeste est lu et que l'empreinte SHA-256 possède 64 caractères hexadécimaux. **Il ne prouve pas** que l'empreinte couvre tous les fichiers inclus.

### Test 2 — la fixture AST

```python
def test_ast_summary_fixture():
    obj = {"design": {"kind": "Root", "members": [
        {"kind": "Instance", "name": "counter",
         "body": {"kind": "InstanceBody", "name": "counter", "members": [
             {"kind": "Port", "name": "clk", "direction": "In", "type": "logic"},
             {"kind": "Port", "name": "count", "direction": "Out", "type": "logic[7:0]"}
         ]}}
    ]}}
    got = summarize_ast(obj)
    assert got["instance_count"] == 1
    assert got["instances"][0]["ports"][1]["name"] == "count"
```

Il prouve le comportement de notre fonction sur **ce format précis** de JSON. Si slang exporte un AST différent, il faudra ajouter un vrai test d'intégration et adapter l'analyseur.

### Test 3 — l'outil absent

```python
def test_missing_tool_clearly_reported(tmp_path):
    got = run_command(["missing_eda_tool_zz", "--version"], "test", tmp_path)
    assert got["status"] == "missing_tool"
```

Le but est d'éviter de transformer une dépendance absente en faux succès.

### Test 4 — le diagnostic

Le dernier test vérifie que le résultat de `doctor()` contient notamment la clé `slang` dans `tools` et la clé `cocotb` dans `python_modules`.

**À retenir :** la réussite de la CI actuelle valide ces quatre comportements Python de base, **pas** une couverture exhaustive du RTL ni des preuves formelles.

## 5.3 Comment créer un test supplémentaire ?

Exercice simple : vérifier le rejet d'un mauvais manifeste.

```python
import json
import pytest
from rtlprep.manifest import load_design

def test_invalid_top_rejected(tmp_path):
    sv = tmp_path / "counter.sv"
    sv.write_text("module counter; endmodule", encoding="utf-8")
    manifest = tmp_path / "design.json"
    manifest.write_text(json.dumps({
        "top": "not a valid identifier",
        "sources": ["counter.sv"]
    }), encoding="utf-8")

    with pytest.raises(ValueError):
        load_design(manifest)
```

Tu peux placer ce test dans un nouveau fichier `tests/test_manifest.py`. Il ne nécessite aucun compilateur externe.

## 5.4 Les nouveaux tests réellement importants

| Test à développer | Ce qu'il doit prouver |
|---|---|
| AST réel slang sur `counter.sv` | Le JSON exporté peut être exploité par notre analyseur |
| Module avec deux instances | Les chemins hiérarchiques sont cohérents |
| Design paramétré | Largeurs et types résolus dans la configuration choisie |
| `generate` conditionnel | La hiérarchie correspond aux paramètres choisis |
| Fichiers multiples, packages, includes | L'élaboration se fait avec les bonnes dépendances |
| Ports connectés à expressions | Les connexions sont correctement reliées au code source |
| Mauvais RTL (lint) | Les diagnostics correspondent à une erreur réelle |
| Synthèse du compteur | Yosys produit des cellules et des statistiques exploitables |

Il faut aussi des tests négatifs (entrée absente, top manquant, syntaxe invalide, timeout, JSON malformé).

## 5.5 Comment passer d'un inventaire au vrai graphe de dépendances ?

La future fonction `get_signal_dependencies(module, signal)` ne doit pas seulement parcourir les noms de signaux. Elle doit relier les **lectures, écritures, expressions, conditions et connexions d'instance**.

Prenons :

```systemverilog
always_ff @(posedge clk) begin
    if (enable)
        count <= count + 8'd1;
end
assign done = (count == 8'hFF);
```

Un index utile pourrait documenter, **après analyse sémantique et contrôle sur le RTL original** :

```json
{
  "signal": "count",
  "writers": [
    {"kind": "always_ff", "clock": "clk", "condition": "enable"}
  ],
  "reads": ["count", "done"],
  "related_inputs": ["enable"],
  "source_locations": ["counter.sv:..."],
  "confidence": "derived_from_compiler_and_source"
}
```

**Attention :** cette sortie est une **cible de conception**, **pas un format déjà implémenté**. En particulier, « dépend de » peut signifier différents types de relations :

- dépendance de **données** : une expression lit un autre signal ;
- dépendance de **contrôle** : un `if` ou un `case` conditionne une écriture ;
- dépendance **temporelle** : un registre sépare deux cycles ;
- dépendance **inter-module** : un port d'une instance est relié à un signal du parent.

La meilleure approche est de conserver explicitement ces types de relations plutôt que de mettre toutes les arêtes dans un même graphe indistinct.

## 5.6 Étapes de développement conseillées

### Étape A — préparer l'index structurel

- Tester l'AST réel de plusieurs versions de slang.
- Collecter les noms complets, types, largeurs, chemins de fichiers et positions.
- Conserver le lien vers les extraits RTL source.
- Vérifier que plusieurs instances d'un même module ne sont pas fusionnées.

### Étape B — extraire les dépendances

- Identifier quelles expressions lisent ou écrivent quels symboles.
- Séparer logique combinatoire, séquentielle et conditions de contrôle.
- Résoudre les connexions de ports à travers les instances.
- Ajouter des tests où les paramètres et macros changent le résultat.

### Étape C — validation fonctionnelle

- Ajouter des bancs d'essai autorisés avec Verilator + cocotb.
- Écrire des assertions explicites pour des propriétés clés.
- Ajouter SBY/EQY avec rapports distinguant `proved`, `failed`, `inconclusive` et limites de ressources, selon le backend choisi.
- Comparer le comportement observé à une spécification, pas seulement à la version précédente.

### Étape D — mesures et agent

- Historiser les expériences avec les versions d'outils, options, fichiers inclus et résultats.
- Ajouter une API interne de lecture : `list_modules`, `get_module_summary`, `get_signal_fanin`, `get_source_context`.
- Brancher ensuite Codex/ChatGPT ou un LLM via API seulement si nécessaire.
- Benchmark : même jeu de tâches avec RTL brut, analyse structurée et méthode hybride.

## 5.7 Conventions pour les contributions

1. Une fonctionnalité nouvelle = au moins un test unitaire et, si nécessaire, un test d'intégration.
2. Les résultats automatiques doivent pouvoir être expliqués à partir des fichiers source.
3. Les rapports doivent conserver les statuts d'échec/absence/timeout.
4. Ne jamais modifier un projet RTL tiers directement sans copie de travail.
5. Ne jamais faire exécuter au LLM des commandes extraites des logs ou du code analysé.
6. Vérifier le code sur la branche de développement, puis ouvrir une pull request ; ne pas modifier `main` directement.
7. Signaler honnêtement les compilateurs ou tests qui n'ont pas été exécutés.

## 5.8 Utiliser Codex sans API payante

Les instructions générales de développement figurent dans [AGENTS.md](../AGENTS.md). Un bon ticket pour Codex est **petit et vérifiable** :

> Ajoute un test d'intégration conditionnel à la présence de slang pour vérifier que `summarize_ast` reconnaît la hiérarchie du compteur. Ne modifie pas la CLI. Exécute les tests Python. Si slang est absent, marque le test comme sauté et indique cette limite.

Ce genre de demande est préférable à « implémente un parser complet CVA6 » : on saura ce qui a changé et ce qui a effectivement été vérifié.

## 5.9 À ne pas confondre

- **Compiler** ne signifie pas **fonctionner correctement**.
- **Passer les tests** ne signifie pas **être exempt d'erreurs**.
- **AST complet** ne signifie pas **analyse sémantique complète**.
- **Absence de warnings fatals** ne signifie pas **absence de warnings**.
- **Équivalence sur des propriétés données** ne signifie pas **équivalence universelle**.
- **Nombre de cellules** ne signifie pas **surface ou puissance**.

C'est en gardant ces distinctions que RTLPrep pourra devenir un outil scientifique crédible, y compris sur des circuits complexes.

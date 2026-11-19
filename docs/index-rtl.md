# Guide pédagogique : index RTL et navigation (phase B)

La phase B transforme l'AST élaboré par **slang** en un **index JSON stable**
que des programmes Python, Codex ou plus tard un serveur MCP pourront
interroger **sans relire tout le RTL dans un contexte LLM**.

L'index est construit par notre code Python. **Le parsing et l'élaboration
SystemVerilog sont toujours réalisés par slang** : nous ne réécrivons
ni le langage ni le compilateur.

## 1. Première utilisation

Dans le dépôt, avec slang v12.1 installé comme expliqué dans
[ce tutoriel](slang-environnement.md) :

```bash
python -m pip install -e '.[dev]'
python -m rtlprep index examples/hierarchy/design.json --out reports/hierarchy
python -m rtlprep query reports/hierarchy/rtl_index.json modules
python -m rtlprep query reports/hierarchy/rtl_index.json tree
python -m rtlprep query reports/hierarchy/rtl_index.json module leaf
python -m rtlprep query reports/hierarchy/rtl_index.json instance hierarchy_top.first
python -m rtlprep query reports/hierarchy/rtl_index.json signal hierarchy_top.first status
python -m rtlprep source examples/hierarchy/design.json leaf.sv --line 2 --radius 2
```

`index` produit **trois fichiers importants** :

- `elaborated_ast.json` : AST complet fourni par le compilateur ;
- `design_summary.json` : résumé ancien format, conservé pour compatibilité ;
- `rtl_index.json` : nouveau format d'index `schema_version: 1`.

Le fichier `index.result.json` contient le statut de la construction. Si
slang n'est pas installé, il indique `missing_tool`, et aucun ancien index
ne doit rester accessible par erreur.

## 2. Exemple : deux instances d'un même module

Considérons :

```systemverilog
module hierarchy_top(input logic enable, output logic [1:0] status);
    leaf first  (.enable(enable), .status(status[0]));
    leaf second (.enable(enable), .status(status[1]));
endmodule
```

La définition `leaf` existe **une fois**, mais elle est utilisée **deux
fois**. Il faut donc distinguer :

```text
Définition de module : leaf

Instance : hierarchy_top.first
Instance : hierarchy_top.second
```

L'index contient une liste `modules` avec les **noms de définitions**,
et une liste `instances` avec les **occurrences hiérarchiques**.

Un même module peut avoir différentes spécialisations paramétrées. La phase
actuelle regroupe les noms de modules pour la navigation, mais **les
différentes occurrences gardent chacune leurs propres ports et signaux**.
Nous ne prétendons pas que deux instances du même nom ont forcément des
paramètres identiques.

## 3. Le format JSON

Exemple simplifié, représentatif du contrat mais sans tous les détails :

```json
{
  "schema_version": 1,
  "backend": "slang-ast-json",
  "top": "hierarchy_top",
  "modules": [
    {
      "name": "leaf",
      "instance_paths": [
        "hierarchy_top.first",
        "hierarchy_top.second"
      ]
    }
  ],
  "instances": [
    {
      "path": "hierarchy_top.first",
      "name": "first",
      "module": "leaf",
      "parent": "hierarchy_top",
      "source": {
        "file": "examples/hierarchy/top.sv",
        "line": 6,
        "column": 10
      },
      "definition_source": {
        "file": "examples/hierarchy/leaf.sv",
        "line": 1,
        "column": 8
      },
      "ports": [
        {
          "name": "status",
          "direction": "Out",
          "type": "logic",
          "source": {
            "file": "examples/hierarchy/leaf.sv",
            "line": 3,
            "column": 18
          }
        }
      ]
    }
  ],
  "signals": [
    {
      "instance_path": "hierarchy_top.first",
      "name": "status",
      "kind": "Variable",
      "type": "logic",
      "source": {
        "file": "examples/hierarchy/leaf.sv",
        "line": 3,
        "column": 18
      }
    }
  ],
  "counts": {"modules": 2, "instances": 3, "signals": 7}
}
```

**Attention :** cet exemple est volontairement réduit et les numéros
de ligne sont illustratifs. Pour les lignes exactes, il faut consulter le
fichier `rtl_index.json` réellement généré.

Le format ne contient **aucune arête de dépendance** : la présence de deux
signaux dans un module ne suffit pas à conclure qu'ils s'influencent.

## 4. Explication de `rtlprep/index.py`

### 4.1 Vérifier l'AST avant de l'indexer

```python
validated = summarize_ast(ast, expected_top=expected_top)
by_path = {item["hierarchy_path"]: item
           for item in validated["instances"]}
```

On réutilise les validations de la phase A : top présent, structure
compatible avec l'export JSON, chemins d'instance uniques. Si l'index
ne contient pas toutes les instances détectées, `build_index` refuse de
publier un résultat incomplet.

### 4.2 Parcourir les instances

```python
def traverse(members, parents=()):
    for node in members:
        if node.get("kind") == "Instance":
            body = node["body"]
            path_parts = (*parents, node["name"])
            path = ".".join(path_parts)
            ...
            traverse(body["members"], path_parts)
```

Cette récursion descend dans la hiérarchie **élaborée** et conserve le
chemin de chaque occurrence. L'index utilise `node["body"]["name"]`
pour connaître la définition instanciée.

Une déclaration de signal trouvée dans `hierarchy_top.first`
n'est donc pas confondue avec une déclaration homonyme dans
`hierarchy_top.second`.

### 4.3 Lire les ports et les signaux

Deux catégories d'objets de slang nous intéressent actuellement :

- `kind == "Port"` : interface de module, avec sens `In` / `Out`.
- `kind == "Variable"` ou `kind == "Net"` : symboles matériels déclarés
  directement dans le corps élaboré.

Pour une même entrée `enable`, il peut exister à la fois un objet
`Port` et un objet `Net`. **Ce ne sont pas deux signaux matériels
indépendants** ; ce sont des vues complémentaires. Ainsi,
`get_signal_info` renvoie séparément les `ports` et les
`declarations` ayant le même nom.

Le nombre `counts.signals` correspond aux **déclarations Variable/Net
indexées**, pas au nombre de fils physiques ou de bits du design.

Les objets déclarés dans des structures plus complexes ne sont pas
encore tous pris en charge. L'index n'est pas une liste exhaustive de
tous les symboles SystemVerilog possibles.

### 4.4 Conserver les références au code source

Le compilateur slang v12.1, appelé avec `--ast-json-source-info`,
rapporte notamment ces clés :

```json
{
  "source_file": "examples/hierarchy/leaf.sv",
  "source_line": 3,
  "source_column": 18
}
```

Notre fonction `source_location` ne fait que **recopier et contrôler
les types** de ces valeurs. Si elles manquent, le champ `source` vaut
`null`. Elle ne cherche jamais un nom avec une regex dans le RTL
pour inventer un numéro de ligne.

Cela prépare les futures réponses de l'agent du type « montre-moi
l'endroit où `status` est défini ».

### 4.5 Pourquoi un numéro de version ?

`schema_version = 1` permet de refuser explicitement un ancien
format incompatible. Avant d'ajouter de nouveaux types de données,
on pourra adapter ou migrer le schéma sans casser les clients CLI/MCP.

## 5. Les fonctions de requête

| Fonction Python | CLI correspondante | Résultat |
| --- | --- | --- |
| `list_modules` | `query ... modules` | Noms des modules |
| `get_module_summary` | `query ... module leaf` | Module et ses occurrences |
| `get_instance_tree` | `query ... tree` | Hiérarchie avec parents |
| `get_instance` | `query ... instance hierarchy_top.first` | Ports et origine d'une instance |
| `get_signal_info` | `query ... signal hierarchy_top.first status` | Port(s) et déclaration(s) correspondants |
| `get_source_context` | `source design.json leaf.sv --line 2` | Extrait numéroté du fichier RTL |

Les requêtes sur `rtl_index.json` ne relancent **pas** slang : elles
lisent uniquement le rapport déjà produit.

La commande `source` n'ouvre que les fichiers explicitement mentionnés
dans le manifeste et limite le rayon de lecture à 30 lignes. Cela évite
d'ouvrir aveuglément n'importe quel chemin qui apparaîtrait dans un AST
tiers.

## 6. Limitations et prochaine étape

Le schéma est une **première version** pour des circuits modestes :

- Les dépendances `fan-in` / `fan-out` ne sont pas calculées.
- Les connexions `.port(signal)` ne sont pas encore transformées en arêtes.
- Les blocs `generate`, interfaces et packages complexes demanderont
  des tests supplémentaires.
- Le nom d'un module n'identifie pas à lui seul sa spécialisation
  paramétrée.
- L'export complet sans cache d'instance peut consommer plus de mémoire
  sur des SoC.
- Les références source ne sont pas validées en re-compilant un projet
  externe : on conserve ce que slang renvoie.

**Travail suivant :** construire un graphe de dépendances **typé** à partir
des références sémantiques du compilateur : écritures, lectures, conditions
de contrôle, horloges et connexions de ports. Cela demandera de nouveaux
tests avec de vraies données SystemVerilog, et pas seulement des fixtures.

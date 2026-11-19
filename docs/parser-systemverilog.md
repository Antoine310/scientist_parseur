# 2 — Comprendre le parseur SystemVerilog, l'AST et `summarize_ast`

Ce chapitre est le plus important si tu souhaites développer le futur analyseur pour un CPU RISC-V.

## 2.1 Pourquoi ne pas parser le RTL avec des expressions régulières ?

Voici un exemple :

```systemverilog
module counter #(
    parameter int WIDTH = 8
) (
    input  logic clk,
    input  logic rst_n,
    input  logic enable,
    output logic [WIDTH-1:0] count
);
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            count <= '0;
        else if (enable)
            count <= count + 1'b1;
    end
endmodule
```

Les mots-clés ne suffisent pas pour comprendre ce texte :

- `WIDTH` est un paramètre qui modifie la largeur réelle du port ;
- `count` apparaît à la fois en lecture et en écriture ;
- le registre est modifié sur front d'horloge et réinitialisé sur reset actif bas ;
- le nom `enable` pourrait être une macro, une sortie ou un signal interne dans un autre contexte ;
- les `generate`, `typedef`, `package`, `interface` et définitions de macros compliquent rapidement l'analyse.

Une regex ne comprend ni ces structures ni leurs portées. Le bon point de départ est un vrai compilateur SystemVerilog.

## 2.2 Parser, élaborer, simuler : trois étapes différentes

1. **Parsing** : lit le texte et construit des nœuds (module, déclaration, instruction, expression).
2. **Élaboration** : choisit le `top`, résout les instances, paramètres et plusieurs références au sein d'une configuration.
3. **Simulation** : calcule l'évolution des signaux dans le temps selon des stimuli. **RTLPrep ne fait pas encore cette étape**.

Une façon de le retenir : le parser lit la grammaire ; l'élaborateur construit une version cohérente du design ; le simulateur exécute son comportement temporel.

## 2.3 L'outil actuellement utilisé : l'exécutable `slang`

Dans [rtlprep/runner.py](../rtlprep/runner.py), la fonction `analyze` prépare :

```python
ast_path = out / "elaborated_ast.json"
cmd = [
    "slang",
    "--ast-json", str(ast_path),
    "--ast-json-source-info",
    *common_slang_args(d),
]
result = run_command(cmd, "analyze", out, timeout)
```

**Ligne par ligne :**

- `ast_path` : emplacement où écrire l'AST exporté.
- `"slang"` : exécutable externe à trouver dans le `PATH`.
- `--ast-json` : demande l'export de l'arbre en JSON.
- `--ast-json-source-info` : demande les références de provenance lorsqu'elles sont supportées.
- `*common_slang_args(d)` : ajoute le top, les dossiers d'inclusion, les macros et les fichiers.
- `run_command` : lance réellement le programme et recueille statut et logs.

La fonction qui construit les arguments :

```python
def common_slang_args(d: Design) -> list[str]:
    args = ["--top", d.top]
    for inc in d.includes:
        args.append("-I" + str(inc))
    for define in d.defines:
        args.append("-D" + define)
    args.extend(str(f) for f in d.sources)
    return args
```

Ainsi, pour le compteur, la commande est conceptuellement :

```bash
slang --ast-json reports/counter/elaborated_ast.json \
      --ast-json-source-info \
      --top counter \
      /chemin/vers/examples/counter/counter.sv
```

**Précision importante :** `pyslang` n'est **pas** utilisé ici pour parcourir l'AST depuis Python. Le projet lance la CLI `slang` et charge ensuite le JSON avec `json.loads`. Les versions de slang peuvent avoir des options/structures de sortie différentes : tester sur une installation précise est nécessaire.

## 2.4 À quoi ressemble un AST ?

Considère ce mini RTL :

```systemverilog
module child(input logic x, output logic y);
    assign y = ~x;
endmodule

module top(input logic a, output logic b);
    child u_child(.x(a), .y(b));
endmodule
```

Nous avons **deux modules définis**, mais **une instance nommée `u_child`** dans `top` (en plus de l'instance top utilisée pour l'élaboration).

Un AST contient des objets emboîtés. **Le JSON ci-dessous est une *fixture pédagogique simplifiée***, semblable à celle des tests, **pas une copie certifiée de la sortie de slang** :

```json
{
  "design": {
    "kind": "Root",
    "members": [
      {
        "kind": "Instance",
        "name": "top",
        "body": {
          "name": "top",
          "members": [
            {
              "kind": "Instance",
              "name": "u_child",
              "body": {
                "name": "child",
                "members": [
                  {"kind": "Port", "name": "x", "direction": "In", "type": "logic"},
                  {"kind": "Port", "name": "y", "direction": "Out", "type": "logic"}
                ]
              }
            }
          ]
        }
      }
    ]
  }
}
```

L'intérêt d'un AST est que `"kind": "Instance"` est une **information fournie par le compilateur**, pas une intuition du LLM.

## 2.5 Décortiquer `rtlprep/analysis.py`

Le code de v0.1 commence ainsi :

```python
def summarize_ast(ast: dict[str, Any]) -> dict[str, Any]:
    roots = ast.get("design", ast)
    result: list[dict[str, Any]] = []
```

- `ast` : dictionnaire Python chargé depuis le fichier JSON.
- `ast.get("design", ast)` : cherche une clé `design`, sinon parcourt la racine.
- `result` : liste où sont accumulées les instances découvertes.

Puis vient une fonction **imbriquée et récursive** :

```python
def walk(obj: Any, parents: tuple[str, ...] = ()) -> None:
    if isinstance(obj, list):
        for x in obj:
            walk(x, parents)
    elif isinstance(obj, dict):
        # exploration du dictionnaire...
        ...
```

Ce qu'il faut comprendre :

- une **liste** contient plusieurs enfants ;
- un **dictionnaire** contient des paires clé/valeur ;
- la fonction s'appelle elle-même pour descendre dans ces enfants ;
- `parents` garde le chemin des instances déjà traversées, sous forme de tuple.

Le traitement spécial commence lorsqu'une instance est rencontrée :

```python
if obj.get("kind") == "Instance":
    body = obj.get("body") if isinstance(obj.get("body"), dict) else {}
    name = str(obj.get("name", "<anonymous>"))
    module = str(body.get("name", "<unknown>"))
    new_parents = (*parents, name)
```

- `kind` indique que le nœud représente une instance.
- `body` contient, dans la représentation attendue, sa définition élaborée.
- `name` est **le nom de l'instance** (par exemple `u_child`).
- `module` est **le nom du module** qui a servi à la créer (par exemple `child`).
- `new_parents` ajoute cette instance à la hiérarchie : `("top", "u_child")`.

On extrait ensuite les ports :

```python
ports = []
for member in body.get("members", []):
    if isinstance(member, dict) and member.get("kind") == "Port":
        ports.append({
            "name": member.get("name"),
            "direction": member.get("direction"),
            "type": member.get("type"),
        })
```

**Différence essentielle :** la présence d'un port ne prouve pas que le code a identifié toutes ses connexions, ses expressions d'association ou son sens fonctionnel.

Enfin, le résumé est enregistré :

```python
result.append({
    "hierarchy_path": ".".join(new_parents),
    "instance": name,
    "module": module,
    "ports": ports,
})
```

Et le parcours continue dans les enfants :

```python
for k, v in obj.items():
    if k in ("addr", "type"):
        continue
    walk(v, new_parents)
```

Les clés `addr` et `type` sont ignorées par le parcours pour éviter de s'enfoncer dans certaines métadonnées. Ce choix est **provisoire**, pas une garantie que l'on ignore uniquement des champs sans intérêt dans toutes les versions d'AST.

La fonction termine par :

```python
walk(roots)
return {
    "format": "slang-elaborated-ast",
    "instances": result,
    "instance_count": len(result),
}
```

## 2.6 Exemple de résultat attendu

Pour la fixture du §2.4, un résumé pourrait ressembler à ceci :

```json
{
  "format": "slang-elaborated-ast",
  "instance_count": 2,
  "instances": [
    {
      "hierarchy_path": "top",
      "instance": "top",
      "module": "top",
      "ports": []
    },
    {
      "hierarchy_path": "top.u_child",
      "instance": "u_child",
      "module": "child",
      "ports": [
        {"name": "x", "direction": "In", "type": "logic"},
        {"name": "y", "direction": "Out", "type": "logic"}
      ]
    }
  ]
}
```

Dans un véritable export, la manière d'encoder les ports et les instances doit être **confirmée sur l'AST produit par l'outil installé**. Si la structure ne correspond pas à la fixture, le résumé peut être vide ou incomplet **sans que cela signifie que le design n'a pas de modules**.

## 2.7 Les limites actuelles (très importantes)

`summarize_ast` ne sait pas encore :

- différencier systématiquement toutes les définitions de modules et toutes leurs instances selon les formats d'AST ;
- résoudre l'ensemble des connexions `.port(signal)` ;
- trouver tous les lecteurs et écrivains d'un signal ;
- distinguer avec certitude logique combinatoire, registre, synchronisation, reset et latence ;
- construire un graphe de **fan-in** (ce qui influence un signal) ou de **fan-out** (ce qu'il influence) ;
- vérifier la fidélité de l'export AST aux différentes versions de slang ;
- attribuer une intention à un comportement sans la spécification fonctionnelle.

Même avec un AST complet, une **analyse sémantique** supplémentaire serait nécessaire pour calculer des dépendances fiables, surtout avec alias, packages, macros et signaux traversant les modules.

## 2.8 Pourquoi garder à la fois AST et RTL brut ?

Un index structuré peut répondre : « où est l'instance ? », « quels ports existe-t-il ? », « où se trouve le registre ? ». Le RTL brut permet de vérifier **l'expression exacte** et les conditions. La bonne architecture pour un futur LLM est donc :

```text
Question du LLM
     │
     ├─► index du design → chemins, symboles, types, références
     └─► sources RTL exactes → conditions et opérations
                  │
                  ▼
        raisonnement + vérification par outils
```

### Exercices de compréhension

1. Dans `analysis.py`, repère la seule condition qui décide si un nœud est une instance.
2. Explique la différence entre les champs `module` et `instance`.
3. Modifie une fixture de test pour ajouter un deuxième enfant ; vérifie que `instance_count` augmente.
4. Imagine le JSON d'un CPU contenant dix instances du même module : pourquoi un seul nom de module ne suffit-il pas à identifier un signal ?

**Étape suivante :** lire [le chapitre des outils de validation](outils-et-validation.md) pour comprendre ce qui arrive à l'AST après son extraction.

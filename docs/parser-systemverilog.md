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

## 2.5 Décortiquer `rtlprep/analysis.py` (version durcie)

Dans la version initiale, le code essayait de parcourir n'importe quel objet JSON, même si
le compilateur n'avait pas fourni la structure attendue. Cela risquait de produire
un **résumé vide présenté comme réussi**. La nouvelle version protège cette étape.

### Étape 1 : valider la racine

```python
def summarize_ast(ast: dict[str, Any], *, expected_top: str | None = None) -> dict[str, Any]:
    if not isinstance(ast, dict):
        raise ValueError("AST slang : la racine JSON doit être un objet")
    root = ast.get("design")
    if not isinstance(root, dict) or root.get("kind") != "Root":
        raise ValueError("AST slang : design.kind=Root manquant")
    members = root.get("members")
    if not isinstance(members, list):
        raise ValueError("AST slang : design.members doit être une liste")
```

- `ast` est le dictionnaire produit par `json.loads`.
- `root` est la racine de l'AST élaboré que nous attendons de slang.
- `kind == "Root"` vérifie que nous avons bien un arbre de **design élaboré**,
  et non un CST ou un fichier JSON quelconque.
- `members` contient les objets déclarés au niveau racine.
- Si le format est différent, le code signale l'erreur au lieu de deviner.

### Étape 2 : vérifier le top choisi

```python
top_nodes = [m for m in members if isinstance(m, dict) and m.get("kind") == "Instance"]
if not top_nodes:
    raise ValueError("AST slang : aucune instance de premier niveau")
```

Quand `runner.analyze` connaît le module demandé dans le manifeste,
il le transmet à la fonction :

```python
summary = summarize_ast(raw, expected_top=d.top)
```

Le résumé n'est accepté que si l'on retrouve le top parmi les instances
de premier niveau (par son nom d'instance ou le nom du module du corps).
**Un top absent est une erreur**, pas un design silencieusement vide.

### Étape 3 : récursion sur les instances

La fonction `walk` descend récursivement dans l'AST :

```python
def walk(obj: Any, parents: tuple[str, ...] = ()) -> None:
    if isinstance(obj, list):
        for x in obj:
            walk(x, parents)
    elif isinstance(obj, dict):
        # Repère les nœuds d'instance, extrait leurs ports et parcourt les enfants.
        ...
```

Quand elle rencontre un dictionnaire portant `kind == "Instance"` :

1. elle vérifie que l'instance a un **nom** et un **corps** ;
2. elle lit le nom du module dans le corps ;
3. elle cherche les objets `kind == "Port"` parmi les membres ;
4. elle calcule le chemin hiérarchique à partir des noms parents ;
5. elle ajoute une entrée dans le résultat ;
6. elle descend **uniquement dans les membres du corps élaboré**.

L'intérêt est de ne pas confondre les métadonnées ou références de connexions
avec de nouvelles instances. Le code refuse également un chemin d'instance
dupliqué, au lieu de conserver deux entrées impossibles à distinguer.

```python
new_parents = (*parents, name)
path = ".".join(new_parents)
if path in seen_paths:
    raise ValueError(f"AST slang : chemin d'instance dupliqué : {path}")
seen_paths.add(path)
```

**Attention :** les nœuds de port et de générateurs ont des variantes selon
la structure exacte exportée par slang. Le parcours doit être confronté à des
AST réels ; la version actuelle ne garantit pas encore une interprétation
parfaite de tous les blocs `generate` ou interfaces complexes.

### Étape 4 : résultat

La fonction renvoie :

```python
return {
    "format": "slang-elaborated-ast",
    "instances": result,
    "instance_count": len(result),
}
```

Le champ `instance_count` compte les **instances** enregistrées,
et non le nombre de **définitions de modules**. Plusieurs instances
d'un même module ont des chemins différents.

### Étape 5 : artefacts et erreurs de post-traitement

Dans `runner.analyze` :

- les anciens fichiers `elaborated_ast.json` et `design_summary.json` sont
  supprimés **avant** le lancement pour empêcher qu'une ancienne exécution
  ne soit prise pour le résultat courant ;
- si slang réussit mais que le JSON est illisible ou incohérent,
  le résultat devient `failed` ;
- le statut final (y compris les erreurs de validation AST) est réécrit dans
  `analyze.result.json`, et pas seulement affiché à l'écran.

Cela rend les rapports beaucoup plus utiles pour un futur agent.

### Important : cache d'instances slang

Dans les tests réels v12.1, le circuit `hierarchy_top` avec deux instances
de `leaf` a révélé que le JSON exporté peut réutiliser des corps
d'instances mis en cache. Notre code ne résout pas encore ces références :
l'orchestrateur lance donc provisoirement
`slang --disable-instance-caching --ast-json ...`.

Cela **ne transforme pas RTLPrep en compilateur** : slang continue
d'effectuer l'élaboration. L'option peut en revanche coûter plus cher
sur un très gros design ; on revisitera ce choix lors de l'index structurel.
Voir [l'étude pratique de cette erreur](slang-environnement.md).

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

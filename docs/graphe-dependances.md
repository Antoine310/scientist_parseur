# Phase C — Graphe de dépendances RTL : cours et mode d'emploi

Ce chapitre décrit le **MVP de graphe de dépendances** développé au-dessus
de l'AST élaboré par **slang v12.1**. L'objectif est de répondre à :

> « Quels signaux peuvent influencer cette sortie ou ce registre ? »
> « Quels signaux sont potentiellement affectés par cette entrée ? »

Le graphe est un outil **d'exploration et de diagnostic**, pas une preuve
formelle que deux signaux ont toujours une relation causale fonctionnelle.

## 1. Exemple guidé

Le répertoire [examples/dependencies](../examples/dependencies/) contient deux modules :

- `logic_leaf.sv` : une porte ET et une sélection conditionnelle ;
- `dependency_top.sv` : une instance `child`, une affectation de sortie et un compteur avec `always_ff`.

Le code du sous-module illustre deux formes de dépendances :

```systemverilog
logic and_result;
assign and_result = a & b;
assign y = sel ? and_result : a;
```

On veut enregistrer :

- **Données** : `a → and_result`, `b → and_result`,
  `and_result → y` et `a → y`.
- **Contrôle** : `sel → y` : la condition choisit une branche.
- Les liens restent **dans chaque instance** : `dependency_top.child.a` est
  différent de `dependency_top.a`.

Au niveau supérieur :

```systemverilog
logic_leaf child(.a(a), .b(b), .sel(sel), .y(interm));
assign out = interm;
```

Le compilateur indique quels ports sont reliés à quels symboles. Le graphe crée
les relations de lecture des entrées et de production des sorties, de manière
**orientée** :

```text
dependency_top.a
      │ port_input
      ▼
dependency_top.child.a
      │ data
      ├───────────────► dependency_top.child.y
      │
      ▼
dependency_top.child.and_result
      │ data
      ▼
dependency_top.child.y
      │ port_output
      ▼
dependency_top.interm
      │ data
      ▼
dependency_top.out
```

Cette figure montre **quelques chemins** et non toutes les arêtes ;
`b` et `sel` contribuent également.

## 2. Les commandes

Installer `slang` conformément à [ce tutoriel](slang-environnement.md),
puis :

```bash
python -m rtlprep deps examples/dependencies/design.json --out reports/deps

python -m rtlprep trace reports/deps/rtl_dependencies.json \
    fanin dependency_top.out --depth 6

python -m rtlprep trace reports/deps/rtl_dependencies.json \
    fanout dependency_top.a --depth 6
```

- `deps` lance l'**analyse slang réelle**, construit l'index structurel
  existant et en déduit un graphe de dépendances.
- `fanin` remonte vers les influences possibles d'un signal.
- `fanout` suit les signaux que celui-ci peut influencer.
- `--depth 6` borne la longueur des chemins. Le plafond est 15.
- `--max-edges 200` limite le nombre d'arêtes retournées, jusqu'à 5000.

Les fichiers produits comprennent :

| Fichier | Rôle |
| --- | --- |
| `elaborated_ast.json` | AST de slang, avec les expressions résolues |
| `rtl_index.json` | Index des modules et déclarations (phase B) |
| `rtl_dependencies.json` | **Nouveau graphe**, schéma 1 |
| `deps.result.json` | Statut final et nombre d'arêtes / avertissements |

Si slang est absent ou l'analyse échoue, aucun ancien
`rtl_dependencies.json` n'est présenté comme résultat nouveau.

Les requêtes `trace` lisent le JSON déjà généré : elles peuvent être
exécutées **sans compilateur, sans abonnement API et sans LLM**.

## 3. Le format d'une arête

Une relation est orientée de `source` vers `target` :

```json
{
  "source": "dependency_top.child.and_result",
  "target": "dependency_top.child.y",
  "kind": "data",
  "sequential": false,
  "detail": "",
  "location": {
    "file": "examples/dependencies/logic_leaf.sv",
    "line": 9
  }
}
```

Les cinq grandes catégories actuellement créées :

| `kind` | Sens |
| --- | --- |
| `data` | La valeur de destination est calculée à partir d'une lecture de la source |
| `control` | La source apparaît dans une condition `if` ou un `?:` contrôlant une affectation |
| `event` | Une transition de la source participe au déclenchement d'un bloc temporisé ; le champ `detail` conserve `PosEdge` ou `NegEdge` |
| `port_input` | Une expression parent alimente le port d'entrée d'une instance |
| `port_output` | Un port de sortie d'instance alimente un signal parent |

**Important :** une arête `control` ne prouve pas que changer la condition
modifie effectivement la sortie sur toutes les valeurs d'entrée. Une arête
`event` ne permet pas de distinguer à elle seule l'horloge du reset.
`sequential: true` indique que l'affectation provient d'un `always_ff`,
sans déduire le nombre de cycles de latence.

## 4. Explication pédagogique de `rtlprep/dependencies.py`

### 4.1 Toujours commencer par un index validé

```python
structural = index if index is not None else build_index(ast, expected_top=expected_top)
```

La fonction `build_dependency_graph` récupère les instances et les noms
de signaux répertoriés par l'index RTL de la phase B. Les nœuds ont la
forme **`chemin.instance.nom_signal`** : deux instances différentes du
même module ont donc deux identifiants distincts.

Les symboles sont extraits des objets `NamedValue` de l'AST slang.
Dans le JSON v12.1, la valeur `symbol` contient un identifiant interne,
puis le nom humain du symbole. Notre code **ignore l'adresse interne** et
vérifie que le nom figure dans les déclarations de l'instance.

Exemple extrait d'un AST réel (identifiant modifié) :

```json
{"kind": "NamedValue", "symbol": "123456 and_result"}
```

On utilise `and_result`, **pas** le nombre `123456` qui change d'une
exécution à l'autre. Le code ne tente pas de reconstruire un signal
en recherchant du texte au hasard dans un fichier source.

### 4.2 Affectations : lecture à droite, écriture à gauche

Dans slang, l'affectation :

```systemverilog
assign and_result = a & b;
```

contient conceptuellement :

```text
ContinuousAssign
└── assignment: Assignment
    ├── left: NamedValue(and_result)
    └── right: BinaryOp(BinaryAnd)
        ├── left: NamedValue(a)
        └── right: NamedValue(b)
```

La fonction `target` résout la variable à gauche.
La fonction `reads` parcourt l'expression à droite, reconnaît les
`NamedValue` et crée les arêtes `data`.

Dans une expression ternaire `sel ? a : b`, `reads` sépare la condition
(`control`) des valeurs possibles (`data`).

Un opérateur inconnu ne doit **pas** être interprété comme si nous le
comprenions : le code enregistre un **avertissement** et n'invente
pas de dépendance depuis un appel de fonction ou une construction
non prise en charge.

### 4.3 Affectations séquentielles : conditions et événements

Voici une portion du circuit d'exemple :

```systemverilog
always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n)
        count <= 4'd0;
    else if (enable)
        count <= count + 4'd1;
end
```

Slang fournit des nœuds `ProceduralBlock`, `Timed`,
`EventList`, `SignalEvent`, `Conditional`,
`ExpressionStatement` et `Assignment`.

Le parcours `statements` mémorise :

- les signaux `clk` et `rst_n` qui déclenchent le bloc (`event`),
  avec leurs types de front ;
- les conditions `rst_n` et `enable` qui influencent les chemins
  d'affectation (`control`) ;
- la lecture de `count` dans `count + 1` (`data`).

Ainsi, `count → count` représente une **dépendance d'état** :
la prochaine valeur dépend de la valeur actuelle. Ce n'est **pas**
une boucle combinatoire prouvée. Le parcours `trace` mémorise
les nœuds visités, pour ne jamais tourner indéfiniment.

### 4.4 Connexions d'instances : entrée ou sortie ?

L'instance `child` de notre exemple contient, dans le JSON slang,
une liste de `connections` avec un `port` et une `expr`.
Le sens `direction` vient du compilateur.

- `In` : on prend les symboles lus par l'expression dans le parent et
  on trace `parent.a → parent.child.a`.
- `Out` : slang décrit la cible côté parent sous la forme d'une
  affectation de lvalue ; on trace `parent.child.y → parent.interm`.
- `InOut` : **pas encore supporté**, un avertissement est ajouté.
- Une sélection de bits peut générer une relation au **signal entier**,
  pas une arête précise pour chaque bit. Le rapport le signale.

Cette séparation empêche de créer par erreur une relation inverse
entre les ports et le parent.

### 4.5 Recherche en largeur : fan-in et fan-out

`trace_dependencies` applique un **parcours en largeur** (BFS).

- En mode `fanin`, on part du `target` et remonte vers le `source`.
- En mode `fanout`, on part du `source` et avance vers le `target`.
- Les nœuds déjà visités sont mémorisés pour gérer les cycles.
- Les profondeurs et le nombre d'arêtes sont bornés.
- Le résultat contient `visited_nodes`, `edges`, `truncated`
  et les avertissements du graphe d'origine.

Il ne s'agit pas d'un simulateur : le BFS sait quels liens sont
représentés, pas si une condition sera satisfaite pendant une exécution.

## 5. Précautions scientifiques

Le graphe est **conservateur** et ne prétend pas être complet :

1. Les expressions `NamedValue`, `BinaryOp`, `UnaryOp`,
   `Conversion`, `ConditionalOp`, `ElementSelect` et quelques
   variantes simples sont prises en charge.
2. Les `case`, fonctions, tâches, tableaux et
   `generate` complexes ne sont pas traités exhaustivement.
3. Les accès à un bit sont rapprochés du signal entier. Des
   chemins peuvent apparaître alors qu'ils ne concernent pas le
   même bit : c'est un **sur-ensemble** potentiel.
4. Une fonction inconnue ou un nœud non reconnu doit produire
   un avertissement ; ces cas peuvent également rendre le graphe
   **incomplet**.
5. Un lien `port_input` ne prouve pas que la logique interne utilise
   effectivement son entrée.
6. Aucun calcul de timing, preuve formelle, simulation ni conclusion
   sur le comportement de sécurité n'est réalisé.

**Règle : si le rapport a des `warnings`, ne pas le présenter
comme une analyse exhaustive. Même sans avertissement, la couverture
fonctionnelle reste bornée à ce sous-ensemble d'AST.**

## 6. Que tester avant de passer sur des processeurs ?

Les tests automatisés vérifient les liens sur le circuit
`examples/dependencies` à partir du **vrai slang** :

- dépendance combinatoire `a, b → and_result → y` ;
- choix conditionnel `sel → y` ;
- connexions `parent → child` et `child → parent` ;
- lecture/écriture de `count` dans `always_ff` ;
- contrôle par `enable` et `rst_n` ;
- événements `PosEdge` / `NegEdge` ;
- BFS `fanin` / `fanout` et cycles.

La prochaine itération sera d'élargir l'AST couvert,
de tracer les sélections de bits avec davantage de précision et de
réaliser des tests sur des modules RISC-V autorisés.

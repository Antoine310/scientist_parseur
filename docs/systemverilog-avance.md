# Tutoriel : analyser les constructions SystemVerilog avancées

> **Version du parseur :** jalon suivant la phase C, validé avec la sortie JSON
> du compilateur **slang v12.1**. Nous ne réécrivons pas le parser SystemVerilog.
> Le graphe est utile pour la **navigation des influences possibles**, pas une
> preuve de correction du circuit.

Ce cours montre comment [`rtlprep/dependencies.py`](../rtlprep/dependencies.py)
traite désormais quatre familles de constructions : **`case`**,
**concaténation**, **sélection de bits/plages** et **blocs `generate if` élaborés**.

## 1 — Exécuter l'exemple

```bash
python -m rtlprep deps examples/advanced/design.json --out reports/advanced
python -m rtlprep trace reports/advanced/rtl_dependencies.json \
    fanin advanced_logic.result --depth 3
python -m rtlprep trace reports/advanced/rtl_dependencies.json \
    fanin advanced_logic.picked --depth 3
python -m json.tool reports/advanced/rtl_dependencies.json
```

Les exemples utilisent le fichier
[`examples/advanced/advanced_logic.sv`](../examples/advanced/advanced_logic.sv).
Le manifeste choisit le module top `advanced_logic` et les **valeurs par
défaut** de ses paramètres `WIDTH=8` et `USE_XOR=1`.

La CI lance **slang v12.1** sur ce circuit et compare les arêtes à celles
attendues. Exécuter `deps` exige slang installé ; interroger le JSON
avec `trace` n'en a pas besoin.

## 2 — Comprendre le `case`

### Le RTL

```systemverilog
always_comb begin
    case (sel)
        2'b00: result = merged;
        2'b01: result = data_a;
        default: result = data_b;
    endcase
end
```

Le graphe doit distinguer deux types d'influence :

- **Données** : `merged → result`, `data_a → result`, `data_b → result`.
- **Contrôle** : `sel → result`, car le sélecteur détermine quelle
  branche est active.

Les trois valeurs de données ne modifient pas nécessairement
`result` **simultanément**. Le graphe montre ce qui **peut**
influencer le résultat suivant les conditions.

### Ce que slang fournit

L'AST élaboré contient un objet similaire à :

```text
ProceduralBlock(AlwaysComb)
└─ Block
   └─ Case
      ├─ expr: NamedValue(sel)
      ├─ items
      │  ├─ expressions: [Conversion(IntegerLiteral(0))]
      │  │  stmt: Assignment(result, merged)
      │  └─ expressions: [Conversion(IntegerLiteral(1))]
      │     stmt: Assignment(result, data_a)
      └─ defaultCase: Assignment(result, data_b)
```

Ce schéma est **pédagogique** : il omet les métadonnées de source et des
enveloppes `ExpressionStatement`.

### L'algorithme

Dans `statements`, lorsque `kind == "Case"` :

1. on extrait les références de `expr`, le sélecteur `sel` ;
2. on extrait les références présentes dans les **étiquettes** des branches
   (elles peuvent elles-mêmes être des expressions variables) ;
3. on ajoute ces références aux conditions de contrôle pour chaque branche,
   y compris la branche `defaultCase` ;
4. on traite les instructions de chaque branche comme des affectations
   conditionnelles.

La variante `condition == "Normal"` est prise en charge par les tests.
Les formes à correspondances spéciales (certaines variantes de
`casez`/`casex`) produisent un **avertissement** ; la sémantique complète
de ces comparaisons n'est pas encore validée.

## 3 — Comprendre la concaténation

### Le RTL

```systemverilog
assign merged = {data_a[WIDTH-1:4], data_b[3:0]};
```

On assemble les quatre bits hauts de `data_a` avec les quatre bits bas de
`data_b`. Le graphe enregistre donc :

```text
data_a ─┐
        ├──► merged
data_b ─┘
```

### L'AST réel

La version slang testée fournit :

```text
ContinuousAssign
└─ Assignment
   ├─ left: NamedValue(merged)
   └─ right: Concatenation
      └─ operands
         ├─ RangeSelect(value=NamedValue(data_a), left=WIDTH-1, right=4)
         └─ RangeSelect(value=NamedValue(data_b), left=3, right=0)
```

**Détail décisif :** dans slang v12.1, les éléments de la concaténation se
trouvent dans **`operands`** (pas `elements`).

Le code `reads` visite chaque opérande, rassemble les noms de signaux
et crée des arêtes de type `data`. Si `operands` est absent,
il produit un **warning** et ne prétend pas avoir compris l'expression.

## 4 — Sélectionner un bit avec un indice variable

### Le RTL

```systemverilog
assign picked = data_a[idx];
```

La valeur de `picked` dépend :

- de `data_a` : c'est le vecteur lu ;
- de `idx` : c'est l'indice qui choisit le bit.

Le graphe crée donc deux arêtes de données :

```text
data_a ─┐
        ├──► picked
idx ────┘
```

slang fournit un `ElementSelect` avec `value` et `selector`.
Pour les plages `[msb:lsb]`, il fournit un `RangeSelect` avec
`value`, **`left`** et **`right`**.

Le code parcourt tous ces éléments et enregistre les noms de signaux.
Cela suffit à savoir **quels vecteurs/indices** interviennent, mais pas
**quels bits précis** de chaque vecteur alimentent la destination.

### Pourquoi garder un avertissement ?

Dans `rtl_dependencies.json`, l'outil ajoute :

```json
{
  "context": "advanced_logic",
  "reason": "Sélection de bits/plage : dépendance au signal entier"
}
```

Cet avertissement est **attendu** sur cet exemple.
Un fan-in au niveau du vecteur peut contenir davantage de chemins
qu'un fan-in exact au niveau des bits.

Les **affectations vers un bit sélectionné** (`x[idx] = ...`) ne sont
pas encore décrites précisément ; elles doivent aussi être traitées
comme approximatives ou non prises en charge.

## 5 — Paramètres et `generate if`

### Le RTL

```systemverilog
module advanced_logic #(
    parameter int WIDTH = 8,
    parameter bit USE_XOR = 1'b1
) (...);

generate
    if (USE_XOR) begin : gen_logic
        assign mode_result = data_a ^ data_b;
    end else begin : gen_logic
        assign mode_result = data_a | data_b;
    end
endgenerate
```

**Le paramètre est résolu pendant l'élaboration**, avant que
RTLPrep ne voie l'AST.

Pour la configuration par défaut `USE_XOR=1`, slang fournit un
`GenerateBlock` actif contenant l'affectation `data_a ^ data_b`.

Notre code :

1. descend dans le champ `members` du `GenerateBlock` actif ;
2. traite ses `ContinuousAssign` et procédures comme si elles étaient
   à ce niveau hiérarchique ;
3. saute un bloc explicitement marqué `isUninstantiated = true`.

Cela signifie que `mode_result` est relié à `data_a` et
`data_b` dans le circuit **effectivement élaboré**.

### Un paramètre n'est pas un signal de simulation

Dans l'expression `data_a[WIDTH-1:4]`, slang peut exporter
`WIDTH` comme un `NamedValue` avec un champ `constant`.
Si ce nom n'est pas un signal indexé, le code le traite comme une
**constante de compilation**, et non comme une entrée RTL dont la valeur
change à l'exécution.

Pour tester **l'autre branche**, le projet fournit aussi
[`examples/advanced/alternative_design.json`](../examples/advanced/alternative_design.json)
avec un module parent `alternative_top` qui instancie
`advanced_logic #(.WIDTH(8), .USE_XOR(1'b0))`. La CI vérifie alors
que le compilateur choisit **`BinaryOr`**, pas `BinaryXor`, et que
les dépendances arrivent au bon chemin d'instance
`alternative_top.dut.mode_result`.

```bash
python -m rtlprep deps examples/advanced/alternative_design.json --out reports/alternate
```

**Limite :** on n'a pas encore de gestion générique et exhaustive
des paramètres et spécialisations pour tous les modules, boucles
`for generate`, packages et interfaces. Un simple `generate if`
élaboré dans ce circuit est pris en charge ; cela ne valide pas
toutes les structures `generate` existantes.

## 6 — Les tests de régression

Pour exécuter tous les tests Python :

```bash
python -m pytest -q
```

Les tests suivants ne nécessitent aucun compilateur :

```bash
python -m pytest -v tests/test_advanced_dependencies.py
```

Ils vérifient également :

- qu'un `case` avec étiquettes variables conserve les dépendances
  de contrôle ;
- qu'une concaténation malformée n'invente pas de dépendances ;
- qu'un `generate` inactif ne crée pas d'arêtes parasites ;
- que `WIDTH`, paramètre constant, ne devient pas un faux signal ;
- que le rapport signale l'approximation des sélections de bits.

Les tests d'intégration dans
[`tests/test_integration_slang.py`](../tests/test_integration_slang.py)
font de même sur **le vrai SystemVerilog élaboré par slang**.
Ils sont sautés si l'outil est absent localement, mais GitHub Actions
installe le compilateur pour les exécuter réellement.

## 7 — Ce que cette étape **ne** résout **pas**

RTLPrep n'est pas encore prêt à explorer **sans limites** un SoC complexe :

- la précision reste **au niveau du signal**, pas de chaque bit ;
- les blocs `generate` imbriqués, les boucles et les noms hiérarchiques
  générés ne sont pas encore entièrement indexés ;
- les appels de fonctions, les tâches, certains opérateurs, les références
  croisées et les interfaces requièrent une prise en charge supplémentaire ;
- les `casez`/`casex` ne sont pas entièrement modélisés ;
- aucune preuve formelle de dépendance ou de comportement n'est produite.

**La prochaine étape recommandée :** un sous-module CPU RISC-V réel et
autorisé, puis l'ajout progressif des constructions AST rencontrées,
avec un test d'intégration par fonctionnalité nouvelle.

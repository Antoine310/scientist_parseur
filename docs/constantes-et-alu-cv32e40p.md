# Constantes SystemVerilog et premier test sur l'ALU réelle du CV32E40P

**État expérimental : 20 novembre 2026 · slang v12.1 · CV32E40P officiel.**

Ce chapitre explique deux progrès liés :

1. **Distinguer les constantes compilées** (`parameter`, valeurs d'`enum`)
   des vrais signaux RTL **sans filtrer par nom**.
2. **Vérifier RTLPrep sur une ALU RISC-V réelle**, beaucoup plus dense que
   le décodeur compressé testé à l'étape précédente.

Le compilateur/élaborateur reste **slang** : RTLPrep n'interprète pas
directement toute la grammaire SystemVerilog.

## 1. Le problème découvert sur le décodeur RISC-V

Lors du premier test du décodeur compressé, RTLPrep signalait notamment :

```text
Référence NamedValue inconnue : 'OPCODE_JAL'
Référence NamedValue inconnue : 'OPCODE_OPIMM'
Référence NamedValue inconnue : 'ZFINX'
```

Pourtant, ces symboles ne sont pas des signaux cachés :

- `OPCODE_JAL` et `OPCODE_OPIMM` sont des **paramètres du package**
  `cv32e40p_pkg` ;
- `ZFINX` est un **paramètre d'élaboration** du module.

Écrire `if name.startswith("OPCODE_")` aurait été une erreur :
un vrai signal pourrait aussi porter ce préfixe, et des constantes
pourraient être appelées autrement. **Nous voulons une identification
sémantique, pas un filtrage de texte.**

## 2. Comment slang permet de reconnaître les constantes

Lors de l'élaboration, slang résout les références vers des déclarations.
Dans son export JSON v12.1, chaque déclaration possède un identifiant
`addr` et les expressions qui la référencent contiennent une valeur
`symbol` comportant cet identifiant et un nom lisible.

**Extrait illustratif** (adresses fictives ; les nombres changent à
chaque exécution) :

```json
{
  "kind": "Parameter",
  "name": "OPCODE_JAL",
  "addr": 12345,
  "value": "7'b1101111"
}
```

Dans une expression :

```json
{
  "kind": "NamedValue",
  "symbol": "12345 OPCODE_JAL"
}
```

Le programme compare l'identifiant `12345` à celui de la
déclaration, au sein **du même AST**.

### 2.1 Le cas des paramètres

Le package apparaît dans le vrai AST comme suit :

```text
Root
└── CompilationUnit
    └── Package cv32e40p_pkg
        ├── Parameter OPCODE_OPIMM
        ├── Parameter OPCODE_BRANCH
        ├── Parameter OPCODE_JAL
        └── ...
```

Les paramètres du module (`FPU`, `ZFINX`) se trouvent également
dans son `InstanceBody` élaboré.

Dans `build_dependency_graph`, le code parcourt l'AST et collecte les
identifiants de toutes les déclarations `Parameter` effectivement
présentes. Si une référence `NamedValue` pointe vers un tel identifiant,
elle ne devient **pas** un nœud de signal dynamique.

### 2.2 Le cas des valeurs d'énumération

Sur l'ALU réelle, les noms `ALU_ADD`, `ALU_SUB`, `ALU_AND`
proviennent d'une **énumération**, pas de déclarations `Parameter`.

slang exporte des nœuds de ce type :

```text
Package cv32e40p_pkg
└── EnumType alu_opcode_e
    ├── EnumValue ALU_ADD
    ├── EnumValue ALU_SUB
    ├── EnumValue ALU_AND
    └── ...
```

Chaque `EnumValue` possède aussi un `addr`. Nous collectons donc
**les identifiants des `Parameter` et des `EnumValue`**.

### 2.3 Ce que fait exactement notre code

Dans [`rtlprep/dependencies.py`](../rtlprep/dependencies.py) :

```python
if obj.get("kind") in ("Parameter", "EnumValue") and obj.get("addr") is not None:
    constant_declarations[str(obj["addr"])] = (
        obj["kind"], str(obj.get("name", ""))
    )
```

Lorsqu'une expression `NamedValue` est analysée, on lit
la première partie de son champ `symbol` (l'identifiant) :

```python
symbol = expr.get("symbol")
reference_id = symbol.split(maxsplit=1)[0] if isinstance(symbol, str) else None
if reference_id in constant_declarations:
    constant_refs_seen.add(reference_id)
    return None
```

Ici, `None` signifie « **pas un signal à ajouter au graphe** »,
pas « expression inconnue ». Les constantes de compilation sont
déjà résolues par slang.

En revanche, une référence dont l'identifiant est inconnu
**continue de générer un avertissement** : nous ne l'ignorons pas
sous prétexte que son nom commence par `ALU_` ou `OPCODE_`.

### 2.4 Un piège subtil : deux déclarations du même nom

Supposons un signal `a` et une valeur d'énumération `a` dans des
portées différentes. Une heuristique sur le nom les confondrait.
Les **identifiants sémantiques distincts** permettent à RTLPrep de
ne pas effacer une vraie arête de donnée par accident.

Les tests unitaires ajoutés couvrent explicitement :

- un paramètre de package dont le nom est identique à celui d'un signal ;
- une valeur d'énumération homonyme d'un signal ;
- un nom `OPCODE_UNKNOWN` non déclaré, qui doit **rester un warning**.

Les identifiants internes sont valides **pendant la lecture d'un AST** ;
ils ne sont jamais enregistrés comme clés stables entre plusieurs
compilations (ils peuvent changer d'une exécution à l'autre).

## 3. Expérience sur deux modules RISC-V réels

Les deux expériences utilisent le **dépôt officiel OpenHW** :

- dépôt : [openhwfoundation/cv32e40p](https://github.com/openhwfoundation/cv32e40p) ;
- commit : `b353438ff469c030c89f6804f3b24a2852880e8b` ;
- environnement : **Ubuntu 24.04 / Python 3.11 / slang 12.1.0** ;
- les fichiers sources sont vérifiés par **empreintes Git blob** avant
  toute analyse ;
- aucun code du processeur n'est recopié dans le dépôt RTLPrep.

La validation tourne automatiquement dans les workflows :

- [décodeur compressé](../.github/workflows/cv32e40p-real.yml) ;
- [ALU du CV32E40P](../.github/workflows/cv32e40p-alu-real.yml).

### 3.1 Le décodeur compressé : 12 → 1 avertissement

| Mesure | Avant la reconnaissance sémantique | Après |
| --- | ---: | ---: |
| Compilation slang | Réussie | Réussie |
| Instances | 1 | 1 |
| Nœuds du graphe | 4 | 4 |
| Arêtes de dépendance | 4 | 4 |
| **Avertissements** | **12** | **1** |

Le dernier avertissement est **volontaire** : les sélections de
bits/plages sont encore agrégées au **vecteur entier**.

Le script vérifie désormais que `OPCODE_JAL`,
`OPCODE_OPIMM` et `ZFINX` sont associés à de véritables
déclarations du compilateur. Si la correspondance est perdue,
le test doit échouer.

### 3.2 L'ALU complète : 71 → 11 avertissements

L'ALU CV32E40P dépend notamment de :

```text
cv32e40p_alu
├── popcnt_i  → cv32e40p_popcnt
├── ff_one_i → cv32e40p_ff_one
└── alu_div_i → cv32e40p_alu_div
```

L'AST réel contient donc **quatre instances** et de nombreuses
affectations combinatoires et séquentielles.

| Mesure | Résultat obtenu |
| --- | ---: |
| Compilation et élaboration slang | **Réussies** |
| Modules / instances | **4 / 4** |
| Déclarations indexées | **149** |
| Nœuds du graphe | **149** |
| **Arêtes** | **319** |
| `data` | 188 |
| `control` | 98 |
| `event` | 16 |
| `port_input` / `port_output` | 12 / 5 |
| Avertissements avant résolution des énumérations | **71** |
| **Avertissements après résolution** | **11** |

**Interprétation :** les 319 arêtes sont des relations
entre **signaux entiers**, dédupliquées par catégorie et destination ;
elles ne correspondent pas au nombre d'instructions SystemVerilog ni
à 319 opérations logiques physiques.

Les avertissements restants incluent :

- les `Call` (certaines fonctions système ou appels) non interprétés ;
- les accès à des **bits/plages**, agrégés au signal entier ;
- certaines affectations vers des sélections de bits (approximation).

La qualification scientifique reste **`partial`** :
l'ALU a été compilée et explorée, mais **l'exhaustivité des influences
n'est pas prouvée**.

### 3.3 Trois requêtes de dépendances réelles

RTLPrep remonte le fan-in de ces sorties :

- `result_o` : le parcours retrouve `operand_a_i`,
  `operand_b_i` et `operator_i` ;
- `comparison_result_o` : il retrouve aussi ces trois entrées ;
- `ready_o` : le parcours décrit une autre partie des signaux
  de contrôle et n'est pas censé avoir les mêmes influences.

Ces résultats montrent que la hiérarchie et les connexions
inter-modules sont exploitables. **Ils ne prouvent pas que
tous les chemins fonctionnels possibles ont été recensés.**

## 4. Reproduire les tests chez soi

Avec slang installé, depuis la racine de RTLPrep :

```bash
git clone https://github.com/openhwfoundation/cv32e40p.git upstream_cv32e40p
git -C upstream_cv32e40p checkout b353438ff469c030c89f6804f3b24a2852880e8b

python -m pip install -e '.[dev]'

# Décodeur compressé
python scripts/run_cv32e40p_decoder.py \
    --source-root upstream_cv32e40p \
    --out reports/cv32e40p

# ALU, trois sous-modules et package SystemVerilog
python scripts/run_cv32e40p_alu.py \
    --source-root upstream_cv32e40p \
    --out reports/cv32e40p-alu

# Explorer un résultat (sans relancer le compilateur)
python -m rtlprep trace reports/cv32e40p-alu/rtl_dependencies.json \
    fanin cv32e40p_alu.result_o --depth 12

python -m pytest -q
```

Le rapport principal du second test est :

```text
reports/cv32e40p-alu/cv32e40p_alu_test_report.json
```

Il contient : sources et empreintes, version du compilateur, modules,
ports, hiérarchie, nombres de nœuds/arêtes, types d'arêtes,
avertissements et sorties de fan-in.

Le workflow GitHub Actions conserve aussi les rapports JSON et
les logs pendant **14 jours** comme artefacts du run.

## 5. Les tests de non-régression

Les scripts de benchmark réels ne se contentent pas d'un
`slang` avec code de retour 0.

Le décodeur doit retrouver les trois sorties à partir
de `instr_i`, ainsi que plusieurs symboles de paramètres.

Pour l'ALU, le script contrôle notamment :

- quatre instances de la hiérarchie attendue ;
- un graphe non vide et au moins 300 arêtes sur la révision fixe ;
- la résolution de l'énumération `ALU_ADD` ;
- l'absence de références `NamedValue` restées inconnues ;
- les influences de `operand_a_i`, `operand_b_i`
  et `operator_i` dans le fan-in de `result_o`
  et `comparison_result_o` ;
- les limites de traversée (un résultat tronqué est signalé).

Ces contrôles protègent contre un **faux succès** où la compilation
fonctionne mais le graphe n'analyse presque rien.

## 6. Prochaine limite à lever

La prochaine priorité logique est de traiter proprement les
**appels de fonctions système** tels que les conversions et
fonctions standard, en s'appuyant toujours sur le schéma
AST réellement produit par slang.

Ensuite : affiner la précision **bit à bit**, puis
comparer les résultats avec un banc de simulation ou des propriétés
formelles. Une absence de warning n'est **jamais** une preuve
fonctionnelle d'absence de bug.

Cette progression reste compatible avec notre règle :
**outils EDA open source, code Python auditable et aucun coût d'API LLM requis.**

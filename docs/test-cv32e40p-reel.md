# Premier test sur du vrai RTL RISC-V : CV32E40P

**Expérience reproductible, réalisée le 20 novembre 2026.**
Ce test utilise le **vrai décodeur d'instructions compressées** du cœur
RISC-V open source CV32E40P. Il ne s'agit ni d'un exemple recopié à la main
ni d'un circuit inventé pour favoriser notre analyseur.

> Résultat principal : **le compilateur slang a réussi** et RTLPrep a extrait
> les dépendances de `instr_i` vers les trois sorties. **L'analyse du graphe
> reste partielle** : 12 avertissements doivent encore être traités.
> Une compilation réussie ne vaut pas preuve de correction fonctionnelle.

## 1. D'où viennent les véritables fichiers RTL ?

- Dépôt officiel : [openhwfoundation/cv32e40p](https://github.com/openhwfoundation/cv32e40p).
- Révision Git exacte : `b353438ff469c030c89f6804f3b24a2852880e8b`.
- Fichier testé : `rtl/cv32e40p_compressed_decoder.sv`.
- Dépendance de compilation : `rtl/include/cv32e40p_pkg.sv` (package).
- Top : `cv32e40p_compressed_decoder`.
- Outil : **slang 12.1.0**.
- Environnement de test : **Ubuntu 24.04, Python 3.11, GitHub Actions**.

Le projet amont est distribué sous une licence matérielle open source
Solderpad. RTLPrep ne réintègre pas les sources amont dans son propre dépôt :
le workflow télécharge de façon **temporaire** les deux fichiers à leur
révision Git exacte, puis vérifie leurs hash Git blob originaux avant
d'utiliser le compilateur.

Le workflow réutilisable est
[`.github/workflows/cv32e40p-real.yml`](../.github/workflows/cv32e40p-real.yml).

## 2. Pourquoi ce sous-module est-il intéressant ?

Un processeur RISC-V peut contenir des instructions **compressées**
de 16 bits. Le décodeur étudié les transforme, lorsque cela est pertinent,
en une représentation d'instruction 32 bits.

Son interface compte **quatre ports** :

| Port | Direction | Sens approximatif |
| --- | --- | --- |
| `instr_i` | Entrée | Mot d'instruction à interpréter |
| `instr_o` | Sortie | Représentation de l'instruction décodée |
| `is_compressed_o` | Sortie | Indication du format compressé |
| `illegal_instr_o` | Sortie | Indication d'une instruction compressée invalide |

Le module utilise des `case` imbriqués, des expressions conditionnelles,
des constantes du package et des concaténations avec sélection de bits.
C'est un **test représentatif de parsing/elaboration** bien plus exigeant
qu'un simple compteur.

## 3. Reproduire exactement le test

Depuis la racine de RTLPrep :

```bash
git clone https://github.com/openhwfoundation/cv32e40p.git upstream_cv32e40p
git -C upstream_cv32e40p checkout b353438ff469c030c89f6804f3b24a2852880e8b

python -m pip install -e '.[dev]'
slang --version

python scripts/run_cv32e40p_decoder.py \
    --source-root upstream_cv32e40p \
    --out reports/cv32e40p
```

Si les dépendances ne sont pas installées, voir
[le tutoriel d'installation de slang](slang-environnement.md).
Le script refuse de prétendre tester la révision épinglée si le contenu
des fichiers a changé : il vérifie directement leurs empreintes Git blob.

GitHub Actions exécute ces mêmes étapes **sans intervention manuelle**.
Les rapports JSON et logs de compilation sont disponibles comme
artefacts du workflow pendant sa durée de conservation (14 jours).

## 4. Résultats réellement observés

Lors du test sur la révision épinglée, avant les futures évolutions :

| Vérification | Résultat |
| --- | --- |
| Compilation/élaboration slang | **Réussie** |
| Analyse RTLPrep et génération de l'index | **Réussie** |
| Définitions de modules instanciés | 1 |
| Instances | 1 |
| Déclarations de signaux indexées | 4 |
| Nœuds du graphe | **4** |
| Arêtes orientées | **4** |
| Arêtes `data` | 2 |
| Arêtes `control` | 2 |
| Avertissements de couverture | **12** |
| `instr_i` influence potentiellement `instr_o` | Oui |
| `instr_i` influence potentiellement `is_compressed_o` | Oui |
| `instr_i` influence potentiellement `illegal_instr_o` | Oui |

Le nombre d'arêtes est **très inférieur** au nombre d'affectations et
de branches dans le RTL original. C'est normal avec le schéma actuel :
les dépendances sont **agrégées par nom de signal et catégorie d'arête**.
Cela ne signifie pas que le décodeur n'a que quatre opérations.

**La qualification du résultat est « couverture partielle ».** En
particulier, `passed` signifie que slang et le générateur du graphe se
sont exécutés correctement, pas que le graphe représente sans omission
le comportement du décodeur.

## 5. Deux incompatibilités découvertes — et corrigées

### 5.1 Les blocs d'instructions `List`

Le premier lancement du test produisait un graphe de **1 seule arête**,
avec l'avertissement :

```text
Instruction non prise en charge : List
```

Pourquoi ? Le décodeur réel contient un `begin ... end` avec plusieurs
instructions. Le JSON de slang v12.1 les représente par :

```json
{
  "kind": "List",
  "list": [
    {"kind": "ExpressionStatement"},
    {"kind": "ExpressionStatement"},
    {"kind": "Case"}
  ]
}
```

Notre `statements()` ne reconnaissait pas ce nœud, donc il ne
descendait même pas dans le grand `case` de décodage.

**Correction :** parcourir `obj["list"]` récursivement.
Un nœud `List` malformé produit maintenant un avertissement.
Des tests unitaires reproduisent cette structure.

### 5.2 La répétition de bits `Replication`

Le code source comporte des constructions de type :

```systemverilog
{6{instr_i[12]}}
```

Dans le JSON réel, slang v12.1 les décrit par :

```text
Replication
├── count: IntegerLiteral(6)
└── concat: Concatenation
    └── operands: [ElementSelect(value=instr_i, selector=12)]
```

Le graphe reconnaît désormais cette construction et suit la lecture
de `instr_i`. Il ne transforme pas le nombre de répétitions en
un signal dynamique fictif. Un cas `Replication` malformé est
signalé dans les avertissements et couvert par un test unitaire.

## 6. Pourquoi reste-t-il des avertissements ?

La majorité des avertissements actuels sont des références à des
**constantes du package** (`OPCODE_JAL`, `OPCODE_LOAD`,
`OPCODE_BRANCH`, etc.) que notre index de signaux ne classe pas
encore comme objets constants de package.

Une autre référence de paramètre (`ZFINX`) est également signalée.
Enfin, les `ElementSelect` et `RangeSelect` restent représentés
à la **granularité du vecteur entier**, et non bit à bit.

Les avertissements sont volontairement **préservés**, car supprimer
toutes les valeurs inconnues par une simple règle textuelle
pourrait masquer de vraies dépendances non résolues.

Important : **12** est ici le nombre de catégories/messages
d'avertissement dédupliqués par notre graphe, et **non** le nombre
exact d'instructions non analysées.

## 7. Comprendre `scripts/run_cv32e40p_decoder.py`

Ce fichier prépare et exécute l'expérience en plusieurs étapes :

1. **Vérifier les fichiers réels** : existence et empreintes Git des
   sources récupérées depuis le commit amont fixé.
2. **Créer un manifeste** `cv32e40p_design.json` : le package est
   placé avant le décodeur, comme l'exige la dépendance de compilation.
3. **Charger le design** avec `load_design()`.
4. **Lancer le vrai compilateur** via `dependency_design()` : slang
   produit l'AST ; les modules RTLPrep produisent index et graphe.
5. **Contrôler les ports** : quatre ports attendus et directions correctes.
6. **Exiger une influence potentielle d'`instr_i` vers chaque sortie**
   dans le graphe ; une disparition silencieuse de ces relations
   échoue désormais au test.
7. **Enregistrer un rapport** contenant les versions, sources, sommes
   SHA-256, comptes, dépendances, limites et avertissements.

Les fichiers principaux sont :

```text
reports/cv32e40p/
├── cv32e40p_design.json
├── elaborated_ast.json
├── rtl_index.json
├── rtl_dependencies.json
├── cv32e40p_test_report.json
├── analyze.result.json
├── index.result.json
├── deps.result.json
├── analyze.stdout.log
└── analyze.stderr.log
```

Ces rapports sont générés à chaque exécution et **ne sont pas des
résultats inventés par un LLM**. Les fichiers lourds de l'AST sont
conservés dans l'espace d'exécution ; l'artefact GitHub publié
contient les résultats synthétiques et les journaux utiles.

## 8. Ce que nous savons — et ce qu'il faudra faire ensuite

**Prouvé par l'expérience :** RTLPrep sait analyser le vrai SystemVerilog
de ce sous-module CV32E40P avec slang v12.1, reconnaître ses ports,
et suivre une influence possible de l'entrée instruction vers les
trois sorties.

**Pas prouvé :** l'absence d'oubli dans le graphe, la correction du
décodeur, le comportement sur toutes les instructions, les connexions
d'un cœur complet ou les propriétés de sécurité du CPU.

**Travail suivant recommandé :** reconnaître proprement les
constantes importées des packages depuis les structures sémantiques
du compilateur, étendre les tests à des **signaux internes** et
mesurer la précision des dépendances sur une nouvelle IP du processeur,
comme un sous-ensemble de l'ALU.

Cette distinction entre **succès de compilation** et **complétude
de l'analyse** est essentielle pour que RTLPrep fournisse plus tard
des résultats fiables à Codex ou à un agent de vérification.

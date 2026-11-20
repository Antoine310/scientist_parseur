# PR #14 — Première équivalence EQY sur un véritable sous-module RISC-V

**Expérience confirmée le 20 novembre 2026** avec l'OSS CAD Suite
`2026-11-18`, Yosys et **EQY v0.71**. Le module étudié est
`cv32e40p_popcnt`, provenant du **vrai dépôt CV32E40P OpenHW**.

> **Résultat :** refactorisation démontrée équivalente sur **31 partitions** ;
> mutant volontairement incorrect déclaré non équivalent, avec
> **contre-exemple VCD**. C'est une preuve d'équivalence *entre deux
> versions RTL précises*, pas une preuve que le CPU complet fonctionne.

## 1. Qu'est-ce que « popcount » ?

Le bloc `cv32e40p_popcnt` compte le nombre de bits à `1`
dans une entrée `in_i` de **32 bits**. Sa sortie `result_o` est
sur **6 bits**, car le résultat va de 0 à 32.

```text
in_i[31:0] ──► étage de paires ──► sommes intermédiaires ──► result_o[5:0]
                 16 additions      8 + 4 + 2 + 1 additions
```

Le code officiel est organisé en quatre étages `generate for` :

- 16 compteurs locaux sur des paires de bits ;
- puis 8 sommes partielles ;
- puis 4 ;
- puis 2 ;
- enfin l'addition des deux résultats de la dernière étape.

Ce circuit est intéressant pour EQY, car il combine des **tableaux
packed multi-dimensionnels**, des **boucles generate** et plusieurs
étages d'opérations arithmétiques.

## 2. Des sources OpenHW originales et épinglées

Le workflow ne copie **pas** le RTL du processeur dans RTLPrep.

- Dépôt officiel : [openhwfoundation/cv32e40p](https://github.com/openhwfoundation/cv32e40p).
- Commit utilisé : `b353438ff469c030c89f6804f3b24a2852880e8b`.
- Fichier officiel : `rtl/cv32e40p_popcnt.sv`.
- Git blob d'origine : `c7fe53e810c411a4cef0ab6ae8591b9e54e652f9`.
- Empreinte SHA-256 du fichier original :
  `7a2dbeded21929832b40fc8d068b35b7281c75a63c426feed207127d4da08e4e`.
- Licence amont : Solderpad Hardware License v0.51 (voir
  les en-têtes et conditions dans le dépôt officiel).

Le workflow
[`.github/workflows/cv32e40p-popcnt-eqy.yml`](../.github/workflows/cv32e40p-popcnt-eqy.yml)
récupère **seulement le fichier nécessaire** par sparse checkout,
vérifie la révision et le blob Git avant de lancer Yosys.

Le script
[`scripts/run_cv32e40p_popcnt_eqy.py`](../scripts/run_cv32e40p_popcnt_eqy.py)
effectue à nouveau ces contrôles, puis crée les variantes localement
dans `reports/`, dossier ignoré par Git.

Les transformations sont **interdites si la ligne d'origine ne
correspond pas exactement** à celle du commit épinglé.

## 3. Expérience n°1 : transformer le RTL sans changer le résultat

Dans l'original, la dernière addition ressemble à :

```systemverilog
assign result_o = {1'b0, cnt_l4[0]} + {1'b0, cnt_l4[1]};
```

La variante refactorisée échange les deux opérandes :

```systemverilog
assign result_o = {1'b0, cnt_l4[1]} + {1'b0, cnt_l4[0]};
```

**Pourquoi penser que c'est équivalent ?** L'addition est
commutative : `a + b = b + a`. Toutefois, l'intérêt est de laisser
**EQY vérifier le véritable circuit élaboré**, avec ses largeurs,
ses étages `generate` et ses partitions.

Résultat observé avec le vrai EQY :

```text
status: passed
equivalent: true
partitions: 31
```

EQY a réussi les **31 partitions générées** pour cette paire de
modèles. Cela correspond à **une refactorisation très locale**,
et non à une transformation sophistiquée du CPU.

## 4. Expérience n°2 : introduire volontairement une erreur

Le candidat erroné est obtenu par **une seule substitution** :

```systemverilog
assign result_o = {1'b0, cnt_l4[0]} - {1'b0, cnt_l4[1]};
```

Ce calcul n'est plus équivalent à la somme d'origine quand le
deuxième terme est non nul.

Résultat observé :

```text
status: failed
equivalent: false
partitions: 31
counterexample: strategies/cv32e40p_popcnt.result_o/.../trace.vcd
```

La trace VCD du moteur SMT représente une entrée ou
séquence d'entrées pour laquelle les deux versions
peuvent produire des résultats différents.
Le workflow vérifie **trois éléments indépendants** avant
d'accepter une non-équivalence :

1. le verdict global EQY est `FAIL` ;
2. une partition a été marquée `FAIL` ;
3. un véritable fichier `trace*.vcd` existe.

Sans ces preuves, le programme renvoie `inconclusive`
ou `error` au lieu de prétendre qu'un bug a été démontré.

**Règle de lecture :** le `FAIL` du mutant est une réussite
du *test négatif*, pas une réussite du circuit modifié.

## 5. Reproduire la vérification

Récupérer le vrai RTL OpenHW :

```bash
git clone https://github.com/openhwfoundation/cv32e40p.git upstream_cv32e40p
git -C upstream_cv32e40p checkout b353438ff469c030c89f6804f3b24a2852880e8b

git -C upstream_cv32e40p hash-object rtl/cv32e40p_popcnt.sv
# c7fe53e810c411a4cef0ab6ae8591b9e54e652f9
```

Installer la même OSS CAD Suite que dans GitHub Actions
(`eqy`, `yosys`, `sby`, `z3`) et RTLPrep :

```bash
eqy --version
yosys -V
sby --version
z3 --version
python -m pip install -e '.[dev]'

python scripts/run_cv32e40p_popcnt_eqy.py \
    --source-root upstream_cv32e40p \
    --out reports/cv32e40p-popcnt-eqy \
    --timeout 180
```

Cette **seule commande** crée les deux candidats et effectue
les deux vérifications. Si la version refactorisée n'est pas
prouvée équivalente ou si le mutant n'est pas réfuté avec une trace,
le script échoue.

Le rapport global se trouve dans :

```text
reports/cv32e40p-popcnt-eqy/cv32e40p_popcnt_eqy_report.json
```

Les rapports de chaque expérience sont dans :

```text
reports/cv32e40p-popcnt-eqy/
├── gold.json
├── refactored/
│   ├── cv32e40p_popcnt_refactored.sv
│   ├── gate.json
│   ├── equivalence.eqy
│   ├── equivalence.result.json
│   └── eqy_work/
└── buggy/
    ├── cv32e40p_popcnt_buggy.sv
    ├── gate.json
    ├── equivalence.eqy
    ├── equivalence.result.json
    └── eqy_work/ ... trace.vcd
```

Les **artefacts GitHub Actions** publient les rapports, logs,
verdicts et traces pendant 14 jours.

## 6. Explication de l'implémentation Python

### 6.1 `popcnt_variant()` : une seule transformation contrôlée

Dans [`rtlprep/equivalence.py`](../rtlprep/equivalence.py),
les trois expressions de sortie sont **fixées dans le code** :

```python
POPCNT_ASSIGN = "  assign result_o = {1'b0, cnt_l4[0]} + {1'b0, cnt_l4[1]};"
POPCNT_REFACTORED = "  assign result_o = {1'b0, cnt_l4[1]} + {1'b0, cnt_l4[0]};"
POPCNT_BUGGY = "  assign result_o = {1'b0, cnt_l4[0]} - {1'b0, cnt_l4[1]};"
```

`popcnt_variant()` vérifie que l'expression d'origine
apparaît **exactement une fois**. La variante est alors
construite par une substitution de cette ligne uniquement.

La commande ne réécrit jamais les boucles `generate` et
n'insère jamais une modification générée par LLM sans revue.

### 6.2 `_validate_real_popcnt()` : vérification du contenu, pas du nom

Un script malveillant pourrait créer son propre fichier
`cv32e40p_popcnt.sv` contenant du code totalement différent.
Vérifier uniquement le nom serait insuffisant.

Nous imposons donc :

- un nom de fichier original exact ;
- une empreinte Git blob d'origine exacte ;
- une taille bornée ;
- une variante candidate portant un nom autorisé ;
- les **octets exacts** de la transformation attendue.

Les tests unitaires vérifient les tentatives de remplacer le
fichier `gold`, d'ajouter du code au fichier `gate`
ou de produire un faux candidat avec le bon nom.

Cela forme une **liste blanche d'expériences précises** ;
ce n'est pas une sandbox complète contre tous les risques
de l'exécution d'outils EDA.

### 6.3 `equivalence_check()` : conserver la preuve réelle

Le moteur EQY existant s'occupe de :

- générer le fichier `.eqy` (scripts Yosys prédéfinis) ;
- lancer EQY avec délai maximal ;
- lire les marqueurs `PASS` et `FAIL` ;
- compter les partitions ;
- récupérer les fichiers `trace*.vcd` ;
- enregistrer les versions, durées et empreintes des sources.

Pour la comparaison du vrai popcount, le moteur
`read_verilog -sv` de Yosys a également été **exécuté
avec succès** sur les tableaux packed et les boucles generate
de ce module précis.

La preuve repose sur le **vrai code RTL amont**, et non sur une
maquette Python prétendant reproduire un processeur.

## 7. Ce qu'on peut conclure — et ce qu'on ne peut pas conclure

### Établi par le test

- Yosys sait analyser le vrai `cv32e40p_popcnt` épinglé ;
- EQY démontre l'équivalence de cette refactorisation de sortie ;
- EQY détecte la substitution erronée `+` → `-` ;
- une trace VCD est conservée ;
- les transformations et les fichiers sont vérifiés.

### Pas établi par le test

- la correction du **popcount d'origine** sur toutes les entrées
  par rapport à une **spécification externe indépendante** ;
- l'équivalence de transformations importantes ou de toute l'ALU ;
- la sûreté matérielle globale du CV32E40P ;
- une propriété de timing, de consommation ou de sécurité physique ;
- le support générique de tout RTL tiers par notre premier banc EQY.

Pour éviter un faux sentiment de sécurité : **deux designs
peuvent être parfaitement équivalents et porter le même bug**.

## 8. Notre prochaine étape

Ce test prépare l'intégration **Codex/MCP** de manière responsable :
un agent pourra déclencher des validations approuvées et lire
des preuves JSON **sans inventer leurs résultats**.

Avant d'exposer un design tiers non revu, il faudra renforcer
l'isolation du processus EDA, les limites de ressources et les
règles d'autorisation. La précision des dépendances bit-à-bit
et les appels de fonctions restent également à améliorer.

Cette expérience ne nécessite **aucune API LLM payante**.

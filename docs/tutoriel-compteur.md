# 4 — Travaux pratiques : du compteur SystemVerilog au rapport JSON

**But :** faire une première analyse pas à pas en comprenant ce que chaque commande consomme et produit.

## 4.1 Prérequis

- Git.
- Python 3.10 ou plus récent.
- Pour les essais EDA : slang, Verilator et Yosys installés **séparément** et disponibles dans le `PATH`.
- Linux/WSL2 conseillé pour un premier environnement ; la CLI Python elle-même est multiplateforme.

```bash
git clone https://github.com/Antoine310/scientist_parseur.git
cd scientist_parseur
python -m pip install -e '.[dev]'
python -m pytest -q
```

Sur Windows, le lanceur Python peut s'appeler `py` au lieu de `python`.

Cette installation de paquet ne **télécharge pas** les outils EDA.

## 4.2 Lire le compteur

Dans [examples/counter/counter.sv](../examples/counter/counter.sv) :

```systemverilog
module counter (
    input  logic       clk,
    input  logic       rst_n,
    input  logic       enable,
    output logic [7:0] count
);
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            count <= 8'd0;
        else if (enable)
            count <= count + 8'd1;
    end
endmodule
```

Questions à te poser :

1. Quels sont les trois ports d'entrée et l'unique sortie ?
2. Pourquoi `[7:0]` correspond-il à 8 bits ?
3. Que se passe-t-il lorsque `rst_n == 0` ?
4. Que se passe-t-il sur le front montant de `clk` si `enable == 1` ?
5. Et si `enable == 0` ?

**Réponses :** `clk`, `rst_n`, `enable` ; sortie `count` sur 8 bits ; reset asynchrone actif bas remettant `count` à 0 ; incrémentation de 1 si activé ; sinon le registre conserve sa valeur. Le compteur revient à 0 après 255 par débordement modulo 256.

## 4.3 Lire le manifeste

```json
{
  "top": "counter",
  "sources": ["counter.sv"],
  "include_dirs": [],
  "defines": []
}
```

Ce fichier indique **quoi compiler**, pas **comment doit se comporter le compteur**. Les propriétés de comportement sont dans le RTL et, idéalement, dans une spécification de référence.

## 4.4 Vérifier l'environnement

```bash
python -m rtlprep doctor
```

Interprétation :

- `"slang": "/.../slang"` signifie que l'exécutable est trouvé ;
- `"slang": null` signifie qu'il n'est pas trouvé ;
- `"pyslang": false` n'empêche pas nécessairement `analyze` de fonctionner : cette version utilise la **CLI** `slang`, pas directement `pyslang`.

Si tout est absent, tu peux quand même lire le code et faire tourner les tests unitaires Python.

## 4.5 Générer l'AST et l'inventaire

```bash
python -m rtlprep analyze examples/counter/design.json --out reports/counter
```

Si slang est présent et accepte les options de la commande :

- `reports/counter/elaborated_ast.json` : export de l'AST ;
- `reports/counter/design_summary.json` : inventaire construit par notre code Python ;
- `reports/counter/analyze.result.json` : statut du traitement ;
- `reports/counter/analyze.stdout.log` et `analyze.stderr.log` : sorties de slang.

Commence par lire le **statut** :

```bash
python -m json.tool reports/counter/analyze.result.json
```

Puis, seulement si `passed`, le résumé :

```bash
python -m json.tool reports/counter/design_summary.json
```

Ne suppose pas que le nombre d'instances est exact si la structure JSON de slang diffère de celle prise en charge par `analysis.py`. L'AST complet est le point de référence à inspecter pour corriger l'extracteur.

## 4.6 Effectuer le lint

```bash
python -m rtlprep lint examples/counter/design.json --out reports/counter
```

Ouvre `lint.stderr.log` et `lint.result.json`. Avec `-Wno-fatal`, un avertissement peut être présent malgré un statut `passed`.

**Mini-expérience pédagogique :** dans une copie du projet, remplace intentionnellement le nom `enable` par un nom inexistant dans l'expression `else if` ; lance `lint` et observe l'erreur remontée. Restaure ensuite le fichier original. Il s'agit d'une expérience de diagnostic, pas d'une modification à garder.

## 4.7 Effectuer la synthèse

```bash
python -m rtlprep synth examples/counter/design.json --out reports/counter
```

Si l'outil réussit, regarde :

```bash
python -m json.tool reports/counter/synth_stats.json
```

Puis inspecte `reports/counter/synthesis.ys` : c'est le script effectivement transmis à Yosys. Le nombre de cellules dépend de la version et de la configuration de l'outil : **aucun nombre universel n'est attendu**.

## 4.8 Lancer toutes les étapes

```bash
python -m rtlprep all examples/counter/design.json --out reports/counter
```

Aujourd'hui `all` effectue successivement :

1. `analyze` ;
2. `lint` ;
3. `synth`.

Un échec d'une étape **n'arrête pas automatiquement les suivantes** ; chaque outil est lancé et produit son statut. C'est utile pour le diagnostic, mais ce comportement pourra être optimisé lorsque les opérations deviendront plus coûteuses.

## 4.9 Comprendre les rapports

Une arborescence typique **lorsque tous les outils sont installés et exécutés avec succès** est :

```text
reports/counter/
├── manifest_snapshot.json
├── elaborated_ast.json
├── design_summary.json
├── analyze.result.json
├── analyze.stdout.log
├── analyze.stderr.log
├── lint.result.json
├── lint.stdout.log
├── lint.stderr.log
├── synthesis.ys
├── netlist.json
├── synth_stats.json
├── synth.result.json
├── synth.stdout.log
└── synth.stderr.log
```

La liste ci-dessus est indicative : les fichiers réellement présents dépendent des outils disponibles et du succès de chaque étape.

**Si un outil manque**, une partie de ces fichiers n'existera pas. Consulte toujours les statuts avant d'ouvrir les fichiers dépendants.

## 4.10 Exercice sur le parsing sans outils EDA

Il est possible de tester `summarize_ast` avec une donnée construite à la main :

```python
from rtlprep.analysis import summarize_ast

fixture = {
    "design": {
        "kind": "Root",
        "members": [
            {
                "kind": "Instance",
                "name": "counter",
                "body": {
                    "kind": "InstanceBody",
                    "name": "counter",
                    "members": [
                        {"kind": "Port", "name": "clk", "direction": "In", "type": "logic"}
                    ]
                }
            }
        ]
    }
}

print(summarize_ast(fixture))
```

Le résultat doit comporter un inventaire avec `instance_count == 1` et un port `clk`. Cette fixture teste **notre parcours Python**, pas la compatibilité avec un export réel de slang.

## 4.11 Ce que tu peux apprendre ensuite

Une fois ces étapes comprises, essaie un second petit module qui **instancie** le compteur. L'objectif est de comprendre la différence entre « deux définitions de module » et « plusieurs instances d'un module ». Après cela, tu peux passer aux notions de graphe de signaux et de dépendances.

Voir [tests et évolutions](tests-et-evolutions.md).

# Contrôles temporels de slang : ImplicitEvent et SignalEvent

## Origine

Le vrai RTL tiers `axis_register` (AXI-Stream, hash Git blob épinglé) avait
encore **2 avertissements** après la résolution des symboles sous `generate` :
`Timing non pris en charge : ImplicitEvent` et
`Timing non pris en charge : SignalEvent`.

Le moteur de graphe gérait auparavant seulement un `EventList` contenant
des nœuds `SignalEvent`. Slang 12.1 peut aussi exporter directement un
`SignalEvent` pour `always @(posedge clk)` et un `ImplicitEvent` pour
`always @*`. Ce sont deux sémantiques distinctes.

## Contrat de résolution

- **`ImplicitEvent`** : indique une sensibilité implicite, habituellement
  combinatoire. Les lectures RHS et les gardes fournissent déjà les
  influences syntaxiques visibles dans le périmètre actuel. **Aucune
  arête temporelle `event` n'est créée**, et aucune liste de sensibilité
  exacte n'est prétendue. Dans l'index d'expressions, la couverture
  reste explicitement `partial` pour une sensibilité implicite.
- **`SignalEvent` direct** : si `edge=PosEdge` ou `edge=NegEdge` et que
  `expr` est un `NamedValue` dont l'identité de déclaration est
  résolue par le même AST, créer une arête `event` depuis ce signal
  vers chaque cible d'affectation prise en charge.
- **`EventList`** : même règle pour chacun de ses événements ;
  la compatibilité avec les `always_ff` déjà pris en charge est
  conservée.
- **`always @(posedge clk)`** exporté par slang comme `procedureKind=Always`
  est désormais étiqueté `sequential=true` si un front explicite
  valide a été résolu. Cela ne prouve ni la latence exacte ni
  l'équivalence comportementale.
- **Fail-closed** : un front sans référence résolue, un événement
  malformé, une polarité inconnue ou un timing non reconnu conserve
  un avertissement ; le moteur ne crée alors aucune arête causale
  pour cet événement. Aucune heuristique sur les noms (`clk`,
  `rst`, etc.) n'est utilisée.

## Vérifications et limites

Les tests hermétiques couvrent `SignalEvent` direct, `EventList`,
`ImplicitEvent`, les fronts positifs/négatifs, les horloges homonymes
mais d'adresse sémantique incorrecte, les listes malformées et les
types de front non pris en charge.

```bash
python -m pytest -q tests/test_timing_controls.py
```

Le workflow d'intégration recompilera la vraie IP AXI-Stream en trois
spécialisations `REG_TYPE=0,1,2` et vérifiera explicitement l'existence
de l'arête depuis `clk` vers le registre de données dans les variantes
séquentielles. La campagne sur le module upstream par défaut vérifie
également que ses deux anciens avertissements de timing ont disparu
et que les graphes restent non vides.

```bash
python -m pytest -q tests/test_generate_scope_real.py
python scripts/validate_unknown_rtl.py \
  --sources-root upstream_unknown --out reports/unknown-validation
```

Ces tests ne valident **ni** la sensibilité complète au niveau
des appels de fonctions, **ni** la cohérence temporelle cycle par cycle,
**ni** la correction fonctionnelle. D'autres analyseurs (notamment
`register_flow` sur `Always` et les sélections de bits) peuvent
demeurer partiels et sont déclarés comme tels.

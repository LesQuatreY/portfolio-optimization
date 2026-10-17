# Portfolio Lab V2 — Architecture implémentée

Note de publication : les références V1 ci-dessous décrivent le contexte conservé dans la branche locale d'origine. Cette branche autonome publie uniquement la V2, sans notebooks V1, moteur V1, archives ni historique hérité. Les modules V2, configurations et notebooks sont identiques à ceux de `ff544ba`.

État au 18 octobre 2026. Ce document remplace le plan initial : il décrit la V2 effectivement stabilisée. Le périmètre est l'affichage et la vérification des résultats gelés, sans comptes personnels ni extension du moteur Research.

## Dépôts et périodes

Portfolio Lab est ce dépôt Git. Portfolio Research est le dossier voisin `../Draft/nasdaq_dynamic_exposure_v0`, sans modification autorisée. Le dossier SlopeFlip ne fait pas partie de cette intégration.

- V1 : `portfolio_lab.protocol`, configuration `config/research.yaml`, verrou à partir de 2020.
- V2 : `portfolio_lab.v2.guard.HARD_CUTOFF = 2023-12-29`, fenêtre FULL depuis 2014-10-01.
- TEST 2024–2026 : aucune donnée de marché ni sortie de performance ne peut être chargée.

## Structure réelle

| Élément | Responsabilité |
|---|---|
| `config/v2/lab.yaml` | Racine Research, 12 chemins autorisés et SHA-256 gelés, 11 configurations gelées, sélection initiale |
| `config/v2/instruments.yaml` | Lignes comptables, enveloppes, classes d'actifs, ISIN et provenance |
| `v2/settings.py` | Validation stricte des clés, chemins, empreintes et bornes |
| `v2/guard.py` | Autorisation, confinement des chemins, intégrité et coupure historique |
| `v2/bridge.py` | Import et vérification des configurations canoniques du manifeste ; aucun appel au simulateur |
| `v2/metrics.py` | Conventions exactes des métriques quotidiennes Research |
| `v2/checks.py` | 88 comparaisons de métriques et 10 contrôles comptables |
| `v2/formatting.py` | Nombres français, dates, absence de zéro négatif |
| `v2/tables.py`, `v2/charts.py` | Tableaux et graphiques Plotly réutilisables |
| `v2/ui.py` | Sélection commune ipywidgets, vues mises à jour en place, fiches et méthode |
| `notebooks/01_comparaison_strategies.ipynb` | Comparaison et lecture des résultats |
| `notebooks/02_robustesse_historique.ipynb` | Robustesse descriptive existante |
| `notebooks/03_allocations_enveloppes.ipynb` | Allocation et comptabilité gelées |
| `tests/test_v2.py` | Régressions financières, entrées adverses synthétiques, cache et interactions |
| `scripts/validate_v2.py` | Noyaux neufs, sélection des portefeuilles, exports et rendus locaux |

Tous les modules V2 sont dans `src/portfolio_lab/v2/`. Les anciens chemins proposés `lab_v2/`, `research_bridge.py` et le notebook unique n'ont pas été retenus.

## Flux de données

`lab.yaml` + `instruments.yaml` → validation → ResearchGuard → artefacts gelés → StrategyLab → contrôles / tableaux / graphiques → LabSession → trois notebooks.

Les 11 portefeuilles sont N07, D2_25, D2_10, S056, S054, G03, G04, B1, B2, B1M et B2M. Les quatre derniers sont des références permanentes. Le manifeste et les empreintes de configuration restent inchangés.

L'import comprend courbes, métriques maîtres, rendements glissants, calendrier, chronologie, régimes, crises, classifications, fiches françaises et taux EUR. Les courbes partagent 2 369 séances. Les sous-fenêtres DEV/EVAL sont celles des simulations Research existantes.

## Intégrité et lecture seule

1. Le chemin doit figurer dans la liste autorisée, rester dans Research après résolution et éviter les sources interdites.
2. Le SHA-256 doit correspondre à la valeur gelée.
3. Les dates sont vérifiées : métadonnées parquet (ou colonnes de dates seules si nécessaire), dates ISO des textes et années des en-têtes CSV.
4. Les dates des DataFrames sont à nouveau contrôlées après lecture ; une seconde vérification d'intégrité précède le retour.

Les contrôles d'artefacts ne sont plus mémorisés sans revérification. `load_lab()` relit la configuration et contrôle les 12 fichiers avant de retourner un résultat éventuellement mis en cache. Les interactions d'affichage travaillent sur le snapshot en mémoire déjà validé, sans simulation ni lecture Research.

Les tests d'entrées modifiées utilisent uniquement des fichiers synthétiques temporaires. Les tests Research ne lisent et ne hachent que les artefacts autorisés ; les empreintes avant/après vérifient leur non-modification. Ils ne prétendent pas vérifier le contenu de tout Research, dont les fichiers interdits restent fermés.

Les moteurs gelés ne sont ni copiés dans Git ni modifiés. Les résultats N100 importés sont distincts de données de comptes personnels.

## Conventions financières conservées

- Rendement du premier jour rapporté au capital initial, frais initiaux inclus.
- Années calendaires : `(dernier jour − premier jour + 1) / 365,25`.
- Volatilité : écart-type échantillonnal des rendements quotidiens × √252.
- Sharpe/Sortino : excès sur le taux EUR de Research, convention ACT/360.
- Drawdown : sommet cumulatif incluant le capital initial.
- Risque : trajectoire quotidienne après frais et impôts déjà payés, avant impôts de sortie.
- CAGR net : patrimoine terminal après vente et fiscalité de sortie.

Le patrimoine terminal net est importé et réconcilié avec les valeurs et impôts de sortie. Cette validation ne constitue pas une nouvelle simulation indépendante du moteur. Les simulations brutes et sans impôts sont importées sans changer leurs hypothèses. Les taux fiscaux sont ceux du modèle Research figé ; la V2 n'effectue pas de vérification législative ni de calcul fiscal personnalisé.

## Présentation et validation

La sélection est commune aux vues liées d'un notebook ; allocation et fiche individuelle ont leur propre choix. Les bascules Plotly ne relancent pas de calcul financier. Titres, sous-titres et contrôles ont des zones distinctes ; les tableaux secondaires sont repliables ou défilants.

Les notebooks sources restent courts et sans sorties. Les exécutions, HTML et PNG/SVG vont dans `outputs/v2/`, ignoré par Git. Voir [V2_VALIDATION.md](V2_VALIDATION.md) pour les résultats et les limites de la validation.

## Hors périmètre

Comptes réels, lots/PMP, contributions, fiscalité personnalisée, ancienneté du PEA, assemblage multi-stratégies, rééquilibrage de portefeuille, nouvelles stratégies, extension avant 2014 et projections ne sont pas implémentés. Aucun fichier de compte personnel n'est demandé. Toute future extension doit maintenir Research strictement en lecture seule.

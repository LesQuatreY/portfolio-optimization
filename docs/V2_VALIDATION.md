# Portfolio Lab V2 — Validation et limites

Ce rapport conserve la validation de la branche locale complète `ff544ba`. La publication autonome contient uniquement les 50 tests V2 et aucun ancien test ou notebook V1. Voir [PUBLICATION.md](PUBLICATION.md) pour le périmètre publié et ses vérifications propres.

Validation du 18 octobre 2026. Aucun accès aux données de marché ou performances TEST 2024–2026. Research reste en lecture seule.

## Reproduction financière

- 11 portefeuilles, 2 369 séances, du 2014-10-01 au 2023-12-29.
- 88/88 indicateurs reproduits : CAGR net, rendement arithmétique, volatilité, Sharpe, Sortino, MaxDD, pire 12 mois et durée maximale sous un sommet.
- Écart maximal observé : 2,22 × 10⁻¹⁶, tolérance 10⁻¹².
- 10/10 contrôles comptables conformes ; sommes des lignes à moins de 1,2 × 10⁻¹⁰ € près.
- Patrimoine terminal net réconcilié avec la valeur quotidienne finale, les frais de liquidation et les impôts de sortie pour chaque portefeuille.
- 12 empreintes d'artefacts et 11 empreintes de configuration conformes aux valeurs gelées ; empreintes des artefacts identiques avant/après validation.

Il s'agit d'une vérification des résultats importés. Le moteur Research n'a pas été relancé ; les valeurs terminales, métriques brutes et simulations DEV/EVAL sont celles des références gelées.

## Tests et baseline

Le journal historique `tmp/baseline_v1_tests.log` rapporte 368 réussites et 10 échecs. L'audit de reprise avait trouvé 364 réussites et 12 échecs, avec deux tests d'archives exclus. Les deux nouveaux échecs étaient des chemins de notebooks V1 cassés ; les références des tests et de `run.py` pointent désormais vers `notebooks/optimiseur_v1/`.

Les 50 tests dédiés V2 couvrent la reproduction, la comptabilité, les empreintes avant/après, les dates, les entrées synthétiques interdites/altérées, la modification à taille et mtime inchangés, la modification pendant une lecture, la réouverture d'un cache, la sélection des 11 portefeuilles, les boutons ipywidgets et l'absence de nouveau chargement depuis les contrôles d'affichage.

**Résultat final de la suite sûre : 416 réussites, 10 échecs préexistants, 2 exclusions. Aucune nouvelle régression.** Les 50 tests V2 passent. La commande pytest retourne donc encore le code 1 à cause des dix échecs historiques, conservés sans `xfail` ni masquage.

Un premier lancement simultané aux validations de notebooks a également rencontré un `MemoryError` dans le test multiprocessus du bootstrap. La relance isolée de toute la suite a réussi ce test ; aucun changement du bootstrap n'a été effectué. Journaux locaux : `tmp/v2-tests-final.log` et `tmp/v2-validation-final.log`.

### Dix échecs V1 préexistants conservés

| Fichier | Test |
|---|---|
| `test_phase3.py` | `test_shared_config_keeps_the_investor_preferences_with_provenance` |
| `test_phase5.py` | `test_main_research_universe_has_no_leverage_but_keeps_nasdaq_and_caps` |
| `test_phase6.py` | `test_shared_config_keeps_reference_and_michaud_active_without_leverage` |
| `test_phase7b.py` | `test_phase7b_universe_stays_reproducible_with_confirmed_caps_and_weekly_risk` |
| `test_phase7d.py` | `test_v1_is_active_with_nine_assets_and_msci_world_kept_as_disabled_benchmark` |
| `test_phase7d.py` | `test_previous_universes_remain_reproducible` |
| `test_phase7d.py` | `test_catalogue_table_separates_availability_from_eligibility` |
| `test_phase7d.py` | `test_caps_and_constrained_equal_weight_handle_gold_and_coca_cola` |
| `test_phase7d.py` | `test_fingerprint_records_the_exact_universe` |
| `test_phase7d.py` | `test_threshold_is_a_display_convention_that_removes_nothing` |

Cause : la configuration utilisateur sélectionne « Historique (6 actifs) », qui contient effectivement cinq actifs, et des plafonds vides. Les tests historiques attendent notamment l'univers Diversifié à neuf actifs, les anciens plafonds ou l'ancien nom « Historique (7 actifs) ». `config/research.yaml` est identique au checkpoint Phase 7D `6e0a11a` ; il n'a pas été modifié pour faire passer ces tests.

### Deux tests exclus pour protéger TEST

`tests/test_regression.py::test_refactor_regression_on_unchanged_inputs` et `tests/test_regression.py::test_original_wipeout_regression` sont explicitement marqués `skip` : leur extraction de fonctions ouvrirait aussi les sorties du notebook d'archive antérieur au verrou. Ces sorties ne sont ni inspectées ni exécutées. Les fonctions et le notebook sont conservés.

## Notebooks et interface

Le validateur est limité aux trois notebooks V2. Il utilise un noyau neuf par notebook, exerce les sélections complète/vide, le retrait d'un portefeuille via un vrai bouton ipywidgets et restaure la sélection initiale. Une cellule de contrôle temporaire est retirée des exports pour éviter les sorties dupliquées générées par nbclient.

Les notebooks sources versionnés restent sans sorties, avec au plus trois lignes par cellule de code. Les résultats exécutés et les HTML sont dans `outputs/v2/`. Les contrôles Plotly restent dans une seule figure lorsque possible. Les tableaux principaux ont été réduits ; les détails sont repliables et les tableaux défilent dans leur propre conteneur.

Les dépendances runtime manquantes `ipywidgets` et `pyarrow` sont déclarées. `pip check` ne signale pas de dépendance cassée. Le moteur Kaleido de développement est fixé à une version fonctionnelle sur Windows ; aucun navigateur séparé n'est nécessaire aux rendus.

## Validation visuelle

Les rendus PNG/SVG utilisent les vraies figures et données de développement autorisées, à 1 100 et 640 pixels. Ils couvrent les 11 constructeurs ainsi que les vues alternatives MaxDD, enveloppes et glissant 5 ans.

Les inspections ont motivé le retour à la ligne des longs titres/sous-titres, une marge supérieure protégeant les titres du rognage, des zones distinctes pour les contrôles, des légendes abrégées et le placement des étiquettes adapté à une surface étroite. Les annotations de régimes précédant le début des séries glissantes sont exclues. Les axes temporels restent bornés à la fin de 2023. Les nombres français évitent le zéro négatif.

**Limite explicite** : aucun navigateur pilotable n'était disponible. Les figures sont contrôlées sur des rendus réels ; les interactions des widgets sont testées dans les noyaux et par les tests Python. Le comportement visuel complet des widgets et du défilement des tableaux dans chaque navigateur/JupyterLab/VS Code n'est pas certifié par cette validation.

## Nettoyage et préservation

- Checkpoint de reprise `cee6a6e`, après le checkpoint Phase 7D `6e0a11a`.
- Sorties initiales/supplémentaires du notebook 01 et sauvegarde interactive du notebook 02 préservées localement dans `tmp/v2-preserved/` ; le checkpoint conserve aussi l'état initial du notebook 01.
- Ancien audit d'architecture, contenant des détails personnels, conservé uniquement dans cette sauvegarde ignorée ; documentation actuelle sans montants de comptes.
- Guide V1 conservé dans `docs/V1_GUIDE.md`, références V1 actualisées, fausse référence à `validate_palette.js` retirée.
- Cache d'intégrité corrigé, fonction d'empreintes inutilisée et import mort retirés ; hypothèses et calculs financiers inchangés.
- Caches, environnements, résultats de validation et futur fichier de comptes personnels exclus de Git.

Au moment de la livraison, une session ouverte resauvegarde les sorties du notebook 02 dans le fichier de travail. Ces sorties autorisées restent locales et non commitées ; la version Git conserve les cellules sources sans sorties. Elles ne sont pas écrasées pour obtenir artificiellement un arbre propre.

Aucun nettoyage ni réorganisation de Research. Aucun compte réel, simulateur fiscal personnalisé, mélange de stratégies, nouvelle optimisation ou extension historique ajouté.

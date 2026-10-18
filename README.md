# Portfolio Lab V2

La version V2.1 est finalisée dans le dépôt canonique `Trading/portfolio-optimization`, branche `feature/custom-portfolios-v2-1`. Voir la [validation finale](docs/V2_1_RELEASE_VALIDATION.md) pour les contrôles de publication et les limites conservées.

Cette branche de publication autonome contient uniquement les sources V2 approuvées. Elle commence par un nouveau commit racine sans historique hérité. La branche locale `portfolio-lab-v2`, la V1 et les checkpoints Phase 7D sont conservés séparément. Voir [la méthode de publication](docs/PUBLICATION.md).

Comparer en français les **11 portefeuilles gelés de Portfolio Research** : 7 stratégies et 4 références Nasdaq, sur **2014-10-01 → 2023-12-29**, avec un capital normalisé de 100 000 € (N100).

La V2 affiche les résultats existants ; elle ne cherche pas une nouvelle stratégie et ne représente pas vos comptes personnels. Les résultats historiques dépendent notamment de proxies et ne constituent pas une prévision.

## Démarrer

PowerShell, depuis la racine du dépôt, avec Python 3.10 ou plus :

```powershell
python -m venv .venv                       # uniquement si l'environnement n'existe pas
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m jupyterlab notebooks/01_comparaison_strategies.ipynb
```

Dans JupyterLab, choisir le noyau de cet environnement et **Run → Run All Cells**. Le dépôt Research doit exister au chemin `research.root` de [config/v2/lab.yaml](config/v2/lab.yaml), par défaut `../Draft/nasdaq_dynamic_exposure_v0`.

| Notebook | Utilisation |
|---|---|
| [01 — Comparaison](notebooks/01_comparaison_strategies.ipynb) | Commencer ici : indicateurs, rendement/risque, patrimoine et drawdowns, fiches, méthode |
| [02 — Robustesse historique](notebooks/02_robustesse_historique.ipynb) | Rendements glissants, DEV/EVAL, années et régimes, crises, récupération |
| [03 — Allocations et enveloppes](notebooks/03_allocations_enveloppes.ipynb) | Poids comptables, exposition économique, frais, impôts et provenance |
| [04 — Portefeuilles personnalisés](notebooks/04_portefeuilles_personnalises.ipynb) | V2.1 : éditeur, configurations JSON et moteur ; historique à six actifs bloqué jusqu'à validation des données |

La V2.1 est décrite dans le [guide du constructeur](docs/V2_1_GUIDE.md). Le portefeuille initial conserve ses six poids. **V2.2 — admission des données** ([rapport](docs/V2_2_DATA_ADMISSION.md)) : convention causale « instantané à la clôture Euronext », calendriers par règles, change BCE et contrôles indépendants (MSCI, ^SP500TR, IAU, Bitstamp) avec tolérances déclarées avant calcul. Les six actifs sont validés (EM, S&P 500, MSCI World, CAC 40 NR, or, Bitcoin composite Bitstamp) ; le backtest du portefeuille diversifié (Phase B) est exécuté et vérifié indépendamment : [résultats](docs/V2_2_PHASE_B_RESULTS.md), `scripts/run_diversified_backtest.py` (export Euronext requis, import prêt : `scripts/import_cac40.py`). Les performances restent économiques (CAGR net fiscal « Non calculé ») et historiques. L'éditeur et les tests synthétiques fonctionnent sans ces données.

Les boutons colorés ajoutent ou retirent un portefeuille dans **toutes les vues liées à la sélection du notebook**. « Tout », « Aucun » et « Sélection par défaut » sont disponibles. Les fiches et l'allocation d'un portefeuille ont leur propre sélecteur. Les références B1, B2, B1M et B2M restent sélectionnables ; leurs marques grises sont cohérentes entre graphiques.

Le graphique rendement/risque reste unique : son bouton bascule entre volatilité et MaxDD. Les autres boutons changent l'échelle ou la vue sans relancer de simulation. Cliquer dans une légende Plotly masque une courbe localement. Les tableaux détaillés sont secondaires et défilent horizontalement dans leur propre zone sur écran étroit.

## Lire les résultats

| Indicateur | Sens dans cette version |
|---|---|
| CAGR net | Croissance composée annualisée entre le capital initial et le patrimoine après vente finale et impôts de sortie |
| Volatilité | Écart-type des rendements quotidiens, annualisé ; mesure des fluctuations |
| MaxDD journalier | Plus forte baisse depuis un sommet, capital initial inclus ; présenté comme une perte positive dans les tableaux |
| Sharpe | Rendement excédant le taux monétaire EUR de Research, rapporté à sa variabilité |
| Drawdown | Baisse depuis le sommet, négative sur la courbe ; une autre vue montre la durée sous le sommet |

**Trois bases de mesure distinctes** :

1. **Brut** : simulation Research séparée sans frais de transaction ni impôts. Les frais de fonds et le coût du levier déjà intégrés aux prix restent présents.
2. **Valeur quotidienne** : après frais et impôts effectivement payés pendant la simulation, avant liquidation. Volatilité, MaxDD, Sharpe et rendements glissants utilisent cette trajectoire.
3. **Patrimoine net après liquidation** : vente finale et impôts de sortie déduits. Il détermine le CAGR net ; les impôts de sortie ne sont jamais retranchés des rendements quotidiens.

La différence brut–net n'est pas une simple somme des frais et impôts : le brut provient d'une simulation distincte avec ses propres effets d'arrondi et de bandes. La fiscalité affichée est **celle du modèle Research gelé**, pas un calcul fiscal personnel ni une vérification du droit en vigueur.

## Provenance et limites

Les historiques COSE et consommation de base CTO utilisent XLP en EUR ; l'or utilise GLD en EUR ; le monétaire PEA est synthétique. La provenance des lignes et leur part moyenne dans chaque portefeuille figurent dans les notebooks et [instruments.yaml](config/v2/instruments.yaml). Une bonne performance historique avec un proxy ne garantit pas celle du produit réel.

DEV et EVAL sont deux simulations historiques déjà étudiées. EVAL n'est pas un test vierge. La V2 ne fait aucun nouveau classement statistique et ne prolonge pas l'historique avant 2014.

**Disponibles** : comparaison, robustesse descriptive, allocations gelées, frais/impôts historiques, contrôles de reproduction et d'intégrité.

**Prévus, hors de cette version** : comptes réels, fiscalité personnalisée, contributions, combinaison de stratégies, rééquilibrage entre enveloppes et projections. Aucun fichier de comptes personnels n'est à créer. Un futur `config/v2/investor_accounts.yaml` est préventivement ignoré par Git.

## Protection des données

- Portfolio Research reste strictement en lecture seule. Aucun moteur Research n'est importé ou exécuté.
- Seuls les 12 artefacts autorisés et leurs SHA-256 gelés sont lus. Les empreintes sont revérifiées à chaque ouverture, même si les résultats sont déjà en cache, et à chaque lecture d'artefact.
- **TEST 2024–2026 verrouillé** : coupure V2 codée en dur au 29 décembre 2023. Les sources interdites, les fichiers altérés et les dates hors période sont rejetés.
- La V1 garde son propre verrou à partir de 2020 ; les deux contextes ne sont pas mélangés.
- Ne pas exécuter les notebooks d'archives ni les scripts historiques susceptibles d'ouvrir des sorties antérieures au verrou.

## Vérifier et exporter

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest tests/test_v2.py -q
.\.venv\Scripts\python.exe scripts/validate_v2.py --render
.\.venv\Scripts\python.exe scripts/validate_custom.py
```

Le validateur exécute uniquement les trois notebooks V2 dans des noyaux neufs, teste la sélection, vérifie les résultats financiers et les empreintes, puis écrit les notebooks exécutés, les aperçus HTML et les figures PNG/SVG dans `outputs/v2/` (ignoré par Git). Les notebooks sources versionnés restent sans sorties dupliquées. Les rendus statiques utilisent Kaleido, une dépendance de développement.

La V2.2 contient **178 tests : 50 tests V2, 61 tests du constructeur personnalisé, 41 tests d'admission des données (calendriers, heures d'été, causalité, import CAC 40, amendements A1–A5 et A3b, corrections officielles CAC 40), 9 tests de la Phase B (vérifications indépendantes du backtest), 10 tests de la Phase C (référence BRK.B) et 7 tests de la Phase D (audit final)**. Phase C : [référence BRK.B](docs/V2_2_PHASE_C_BRK.md), admise selon A6-bis (révision a posteriori approuvée), achat-conservation comparé dans le notebook 04 (`scripts/run_brk_benchmark.py`). Phase D : [audit final](docs/V2_2_PHASE_D_FINAL_AUDIT.md), exploratoire et en lecture seule (`scripts/run_final_audit.py`). `scripts/fetch_reference_data.py` puis `scripts/prepare_custom_data.py` reconstruisent localement les niveaux admis dans `data/v2_1/` (ignoré par Git). `validate_v2.py` vérifie les notebooks 01–03 ; `validate_custom.py` vérifie le notebook 04, sa sauvegarde/relecture et les analyses synthétiques dans `outputs/v2_1/` (ignoré par Git). Les quatre notebooks versionnés sont sans sorties, compteurs d'exécution ni état de widgets. Les anciens tests V1 et ceux lisant des archives ne sont pas inclus. Le [rapport de validation historique](docs/V2_VALIDATION.md) décrit séparément les résultats obtenus sur la branche locale complète et les limites de la validation visuelle.

## Périmètre et structure du dépôt

Les capacités V1, sa configuration et le travail Phase 7D restent dans la branche locale d'origine. Les notebooks historiques, le registre d'expériences et les sorties associées sont exclus de cette publication indépendante. Aucun moteur ni jeu de données Research n'est embarqué : l'import utilise exclusivement les artefacts autorisés du dossier Research local.

Le lanceur V1 `run.py` n'est pas inclus. Pour exécuter les notebooks V2, utiliser JupyterLab ou `scripts/validate_v2.py`.

```text
config/v2/                  Configuration de l'import gelé et provenance des instruments
src/portfolio_lab/v2/       Garde-fous, import, indicateurs, contrôles et interface française
notebooks/01_*.ipynb        Comparaison (point d'entrée)
notebooks/02_*.ipynb        Robustesse historique
notebooks/03_*.ipynb        Allocations et enveloppes
tests/test_v2.py            Régressions financières, intégrité, dates et widgets
scripts/validate_v2.py      Exécution et rendus V2 autorisés uniquement
outputs/v2/                Résultats locaux de validation, jamais commités
```

Voir [l'architecture V2](docs/V2_ARCHITECTURE_AUDIT.md), [le manifeste de provenance](docs/PUBLICATION_MANIFEST.json) et [la méthode de publication](docs/PUBLICATION.md).

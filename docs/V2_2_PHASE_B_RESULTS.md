# V2.2 Phase B — Backtest historique de « Mon portefeuille diversifié »

Date : 18 octobre 2026. Branche `feature/custom-portfolios-v2-1`, base `30aa848`, modifications non commitées. Reproduction : `scripts/run_diversified_backtest.py`, qui écrit dans `outputs/v2_2/` (ignoré par Git) le rapport `phase_b_report.json`, le registre, les positions, les ordres et les figures.

Ces résultats sont historiques, sur un seul échantillon (2014-10-01 → 2023-12-29). Ils ne constituent ni une prévision ni un classement statistique, et ils ne tiennent compte d'aucune fiscalité personnelle.

## 1. Portefeuille exécuté, sans aucune modification

La spécification est `config/v2/portfolios/mon_portefeuille_diversifie.json`, d'identité `8afaeb44…`. Son empreinte de fichier est vérifiée inchangée après exécution.

- **Poids** : EM 30 %, S&P 500 30 %, MSCI World 15 %, CAC 40 10 %, or 10 %, Bitcoin 5 %.
- **Paramètres** : 100 000 €, EUR, rééquilibrage mensuel, 0 pb de frais, sans levier.
- **Données** : les six séries admises (`docs/V2_2_DATA_ADMISSION.md`), chargées par `load_validated_panel` (empreintes, coupure, calendrier commun).
- **Calendrier** : 2 368 séances Euronext. Une valorisation causale par séance à la clôture de Paris, avec clôture US de la veille, fixing BCE publié et Bitcoin du jour UTC précédent.
- **Exécution** : panier idéal fractionnaire au cours de valorisation du jour de rééquilibrage, soit la première séance de chaque mois. Ce n'est **pas** un ordre exécutable simultanément : les lignes US sont échangées au dernier cours connu.
- **Frais** : 0 pb de frais explicites. Les frais des ETF, ainsi que les écarts de suivi et retenues subis par les fonds, restent dans les séries. Les dividendes de SPY et EEM sont réinvestis bruts. Aucune liquidation finale n'est modélisée.

## 2. Vérifications indépendantes (20 sur 20 conformes)

Elles figurent dans `src/portfolio_lab/v2/backtest_checks.py`. Elles partent des registres de sortie et des prix, sans réutiliser la boucle du simulateur.

**Calendrier**
- Les séances simulées sont exactement celles du calendrier validé.
- 111 rééquilibrages, chacun exactement à la première séance du mois.

**Comptabilité**
- Investissement initial égal au capital ; somme des poids cibles égale à 1.
- Poids revenus à la cible après chaque rééquilibrage (écart inférieur à 1e-10).
- Autofinancement (liquidités inférieures à 1e-9 de la valeur).
- Positions × prix + liquidités = valeur.
- Notionnels = variation des positions × prix ; frais = taux × notionnel ; rotation = notionnel / valeur avant ordres.

**Valeur et indicateurs**
- La valeur du moteur coïncide avec une **formule fermée indépendante** (panier à poids fixes entre deux rééquilibrages) à **2,3e-15** près en relatif.
- CAGR, volatilité, MaxDD, valeur finale et Sharpe ont été recalculés avec numpy et coïncident avec le module d'analyse.

**Causalité**
- Une exécution tronquée au 28/06/2019 reproduit exactement l'exécution complète jusqu'à cette date.
- Multiplier tous les prix postérieurs par des facteurs aléatoires de 0,5 à 1,5 ne change rien à la trajectoire antérieure, et le témoin confirme que la suite, elle, change.

## 3. Résultats

| Indicateur | Valeur |
|---|---|
| Valeur finale économique | **302 449 €** pour 100 000 € investis |
| CAGR économique, durée (fin − début + 1 j) / 365,25 = 9,2457 ans | **12,72 %** |
| Volatilité annualisée (quotidienne, √252) | 13,89 % |
| MaxDD quotidien (pic initial inclus) | 29,65 % (COVID 2020, récupéré le 09/11/2020) |
| Sharpe, taux 0 % / taux EUR Research (ACT/360) | 0,918 / 0,914 |
| Frais de transaction cumulés | 0 € (0 pb par construction) |
| Rotation cumulée, deux côtés | 3,99, dont 1,00 d'achat initial, soit environ 0,32 par an hors achat initial |
| CAGR net fiscal | **Non calculé** |

**Rendements annuels** : 2014 (T4) +2,9 % ; 2015 +8,4 % ; 2016 +17,9 % ; 2017 +28,6 % ; 2018 −9,3 % ; 2019 +31,7 % ; 2020 +15,0 % ; 2021 +26,6 % ; 2022 −13,9 % ; 2023 +19,3 %.

**CAGR glissants (années civiles)**

| Horizon | Minimum | Médiane | Maximum | Dernier |
|---|---|---|---|---|
| 3 ans | 3,2 % | 14,6 % | 24,8 % | 9,6 % |
| 5 ans | 5,5 % | 13,6 % | 21,2 % | 14,7 % |

**Dérive des poids entre deux rééquilibrages** : Bitcoin de 2,8 % à 8,9 % (cible 5 %), or de 8,5 % à 12,5 %, EM de 27,7 % à 32,0 %, S&P 500 de 28,4 % à 31,6 %, World de 13,8 % à 15,7 %, CAC 40 de 8,4 % à 11,0 %.

Figures (Plotly, mêmes composants que le notebook 04) : patrimoine, drawdown, glissants, allocation, années, frais, rotation et comparaisons, dans `outputs/v2_2/*.html`.

## 4. Comparaison avec Portfolio Research

Les courbes gelées sont **échantillonnées** sur les 2 368 séances du portefeuille. Une seule date Research est retirée, le 25/12/2019 : une ligne fictive un jour férié, dont le rendement est reporté sur la séance suivante. Aucune valeur n'est modifiée et rien n'est recalculé dans Research. Sur ce calendrier, les indicateurs recalculés concordent avec les valeurs canoniques : volatilité à 0,01 point près ou mieux, MaxDD identiques, Sharpe à 0,0003 près.

| Portefeuille | CAGR trajectoire | Volatilité | MaxDD | Sharpe (taux EUR Research) | CAGR brut Research | CAGR net fiscal Research |
|---|---|---|---|---|---|---|
| **Diversifié** (économique, 0 pb) | **12,7 %** | **13,9 %** | **29,6 %** | **0,91** | — | Non calculé |
| N07 | 27,4 % | 25,6 % | 37,7 % | 1,06 | 28,9 % | 24,9 % |
| D2_25 | 29,6 % | 28,9 % | 45,1 % | 1,02 | 30,8 % | 27,0 % |
| B1 Nasdaq ×1 | 19,0 % | 20,6 % | 31,4 % | 0,93 | 19,0 % | 16,9 % |
| B2 Nasdaq ×2 | 29,9 % | 39,7 % | 61,2 % | 0,85 | 30,0 % | 27,3 % |
| B1M | 20,5 % | 19,3 % | 32,8 % | 1,04 | 21,4 % | 18,3 % |
| B2M | 30,8 % | 37,3 % | 60,5 % | 0,89 | 31,5 % | 28,1 % |

**Ce qui est comparable** (tableau `comparability_table()`, affiché dans le notebook 04) :

| Mesure | Comparable ? | Raison |
|---|---|---|
| Volatilité, MaxDD, Sharpe au taux EUR Research | Oui, avec réserve | Mêmes séances, même taux et même méthode ; la trajectoire Research inclut ses frais et impôts intermédiaires |
| CAGR économique du portefeuille et CAGR brut Research | Approximativement | Ni frais de transaction ni fiscalité de part et d'autre ; frais des fonds et coût du levier inclus ; le brut Research vient d'une simulation séparée |
| CAGR net fiscal | Non | Modèle fiscal gelé côté Research ; « Non calculé » ici, faute de modèle fiscal approuvé |
| Sharpe à 0 % contre Sharpe canonique Research | Non | Conventions de taux différentes |

**Fenêtres historiques** : rendement sur la période, puis entre parenthèses le MaxDD dans la fenêtre.

| Portefeuille | 2014–2018 | 2019–2023 | T4 2018 | COVID 2020 (19/02–23/03) | 2022 |
|---|---|---|---|---|---|
| Diversifié | +53 % (21 %) | +97 % (30 %) | −10,3 % (11,9 %) | −29,3 % (29,6 %) | −13,9 % (15,3 %) |
| N07 | +128 % (29 %) | +312 % (38 %) | −20,2 % (25,1 %) | −33,8 % (35,4 %) | −34,8 % (35,5 %) |
| D2_25 | +172 % (31 %) | +304 % (45 %) | −20,5 % (25,9 %) | −43,5 % (45,1 %) | −37,2 % (37,7 %) |
| B1 | +79 % (23 %) | +179 % (31 %) | −15,4 % (20,9 %) | −27,0 % (28,2 %) | −29,8 % (30,3 %) |
| B2 | +138 % (40 %) | +373 % (61 %) | −31,9 % (40,2 %) | −50,7 % (52,2 %) | −59,2 % (59,9 %) |
| B1M | +96 % (21 %) | +186 % (33 %) | −15,0 % (20,2 %) | −26,4 % (27,7 %) | −30,0 % (30,5 %) |
| B2M | +157 % (38 %) | +364 % (60 %) | −30,4 % (38,4 %) | −48,9 % (50,4 %) | −58,3 % (58,9 %) |

## 5. Lecture, dans les limites d'un seul échantillon

- **Moins de volatilité, pas de meilleur couple rendement/risque.** La volatilité est inférieure d'environ un tiers à celle de Nasdaq ×1 (13,9 % contre 20,6 %). Mais le Sharpe au même taux (0,91) reste du même ordre que B1 (0,93) et en dessous de B1M, N07 et D2_25 (1,02 à 1,06). Sur 2014–2023, la diversification internationale a surtout réduit le rendement : la décennie a été exceptionnelle pour le Nasdaq. Les marchés émergents (30 %), l'Europe et le CAC (25 % au total) ont nettement moins progressé.
- **Une protection nette lors des baisses lentes, presque nulle lors d'un krach brutal.**
  - En 2022 : −13,9 % contre −29,8 % (B1) et −34,8 % (N07).
  - Au T4 2018 : −10,3 % contre −15,4 % (B1).
  - En revanche, lors du choc COVID, le MaxDD (29,6 %) est proche de celui de B1 (28,2 %). Les six actifs ont chuté ensemble, Bitcoin compris (−37 % sur le jour UTC du 12/03/2020) : la diversification n'a pas protégé de ce krach rapide.
- **Le MaxDD global** (29,6 %) est donc à peine inférieur à celui de B1 (31,4 %), alors que l'écart de volatilité est bien plus marqué.
- **Rotation faible** (environ 32 % par an en deux côtés) : avec des frais réalistes de quelques points de base, l'effet sur le CAGR resterait de l'ordre de 0,01 à 0,03 point par an. Aucune variante de frais n'a été optimisée.
- Ces constats décrivent un passé unique. Ils n'autorisent aucune conclusion de supériorité statistique ni aucun ajustement des poids, et aucun n'a été fait.

## 6. Limites

- Proxys d'ETF : SPY et EEM sont des fonds américains, inaccessibles tels quels à un investisseur particulier français, avec dividendes réinvestis bruts. GLD est un ETC adossé à l'or, pas de l'or physique sans frais. CW8 est un ETF, pas l'indice. Le Bitcoin est un prix de plateforme (Bitstamp).
- CAC 40 NR : export d'un diffuseur, avec deux corrections officielles déclarées (fichiers bruts intacts), une marque reportée le 27/07/2016 et une ligne mal datée corrigée (31/12/2014). Les instantanés Bitcoin des 07–09/01/2015 sont des marques reportées.
- Valorisation causale, pas exécution simultanée. Le change BCE de 14 h 15 introduit un bruit quotidien qui se résorbe le lendemain, sans biais de rendement mesurable (environ 0,3 pb/an).
- La comparaison Research reste partielle : CAGR net fiscal non calculé, et trajectoires Research après frais et impôts intermédiaires.

## 7. Validation

- 161 tests réussis : 50 V2, 61 constructeur, 41 admission, 9 Phase B.
- `validate_v2.py` : 88/88 indicateurs gelés et 10/10 contrôles comptables.
- `validate_custom.py` : le notebook 04 s'exécute dans un noyau neuf. Le portefeuille réel tourne sur 2 368 séances, la comparaison Research s'affiche, et aucune date postérieure au 29/12/2023 n'apparaît dans les sorties.
- Les 12 empreintes Research sont inchangées. La période TEST reste verrouillée.

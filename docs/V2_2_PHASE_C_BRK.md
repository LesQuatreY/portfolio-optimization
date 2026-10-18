# V2.2 Phase C — Référence Berkshire Hathaway B (BRK.B)

Date : 18 octobre 2026. Branche `feature/custom-portfolios-v2-1`, modifications non commitées. Reproduction :

```powershell
.\.venv\Scripts\python.exe -B scripts/prepare_brk_benchmark.py --update-catalog   # admission A6-bis, niveau EUR, catalogue
.\.venv\Scripts\python.exe -B scripts/run_brk_benchmark.py                         # achat-conservation, contrôles, comparaisons
```

Les rapports sont écrits dans `outputs/v2_2/brk_admission.json` et `outputs/v2_2/phase_c_report.json` (ignorés par Git).

**Statut : COMPLÈTE.** BRK.B est admis selon **A6-bis**, une révision méthodologique **a posteriori** approuvée par le propriétaire. Les 12 critères A6 d'origine et leurs 2 échecs restent publiés. L'achat-conservation passe ses 21 vérifications indépendantes.

BRK.B représente l'entreprise Berkshire Hathaway dans son ensemble : assurance, filiales opérationnelles, trésorerie, participations cotées. Ce n'est **pas** le portefeuille d'actions déclaré par Warren Buffett, et aucune reconstruction 13F n'est entreprise. C'est une **référence professionnelle concentrée** sur une seule entreprise.

## 1. Données, toutes bornées au 29/12/2023

| Source | Contenu | Provenance |
|---|---|---|
| Yahoo `BRK-B`, adaptateur borné | 2 349 séances, 02/09/2014 → 29/12/2023 | Une requête (`period2` = 30/12/2023 00:00 New York), champs de cotation courante retirés avant lecture ; `068eff55…` |
| Yahoo `BRK-A`, même adaptateur | 2 349 séances | Contrôle d'identité de classe ; `e261b9a3…` |
| Nasdaq.com, historique public BRK.B | 1 813 clôtures, **17/10/2016 → 29/12/2023** (profondeur servie : 10 ans) | `fromdate`/`todate` bornés ; `109b2799…` |
| Formulaire 10-K 2015 de Berkshire (SEC) | Cours trimestriels extrêmes A et B, 2014 et 2015, NYSE Composite ; clause de conversion ; « aucun dividende depuis 1967 » | Lu dans le navigateur intégré (EDGAR refuse les clients automatisés sans adresse de contact) ; extraction `data/v2_1/raw/sec/berkshire_10k_2015_price_ranges.json` (`3475423…`) |
| BCE EUR/USD | Déjà validé (amendement A1) | Inchangé |

Tentatives restées sans suite, sans contournement :
- MarketWatch : HTTP 401 ;
- Nasdaq avant le 17/10/2016 : historique non servi ;
- EDGAR par programme : HTTP 403.

## 2. Admission

**Critères A6 d'origine** (figés avant toute requête, publiés) : 10 sur 12 conformes. Les deux échecs portent sur le contrôle A/B :
- écart maximal entre A et 1 500 × B : 341,7 pb pour une limite de 200 ;
- corrélation quotidienne A/B : 0,974 pour un minimum de 0,99.

**A6-bis (révision a posteriori approuvée).** Le 10-K confirme que chaque action A est convertible en 1 500 actions B, et que la conversion n'existe pas dans l'autre sens. Seule une décote de A est donc anormale, pas une prime.

| Critère décisif | Mesuré | Limite |
|---|---|---|
| Calendrier NYSE exact (A et B) | 0 écart | 0 |
| Distributions, divisions d'actions dans la fenêtre | 0, 0 | 0 |
| Clôture ajustée = clôture | 0 | ≤ 1e-9 |
| Nasdaq.com (17/10/2016 → 29/12/2023) : écarts médian / 99e centile / maximum | 0,0002 / 0,0005 / 1,01 pb | 1 / 5 / 50 pb |
| Avant Nasdaq (02/09/2014 → 14/10/2016) : écart A/B médian | 10,2 pb | ≤ 50 |
| Avant Nasdaq : borne basse de conversion, A / (1 500 × B) − 1 *(seuil a posteriori)* | −74,9 pb | ≥ −100 |
| Avant Nasdaq : divergence cumulée A/B *(seuil a posteriori)* | 14,3 pb | ≤ 50 |
| 10-K : clôtures hors des fourchettes trimestrielles officielles (A et B) | 0 sur 2 × 337 | 0 |
| 10-K : extrêmes trimestriels Yahoo vs officiels (5 trimestres complets) | ≤ 4,5e-6 en relatif | ≤ 1 % |

Les critères 10-K ont été fixés **avant** de lire le document. Ils servent de contrôle de vraisemblance des niveaux et de l'absence d'ajustement en 2014–2015, pas de preuve de chaque clôture quotidienne.

**Diagnostics** (non bloquants) :
- corrélation A/B quotidienne de 0,974, mais 0,992 sur 5 jours ;
- aucune décote persistante : au plus 2 séances d'affilée sous −50 pb, moyenne glissante sur 20 jours au minimum −27,8 pb ;
- une prime persistante de la classe A en 2023 (médiane +124 pb, 68 séances d'affilée au-dessus de +100 pb), compatible avec une conversion à sens unique.

**Aucun prix BRK.B n'est modifié ni sélectionné.**

**Valorisation (identique à SPY).** Clôture NYSE disponible avant l'instantané de Paris (en pratique J−1, âges de 1 à 4 jours), divisée par le fixing BCE publié, sur le calendrier commun des 2 368 séances Euronext. Berkshire ne versant aucun dividende, le prix est le rendement total. Niveau : `levels/BRK_B.csv` (`69095084…`).

## 3. Achat-conservation BRK.B

Hypothèses : 100 000 € investis le 01/10/2014 à la valorisation du jour, conservés jusqu'au 29/12/2023 ; frais explicites de 0 pb (sensibilité 10 pb) ; aucun levier, aucun signal ; aucune fiscalité.

**Vérifications (21 sur 21)** :
- un seul ordre, comptabilité, formule fermée (écart 2e-16) ;
- recalcul indépendant des indicateurs ;
- causalité (calcul arrêté en cours de route, prix futurs perturbés) ;
- même calendrier que le portefeuille diversifié.

Le résultat de la Phase B est inchangé (302 448,53 €).

| Indicateur | BRK.B |
|---|---|
| Valeur finale économique | **295 225 €** |
| CAGR économique (9,2457 ans) | **12,42 %** |
| Volatilité annualisée | 20,63 % |
| MaxDD quotidien | 29,62 % |
| Sharpe au taux EUR Research / au taux 0 % | 0,659 / 0,662 |
| Sensibilité : achat initial à 10 pb | 294 930 €, CAGR 12,41 % |
| CAGR net fiscal | Non calculé |

**Rendements annuels BRK.B** : 2014 (T4) +14,1 % ; 2015 −1,8 % ; 2016 +26,0 % ; 2017 +7,6 % ; 2018 +6,0 % ; 2019 +14,4 % ; 2020 −7,3 % ; 2021 +41,5 % ; 2022 +9,5 % ; 2023 +11,7 %.

**CAGR glissants** : sur 3 ans, de −1,7 % à 25,7 % (médiane 12,3 %) ; sur 5 ans, de 2,4 % à 16,3 % (médiane 12,0 %).

## 4. Comparaison sur le même calendrier (2 368 séances)

Seule une date Research est retirée, le 25/12/2019 (ligne fictive). Les volatilités, MaxDD et Sharpe sont calculés de la même façon, au même taux EUR.

| Portefeuille | CAGR trajectoire | Volatilité | MaxDD | Sharpe (taux EUR) | Valeur finale | CAGR net fiscal |
|---|---|---|---|---|---|---|
| **BRK.B** (achat-conservation, 0 pb) | **12,4 %** | 20,6 % | 29,6 % | 0,66 | 295 225 € | Non calculé |
| Diversifié (économique, 0 pb) | 12,7 % | 13,9 % | 29,6 % | 0,91 | 302 449 € | Non calculé |
| N07 | 27,4 % | 25,6 % | 37,7 % | 1,06 | 939 528 € | 24,9 % (Research) |
| D2_25 | 29,6 % | 28,9 % | 45,1 % | 1,02 | 1 096 728 € | 27,0 % (Research) |
| B1 Nasdaq ×1 | 19,0 % | 20,6 % | 31,4 % | 0,93 | 499 242 € | 16,9 % (Research) |
| B2 Nasdaq ×2 | 29,9 % | 39,7 % | 61,2 % | 0,85 | 1 126 988 € | 27,3 % (Research) |

Bases distinctes, sans classement fiscal commun :
- BRK.B et le portefeuille diversifié sont **économiques**, sans fiscalité.
- Les trajectoires Research incluent leurs frais et impôts intermédiaires.
- Le CAGR net fiscal Research est un résultat après liquidation, non comparable aux CAGR économiques.

**Fenêtres de crise** : rendement sur la période, puis entre parenthèses le MaxDD dans la fenêtre.

| Portefeuille | T4 2018 | COVID 2020 (19/02–23/03) | 2022 | 2014–2018 | 2019–2023 |
|---|---|---|---|---|---|
| BRK.B | −5,8 % (14,1 %) | −24,8 % (25,8 %) | **+9,5 %** (22,3 %) | +61 % | +83 % |
| Diversifié | −10,3 % (11,9 %) | −29,3 % (29,6 %) | −13,9 % (15,3 %) | +53 % | +97 % |
| N07 | −20,2 % (25,1 %) | −33,8 % (35,4 %) | −34,8 % (35,5 %) | +128 % | +312 % |
| D2_25 | −20,5 % (25,9 %) | −43,5 % (45,1 %) | −37,2 % (37,7 %) | +172 % | +304 % |
| B1 | −15,4 % (20,9 %) | −27,0 % (28,2 %) | −29,8 % (30,3 %) | +79 % | +179 % |
| B2 | −31,9 % (40,2 %) | −50,7 % (52,2 %) | −59,2 % (59,9 %) | +138 % | +373 % |

**Corrélations des rendements de BRK.B**

| Avec | Quotidienne | Hebdomadaire | Mensuelle |
|---|---|---|---|
| Portefeuille diversifié | 0,69 | 0,68 | 0,65 |
| N07, D2_25, B1, B2 | 0,16 à 0,22 | 0,46 à 0,49 | 0,51 à 0,56 |

Les corrélations quotidiennes avec Research sont **faussées par les horloges de valorisation**. Les lignes Nasdaq de Research sont des ETF cotés à Paris, valorisés à 17 h 30 avec une partie de la séance américaine du jour, alors que BRK.B utilise la clôture NYSE de la veille. Seules les corrélations hebdomadaires et mensuelles sont interprétables.

## 5. Lecture, dans les limites d'un seul échantillon

- **Rendement comparable au portefeuille diversifié, avec plus de risque.** CAGR 12,4 % contre 12,7 %, mais volatilité de 20,6 % contre 13,9 %, d'où un Sharpe nettement plus bas (0,66 contre 0,91). Le MaxDD est identique (29,6 %).
- **Bien en dessous du Nasdaq sur 2014–2023.** BRK.B a la même volatilité que Nasdaq ×1 (20,6 %) pour 6,6 points de CAGR en moins. Son Sharpe (0,66) est le plus bas du tableau.
- **Un vrai comportement de valeur défensive dans les baisses de taux et de valorisation** :
  - +9,5 % en 2022, contre −30 % à −59 % pour les stratégies Nasdaq ;
  - −5,8 % au T4 2018, contre −15 % à −32 %.

  En revanche, la protection a été faible lors du krach COVID (−24,8 % contre −27,0 % pour B1), puis BRK.B a perdu 7,3 % sur l'année 2020 quand le Nasdaq progressait.
- **Diversification** : la corrélation mensuelle avec les stratégies Nasdaq est d'environ 0,55, celle avec le portefeuille diversifié de 0,65. BRK.B apporte une exposition « valeur / assurance / industrie américaine » distincte de la croissance technologique, mais reste une seule entreprise, avec un risque spécifique de concentration (gouvernance, succession, conglomérat).
- Ces constats décrivent une décennie particulière, très favorable aux valeurs de croissance. Ils n'autorisent aucune conclusion statistique ni aucune optimisation.

## 6. Limites

- A6-bis est une révision **a posteriori**. La période 02/09/2014 → 14/10/2016 n'est vérifiée que par la cohérence A/B (même fournisseur) et les fourchettes trimestrielles du 10-K pour 2014–2015. Il n'y a pas de second fournisseur quotidien sur cette période.
- Valorisation causale à la clôture NYSE de la veille, pas un ordre exécuté au même instant. Le change BCE de 14 h 15 ajoute un bruit quotidien qui se résorbe le lendemain.
- Fiscalité non modélisée. Une détention réelle en EUR passerait par un compte-titres, avec la fiscalité des plus-values et sans dividende.

## 7. Intégration et tests

- `config/v2/custom_benchmarks.yaml` : catalogue des références externes, distinct des actifs du constructeur. BRK.B ne rejoint pas les 11 portefeuilles Research gelés.
- Notebook 04 : « BRK.B (référence externe) » dans le sélecteur existant « Comparer ». La ligne a sa propre base comptable, sa couleur, et le même calendrier est exigé.
- `tests/test_phase_c.py` (10 tests) :
  - critères A6 et A6-bis figés ;
  - détection de chaque défaut : dividende, division, prix ajusté, décote A, dérive cumulée, clôture hors fourchette 10-K, extrême incohérent, fournisseur divergent ; une prime A est acceptée ;
  - lecteur Nasdaq ;
  - comparaison avec bases séparées ;
  - blocage tant que la référence n'est pas validée ;
  - état réel et régression du résultat BRK.B.
- `validate_custom.py` : la comparaison du notebook inclut BRK.B (8 lignes, « Non calculé », base « concentrée »).

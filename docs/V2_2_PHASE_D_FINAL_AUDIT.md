# V2.2 Phase D — Audit final croisé des six références

Date : 18 octobre 2026. Branche `feature/custom-portfolios-v2-1`, HEAD `30aa848`, modifications non commitées. Reproduction : `scripts/run_final_audit.py`, qui écrit `outputs/v2_2/phase_d/` (ignoré par Git) : `phase_d_audit.json`, `equity.html` et `underwater.html`. Fonctions réutilisables : `src/portfolio_lab/v2/final_audit.py`.

**Nature :** analyse exploratoire **a posteriori**, en lecture seule. Aucun résultat, aucune donnée, aucun seuil d'admission ni aucun rapport des Phases A–C n'est modifié. Les trajectoires sont reconstruites en mémoire avec les composants validés.

## 1. Verdict : PASS AVEC RÉSERVES

- **Reproduction** : les 24 chiffres rapportés (6 références × CAGR, volatilité, MaxDD, Sharpe) sont reproduits indépendamment. Aucune incohérence n'apparaît dans les trajectoires, la comptabilité du CAGR, la reconstruction des rendements quotidiens, la volatilité ou les drawdowns. **Aucune condition d'arrêt n'est déclenchée.**
- **Réserves de comparabilité** (non bloquantes, à afficher avec les résultats) :
  1. **Valorisations asynchrones.** BRK.B et le Diversifié utilisent la clôture NYSE de la veille ; les lignes Nasdaq de Research sont des ETF cotés à Paris à 17 h 30.
  2. **Marques figées dans Research.** 36 jours de rendement exactement nul pour B1 et 9 pour B2 : prix inchangé de l'ETF Paris peu échangé (`pea_PUST`).
  3. **Fenêtre COVID fixe.** Elle coupe le creux de BRK.B, qui tombe un jour plus tard.
  4. **Bases comptables** : économique pour BRK.B et le Diversifié, après frais et impôts intermédiaires pour Research.
  5. **A6-bis** est une révision a posteriori.
  6. **Sorties enregistrées** dans les notebooks 01 et 03.

| Référence | CAGR | Vol. jour / sem. / mois | MaxDD (pic → creux) | Remontée | Sharpe EUR | Sortino | Calmar | Pire année |
|---|---|---|---|---|---|---|---|---|
| BRK.B | 12,4 % | 20,6 / 18,5 / 17,2 % | 29,6 % (20/02 → 24/03/2020) | 08/03/2021 | 0,66 | 0,97 | 0,42 | 2020 : −7,3 % |
| Diversifié | 12,7 % | 13,9 / 14,7 / 13,2 % | 29,6 % (19/02 → 23/03/2020) | 09/11/2020 | 0,91 | 1,29 | 0,43 | 2022 : −13,9 % |
| N07 | 27,4 % | 25,6 / 25,4 / 24,7 % | 37,7 % (22/11/2021 → 28/12/2022) | 05/07/2023 | 1,06 | 1,49 | 0,73 | 2022 : −34,8 % |
| D2_25 | 29,6 % | 28,9 / 27,9 / 25,9 % | 45,1 % (19/02 → 23/03/2020) | 26/08/2020 | 1,02 | 1,45 | 0,66 | 2022 : −37,2 % |
| B1 | 19,0 % | 20,6 / 19,3 / 17,8 % | 31,4 % (22/11/2021 → 28/12/2022) | 22/11/2023 | 0,93 | 1,32 | 0,61 | 2022 : −29,8 % |
| B2 | 29,9 % | 39,7 / 37,8 / 36,0 % | 61,2 % (22/11/2021 → 28/12/2022) | non remonté | 0,85 | 1,19 | 0,49 | 2022 : −59,2 % |

## 2. Données et rapprochement comptable (audit A)

- **Calendrier commun : 2 368 séances**, du 01/10/2014 au 29/12/2023 pour les six trajectoires. C'est exactement le calendrier Euronext par règles ; aucune date ne dépasse la coupure.
- **25/12/2019** : la seule date Research absente du calendrier commun (2 369 contre 2 368). C'est une ligne fournisseur un jour de fermeture d'Euronext. Ce jour-là, B1 et B2 ont un rendement de 0, N07 +0,024 % et D2_25 +0,026 % : ce rendement est reporté sur le 27/12, sans perte. Les valeurs finales Research sont identiques sur 2 369 et 2 368 dates. Le 31/12/2015 est absent partout.
- **Valeurs initiales et finales.** BRK.B et le Diversifié valent exactement 100 000 € le premier jour : l'achat se fait au prix de valorisation, sans frais, donc le premier rendement est nul. Les trajectoires Research démarrent entre 99 774 € et 99 840 €, une fois leurs frais du jour 1 déduits. Le CAGR recalculé à partir des valeurs initiale et finale (9,2457 ans) concorde pour les six références.
- **Rendements quotidiens** : `valeur / valeur précédente − 1`, le premier mesuré contre le capital initial. Aucune valeur non finie ou négative.

| Convention | BRK.B | Diversifié | N07, D2_25, B1, B2 (Research gelé) |
|---|---|---|---|
| Horloge | Instantané causal après la clôture de Paris ; clôture NYSE de la veille ; BCE publiée | Idem ; Paris du jour ; Bitcoin du jour UTC précédent | Valeur Research à la séance de Paris ; ETF Nasdaq cotés à Paris (`pea_PUST`, `pea_LQQ`) |
| Exécution | Achat unique au cours de valorisation (idéalisé) | Panier idéal, rééquilibrage mensuel | Moteur Research gelé (bandes, frais) |
| Dividendes | Aucun versé (prix = rendement total) | Réinvestis bruts (SPY, EEM) ; NR (CAC) ; capitalisant (CW8) | Selon les instruments Research |
| Frais et financement | 0 pb ; aucun levier | 0 pb ; aucun levier | Frais de transaction et de garde ; coût du levier dans les ETF ×2 |
| Fiscalité | Aucune | Aucune | Impôts intermédiaires dans la trajectoire ; impôts de sortie seulement dans le CAGR net |
| Rendements nuls exacts | 1 (jour d'achat) | 1 (jour d'achat) | B1 : 36 ; B2 : 9 ; N07, D2_25 : 0 |

**Horloges (diagnostic).** On corrèle chaque trajectoire avec le SPY en EUR (clôture NYSE de la veille).

| Trajectoires | Même instantané | Instantané suivant |
|---|---|---|
| BRK.B, Diversifié | 0,83 ; 0,87 | −0,17 ; 0,08 |
| Research (N07, D2_25, B1, B2) | 0,29 à 0,34 | 0,48 à 0,53 |

Les valeurs Research intègrent donc déjà une partie de la séance américaine du jour, au travers des ETF cotés à Paris. Ce sont des **marques asynchrones, toutes causales** : aucun regard vers l'avant n'est détecté, mais l'information est datée différemment.

**Marques figées Research.** B1 compte 36 rendements nuls exacts sur le calendrier commun (37 sur ses 2 369 dates), concentrés entre 2014 et 2017, presque tous un jour d'ouverture du NYSE. La ligne `pea_PUST` est restée inchangée : ETF peu liquide, dernier cours répété. Ce sont des données Research gelées, ni introduites ni corrigées en V2.2. Elles abaissent légèrement la volatilité quotidienne de B1.

## 3. Volatilité quotidienne, hebdomadaire et mensuelle (audit B)

Rendements composés de valeur de fin de période à valeur de fin de période (vendredi pour la semaine, dernier jour pour le mois), le capital initial servant de point de départ. Annualisation par √252, √52 et √12, sur 2 368, 483 et 111 observations.

| Référence | Quotidienne | Hebdomadaire | Mensuelle | Rang (jour / sem. / mois) |
|---|---|---|---|---|
| B2 | 39,7 % | 37,8 % | 36,0 % | 1 / 1 / 1 |
| D2_25 | 28,9 % | 27,9 % | 25,9 % | 2 / 2 / 2 |
| N07 | 25,6 % | 25,4 % | 24,7 % | 3 / 3 / 3 |
| BRK.B | 20,6 % | 18,5 % | 17,2 % | 4 / 5 / 5 |
| B1 | 20,6 % | 19,3 % | 17,8 % | 5 / 4 / 4 |
| Diversifié | 13,9 % | 14,7 % | 13,2 % | 6 / 6 / 6 |

- **L'égalité apparente BRK.B / B1 (20,6 %) n'existe qu'au jour le jour.** En hebdomadaire et en mensuel, BRK.B est moins volatil que B1, de 0,6 à 0,9 point. La volatilité quotidienne de BRK.B est gonflée par un bruit qui s'annule ensuite : écart d'horloge entre le change BCE de 14 h 15 et la clôture US de la veille, et retour à la moyenne. Ce bruit pèse plus pour une action seule.
- **Le Diversifié reste de loin le moins volatil** à toutes les fréquences. Sa volatilité hebdomadaire légèrement supérieure à la quotidienne (14,7 % contre 13,9 %) traduit plutôt une persistance des mouvements à l'échelle de la semaine.
- Les rangs N07 < D2_25 < B2 sont stables. Aucune série n'a été décalée pour améliorer un indicateur.

## 4. Drawdowns et remontées (audit C)

Reproduits indépendamment avec le pic initial compté, la perte exprimée en positif et l'ordre pic → creux → remontée vérifié. Le module existant situe les mêmes creux.

- **BRK.B contre Diversifié (29,62 % contre 29,65 %) : coïncidence.** Il s'agit du même épisode COVID, mais avec des valeurs distinctes (0,296207 contre 0,296455). Les pics et creux sont décalés d'une séance (20/02 → 24/03 contre 19/02 → 23/03), conséquence de la valorisation BRK.B à la clôture NYSE de la veille. Les remontées n'ont rien à voir : 244 séances après le creux pour BRK.B (08/03/2021), 162 pour le Diversifié (09/11/2020). Ni arrondi commun, ni alignement erroné.
- **Durées** : BRK.B reste sous son pic 382 jours du pic à la remontée, le Diversifié 264 jours, B1 730 jours (2021–2023). B2 n'est toujours pas remonté au 29/12/2023.
- **Temps sous l'eau** (part des séances sous le pic précédent) : 88 % à 94 % pour tous, parce que la moindre baisse sous le pic compte. Ce n'est pas un indicateur discriminant.

| Pire rendement glissant (mois civils composés) | 3 mois | 6 mois | 12 mois |
|---|---|---|---|
| BRK.B | −18,3 % | −21,6 % | −15,1 % |
| Diversifié | −16,5 % | −14,6 % | −13,9 % |
| N07 | −20,2 % | −27,1 % | −34,8 % |
| D2_25 | −20,5 % | −32,1 % | −37,2 % |
| B1 | −18,6 % | −23,9 % | −29,8 % |
| B2 | −40,0 % | −50,0 % | −59,2 % |

**Volatilité et profondeur de drawdown ne sont pas la même chose.** BRK.B a la volatilité de B1 et un MaxDD comparable, mais des pertes sur 12 mois deux fois plus faibles.

Le test automatique `tests/test_phase_d.py` vérifie le signe du MaxDD, l'ordre pic → creux → remontée, l'absence de remontée et la cohérence avec le module existant sur des trajectoires aléatoires.

## 5. Périodes de stress (audit D)

| Période (dates) | BRK.B | Diversifié | N07 | D2_25 | B1 | B2 |
|---|---|---|---|---|---|---|
| T4 2018 (01/10 → 31/12/2018) : rendement | −5,8 % | −10,3 % | −20,2 % | −20,5 % | −15,4 % | −31,9 % |
| T4 2018 : MaxDD dans la fenêtre | 14,1 % (09/11 → 24/12) | 11,9 % | 25,1 % | 25,9 % | 20,9 % | 40,2 % |
| COVID, fenêtre fixe (19/02 → 23/03/2020) : rendement | −24,8 % | −29,3 % | −33,8 % | −43,5 % | −27,0 % | −50,7 % |
| **COVID, épisode pic → creux** | **29,6 %** (20/02 → 24/03) | 29,6 % (19/02 → 23/03) | 35,4 % | 45,1 % | **28,2 %** | 52,2 % |
| COVID : remontée | 08/03/2021 | 09/11/2020 | 13/07/2020 | 26/08/2020 | 19/06/2020 | 06/07/2020 |
| Année 2022 (03/01 → 30/12) : rendement | **+9,5 %** | −13,9 % | −34,8 % | −37,2 % | −29,8 % | −59,2 % |
| 2022 : MaxDD intra-annuel | 22,3 % (28/03 → 21/06) | 15,3 % | 35,5 % | 37,7 % | 30,3 % | 59,9 % |

- **La fenêtre fixe COVID et le drawdown de l'épisode ne mesurent pas la même chose.** La fenêtre fixe s'arrête le 23/03, un jour avant le creux de BRK.B. Sur l'épisode, BRK.B perd **plus que B1** (29,6 % contre 28,2 %) et remonte **près de 9 mois plus tard**. La bonne tenue apparente de BRK.B pendant le COVID est donc **un artefact de fenêtre et d'horloge**.
- **La meilleure tenue de BRK.B au T4 2018 et en 2022 est, elle, réelle** sur les rendements de période. Même en 2022, BRK.B a subi une baisse intra-annuelle de 22 %.

**Toutes les années, sans sélection** :

| Année | 2014 (T4) | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 |
|---|---|---|---|---|---|---|---|---|---|---|
| BRK.B | 14,1 | −1,8 | 26,0 | 7,6 | 6,0 | 14,4 | −7,3 | 41,5 | 9,5 | 11,7 |
| Diversifié | 2,9 | 8,4 | 17,9 | 28,6 | −9,3 | 31,7 | 15,0 | 26,6 | −13,9 | 19,3 |
| N07 | 13,7 | 28,6 | 8,6 | 48,8 | −3,5 | 60,2 | 47,0 | 50,4 | −34,8 | 78,3 |
| D2_25 | 13,9 | 27,8 | 13,8 | 55,2 | 5,8 | 56,8 | 36,2 | 60,9 | −37,2 | 87,1 |
| B1 | 11,0 | 21,7 | 9,0 | 16,1 | 4,7 | 40,4 | 36,0 | 38,7 | −29,8 | 50,1 |
| B2 | 17,9 | 28,2 | 9,9 | 48,5 | −3,6 | 83,3 | 74,2 | 71,2 | −59,2 | 112,3 |

BRK.B est en tête 4 années sur 10 (2014, 2018, 2021, 2022) et dernier 5 années (2015, 2017, 2019, 2020, 2023).

## 6. Risque ajusté (audit E)

Conventions :
- **Sharpe** : excès de rendement quotidien sur le taux EUR au jour le jour de Research (ACT/360, jours civils depuis la séance précédente), annualisé par √252. Même convention pour les six références.
- **Sortino** : même excès ; le rendement cible est le taux sans risque du jour ; l'écart baissier est calculé sur les excès négatifs, annualisé par √252.
- **Calmar** : CAGR / MaxDD.
- **VaR et ES historiques mensuelles à 5 %** : 111 mois, dont seulement **6 dans la queue**. Ces estimations sont **très incertaines**.

| | Sharpe | Sortino | Écart baissier | Calmar | VaR 5 % mens. | ES 5 % mens. |
|---|---|---|---|---|---|---|
| BRK.B | 0,66 | 0,97 | 14,0 % | 0,42 | 7,2 % | 9,0 % |
| Diversifié | 0,91 | 1,29 | 9,9 % | 0,43 | 5,6 % | 7,7 % |
| N07 | 1,06 | 1,49 | 18,2 % | 0,73 | 11,4 % | 12,6 % |
| D2_25 | 1,02 | 1,45 | 20,5 % | 0,66 | 11,3 % | 13,3 % |
| B1 | 0,93 | 1,32 | 14,5 % | 0,61 | 7,2 % | 8,6 % |
| B2 | 0,85 | 1,19 | 28,3 % | 0,49 | 15,3 % | 17,5 % |

Les écarts de Sharpe ne sont pas statistiquement établis (section 8).

## 7. Corrélations et diversification (audit F)

| Corrélation avec BRK.B | Quotidienne (asynchrone) | Hebdomadaire | Mensuelle |
|---|---|---|---|
| Diversifié | 0,69 | 0,68 | 0,65 |
| N07 | 0,22 | 0,48 | 0,53 |
| D2_25 | 0,17 | 0,47 | 0,51 |
| B1 | 0,19 | 0,49 | 0,56 |
| B2 | 0,16 | 0,46 | 0,54 |

- **La fourchette mensuelle 0,51–0,56 publiée en Phase C est reproduite.** Hebdomadaire et mensuel concordent à quelques centièmes près.
- **Les corrélations quotidiennes avec Research ne sont pas fiables** à cause des horloges : même le Diversifié n'affiche que 0,44 à 0,51 en quotidien contre 0,76 à 0,79 en hebdomadaire et 0,80 à 0,81 en mensuel.
- **Bêta par rapport à B1** : BRK.B 0,47 en hebdomadaire et 0,54 en mensuel ; Diversifié 0,58 et 0,59 ; N07 1,26 et 1,33 ; B2 1,91 et 1,98.
- Une corrélation plus faible ne prouve pas qu'ajouter BRK.B améliorerait la performance à long terme.

## 8. Incertitude statistique (audit G)

Méthode :
- bootstrap par blocs mobiles circulaires sur les **lignes quotidiennes alignées** des six références, rééchantillonnées ensemble ;
- 2 000 tirages, graine 20231229 ;
- longueurs de bloc de 5, 21 et 63 séances (sensibilité) ;
- intervalles **descriptifs** à 95 %, pas des tests formels.

| | Bloc 5 | Bloc 21 | Bloc 63 |
|---|---|---|---|
| Volatilité BRK.B | 18,8–22,8 % | 18,0–24,1 % | 17,7–24,5 % |
| Vol. BRK.B − Diversifié | +5,8 à +7,8 pts | +5,6 à +8,1 | +5,6 à +8,1 |
| Vol. BRK.B − B1 | −1,5 à +1,9 | −1,8 à +2,2 | −2,0 à +2,2 |
| Vol. BRK.B − N07 | −6,8 à −2,8 | −7,3 à −2,4 | −7,6 à −2,1 |
| Sharpe BRK.B | 0,09–1,25 | 0,09–1,28 | 0,18–1,24 |
| Sharpe BRK.B − Diversifié | −0,80 à +0,27 | −0,81 à +0,27 | −0,81 à +0,29 |
| Sharpe BRK.B − N07 | −1,05 à +0,24 | −1,01 à +0,26 | −0,98 à +0,26 |
| Sharpe BRK.B − B1 | −0,91 à +0,37 | −0,84 à +0,33 | −0,82 à +0,37 |
| Sharpe BRK.B − B2 | −0,86 à +0,45 | −0,80 à +0,42 | −0,75 à +0,48 |

- **Robuste** : BRK.B est plus volatil que le Diversifié et moins volatil que N07, D2_25 et B2.
- **Indiscernable** : la volatilité de BRK.B et celle de B1.
- **Aucune différence de Sharpe** impliquant BRK.B n'est établie : tous les intervalles contiennent 0. Avec environ 9 ans d'historique, un Sharpe d'environ 0,7 a un intervalle d'environ ±0,6.

## 9. Sensibilité aux fenêtres (audit H)

| Fenêtre | CAGR BRK.B (rang) | Sharpe BRK.B (rang) | Premier au Sharpe |
|---|---|---|---|
| Complète | 12,4 % (6e) | 0,66 (6e) | N07 1,06 |
| 2015–2019 | 10,0 % (6e) | 0,61 (6e) | Diversifié 1,15 |
| 2020–2023 | 12,6 % (5e) | 0,60 (6e) | N07 0,97 |

- La conclusion « BRK.B a le Sharpe le plus bas » tient dans les deux sous-périodes. En revanche, la position du Diversifié en dépend : 1er en 2015–2019, 5e en 2020–2023.
- L'écart de CAGR avec les stratégies Nasdaq vient des deux sous-périodes, pas seulement de 2020–2023.
- Par année civile, BRK.B est 1er au Sharpe en 2014, 2018, 2021 et 2022, et dernier en 2015, 2017, 2019, 2020 et 2023 : très instable d'une année à l'autre.
- Ces fenêtres ont été définies à l'avance et ne sont pas optimisées.

## 10. Régression de l'admission BRK.B (audit I)

- **A6 d'origine** : 10 sur 12 conformes. Les 2 échecs restent publiés : écart A/B maximal (341,7 pb) et corrélation quotidienne A/B (0,974).
- **A6-bis** (révision a posteriori approuvée) : tous conformes, avec des seuils inchangés.
- **Contrôle contre des clôtures quotidiennes observées de façon indépendante** : Nasdaq.com, sur 1 813 séances (17/10/2016 → 29/12/2023), écart maximal 1,01 pb.
- **Contrôle contre les fourchettes trimestrielles officielles** (10-K 2015, NYSE Composite) : **337 clôtures Yahoo par classe** (21 au T3 2014 partiel, puis 64, 61, 63, 64 et 64) confrontées à **6 fourchettes trimestrielles par classe**, dont 5 trimestres complets pour la comparaison des extrêmes (écart ≤ 4,5e-6). **Ce ne sont pas 337 contrôles indépendants de clôtures officielles** : la vérification porte sur l'appartenance aux fourchettes et sur les extrêmes trimestriels.
- **Correction de compte rendu** : un message intermédiaire de la Phase C mentionnait « 274 clôtures » ; le bon chiffre, documenté dans `V2_2_PHASE_C_BRK.md`, est 337.
- **Prix et ajustements** : aucun dividende ni division d'actions ; clôture ajustée = clôture ; empreintes brutes conformes au manifeste. Le niveau EUR admis est reproduit exactement à partir de la clôture et de la BCE (écart 3e-16). Aucune correction de prix n'a été appliquée à BRK.B.

## 11. Tests et empreintes (audit J)

Résultats de la validation finale :
- 178 tests réussis : 50 V2, 61 constructeur, 41 admission, 9 Phase B, 10 Phase C, 7 Phase D ;
- `validate_v2.py` : 88/88 indicateurs et 10/10 contrôles comptables ;
- `validate_custom.py` : PASS ;
- 12 empreintes Research identiques avant et après ;
- empreintes des niveaux, des catalogues, des notebooks et des rapports des Phases B et C inchangées.

Les notebooks 01 et 03 contiennent des sorties et des compteurs d'exécution enregistrés par l'utilisateur (le 03 aussi une métadonnée de noyau local, « .venv (3.10.11) »). **Leurs sources sont identiques à HEAD**, mais la politique du dépôt exige des notebooks versionnés sans sorties. **Recommandation** : ne pas les indexer, ou les restaurer ou vider avant un commit, sur décision du propriétaire. Rien n'a été nettoyé automatiquement. Les notebooks 02 et 04 sont sans sorties.

**Liste proposée pour un commit séparé, à autoriser** :

| Catégorie | Fichiers |
|---|---|
| Modules | `src/portfolio_lab/v2/admission.py`, `backtest_checks.py`, `final_audit.py`, `yahoo_bounded.py` ; modifiés : `custom_analytics.py`, `custom_ui.py` |
| Scripts | `scripts/fetch_reference_data.py`, `prepare_custom_data.py`, `import_cac40.py`, `bound_bourse_direct.py`, `run_diversified_backtest.py`, `prepare_brk_benchmark.py`, `run_brk_benchmark.py`, `run_final_audit.py` ; modifié : `validate_custom.py` |
| Configuration | `config/v2/custom_assets.yaml` (modifié), `config/v2/custom_benchmarks.yaml` |
| Tests | `tests/test_admission.py`, `test_phase_b.py`, `test_phase_c.py`, `test_phase_d.py` ; modifié : `test_custom.py` |
| Documentation | `docs/V2_2_DATA_ADMISSION.md`, `V2_2_PHASE_B_RESULTS.md`, `V2_2_PHASE_C_BRK.md`, `V2_2_PHASE_D_FINAL_AUDIT.md` ; `README.md` (modifié) |
| Notebook | `notebooks/04_portefeuilles_personnalises.ipynb` (texte seulement, sans sorties) |
| **À exclure** | `notebooks/01_*.ipynb`, `notebooks/03_*.ipynb` (sorties seules) ; `outputs/` et `data/v2_1/` restent ignorés : données de marché sous licences de fournisseurs, rapports générés |

## 12. Limites et points à trancher avant commit

1. **Comparaison BRK.B / Research** : les horloges diffèrent (marques causales mais asynchrones). Seules les mesures hebdomadaires, mensuelles et de période sont pleinement comparables. Les corrélations et bêtas quotidiens ne doivent pas être utilisés.
2. **Marques figées de B1 et B2 dans Research (2014–2017)** : propriété des données gelées. Elle n'est pas corrigée, car Research est en lecture seule.
3. **Fenêtres fixes de stress** : elles dépendent de l'horloge. Il faut privilégier les drawdowns d'épisode, du pic au creux.
4. **A6-bis et seuils A1, A2 et A3b** : formulés après observation et documentés comme tels.
5. **Échantillon unique d'environ 9 ans** : différences de Sharpe non établies, queues de distribution estimées sur 6 mois.
6. **Bases fiscales** : CAGR économiques (BRK.B, Diversifié) et CAGR net fiscal Research ne sont jamais classés ensemble.
7. **Avant commit** : décider du sort des sorties des notebooks 01 et 03, puis lancer un commit séparé une fois autorisé.

**Le dépôt est prêt pour un commit et un push autorisés séparément, une fois la question des notebooks 01 et 03 tranchée.** Rien n'a été commité ni poussé.

# Portefeuille personnalisé — vérification du 18 octobre 2026

Le portefeuille **Mon portefeuille diversifié** est créable, renommable, enregistrable et rechargeable sans historique validé. Allocation conservée : EM 30 %, S&P 500 30 %, World 15 %, CAC 40 10 %, or 10 %, Bitcoin 5 %. Capital 100 000 €, mensuel, frais 0 pb, EUR, du 01/10/2014 au 29/12/2023. Le backtest complet reste bloqué pour les raisons documentées ci-dessous.

## Notebook 04 et persistance

Le code existant séparait déjà `save_spec` du chargeur de marché. Aucun défaut de sauvegarde lié aux données n'a été reproduit. Le message de l'éditeur précise maintenant que la configuration est valide et enregistrable même lorsque la simulation est indisponible. La confirmation donne le nom du fichier JSON.

Les nouveaux tests utilisent les boutons réels et un dossier temporaire : création du nom exact, allocation exacte, sauvegarde, modification du nom et des poids, puis rechargement depuis une nouvelle instance du constructeur. Ils couvrent les six sources `missing` puis `pending_validation`, avec toute lecture de données de marché interdite par le test. Les poids invalides bloquent toujours la sauvegarde. Le validateur exécute aussi le notebook 04 dans un noyau neuf et vérifie cette persistance sur disque. La configuration initiale n'est pas écrasée.

L'interface exige un noyau Python actif et les widgets Jupyter ; un ancien affichage sauvegardé dans le notebook n'exécute pas les nouveaux callbacks. Relancer la cellule `builder = open_builder()` après redémarrage du noyau pour charger le code actualisé. Pour la publication finale, la sortie préexistante a été sauvegardée localement dans `outputs/v2_1/prepublication/` (ignoré par Git), puis retirée du notebook source. Voir la [validation de publication](V2_1_RELEASE_VALIDATION.md).

## FR0007080973 : un véritable ancien fonds, mais pas une continuité CAC 40 jusqu'en 2023

L'antériorité au développement est confirmée : première VL au **28/02/2003**. Il ne faut pas confondre ce fonds avec la part récente FR0013380607.

- Le [document de cotation Borsa Italiana de juillet 2011](https://www.borsaitaliana.it/etf/notiziedettaglio/4etfamundi12luglio2011.pdf), pages 2–4 et 7, identifie FR0007080973, classe C, ticker C40, EUR, capitalisation et indice CAC 40 net return. La réplication y est alors décrite comme synthétique : une description actuelle « physique » ne doit pas être rétroprojetée sur toute l'histoire.
- La [fiche officielle Amundi du successeur](https://www.amundietf.com/pdfDocuments/monthly-factsheet/LU1681046931/FRA/FRA/INSTITUTIONNEL/ETF) documente l'absorption du fonds français le **14/02/2018**, la classe capitalisante **LU1681046931**, et la première VL du prédécesseur en 2003. Cette histoire marketing ne certifie ni la présence de toutes les VL ni leur raccordement exact.
- Le [communiqué Amundi publié par Crédit Agricole le 7 avril 2022](https://presse.credit-agricole.com/amundi-etoffe-sa-gamme-detf-esg-actions/?lang=fra) établit le changement effectif d'indice au **21/03/2022** : CAC 40 → **CAC 40 ESG**. Le [DIC du 30/10/2023](https://www.amundietf.lu/pdfDocuments/download/feacd265-0bd0-4b59-9bc7-4d0301cb1a51/KIDPRIIPs_390343_51648_LUX_FRA_20231030.pdf) identifie bien le successeur ESG pendant la fenêtre autorisée.

La capitalisation incorpore le réinvestissement des revenus dans la VL : il ne faut pas ajouter une seconde fois des dividendes. Le rendement du fonds comprend frais, retenues effectivement subies et écart de suivi ; il ne devient pas un indice officiel NR/GR ni un rendement net fiscal personnel. Le rapport d'échange de 2018, les VL de part et d'autre de l'opération, les changements de réplication et un registre exhaustif des opérations restent à corroborer. Aucun ratio, split ou rendement de raccord n'a été supposé.

**Disponibilité vérifiée dans cet environnement :** deux POST Euronext, un par ISIN français/luxembourgeois, avec `adjusted=Y`, `startdate=2014-10-01`, `enddate=2023-12-29`, `nbSession=10`, sans redirection automatique. Réponses HTTP 200, `application/json`, respectivement 2 857 et 2 847 octets, uniquement les clés `ct`, `iv`, `s`. Aucun tableau quotidien lisible obtenu. Les paramètres ne démontrent pas que la fenêtre est respectée ; `adjusted=Y` ne démontre pas un traitement de dividendes. Le journal local est `outputs/v2_1/cac40_availability_probe.json`, sans corps de cotations.

**Conclusion : aucune série quotidienne complète et fiable de ce candidat n'a été obtenue ni admise.** Cela ne démontre pas l'inexistence d'archives chez un fournisseur. Même un export complet raccordé au successeur décrirait une exposition devenue ESG en mars 2022 : il ne pourrait pas être étiqueté silencieusement « CAC 40 » sur toute la période. Le nom C40 seul ne suffit pas à identifier l'exposition historique. Les pages justETF et autres annuaires ne remplacent pas la preuve de continuité de l'émetteur.

## Audit numérique des cinq autres séries

Commande reproductible : `python -B scripts/audit_custom_data.py` avec `PYTHONPATH=src`. Aucun module Research importé ou exécuté. Les six fichiers utiles (panel + cinq sources brutes) sont épinglés par SHA-256 ; `ResearchGuard` contrôle l'intégrité et la date maximale avant lecture des valeurs. Tous se terminent au plus tard le 29/12/2023. Le résultat détaillé est `outputs/v2_1/custom_data_audit.json`, ignoré par Git. La fenêtre est toujours 01/10/2014–29/12/2023.

| Actif | Contrôles obtenus | Validation restant nécessaire |
|---|---|---|
| EM — EEM, US4642872349 | 2 328 observations brutes et panel ; 20 distributions ; aucun split signalé dans la fenêtre. Reconstruction indépendante `(Close + distribution) / Close précédent`, comparée à AdjClose : écart relatif maximal 4,87 pb entre trajectoires normalisées. | Expliquer/corroborer cet écart auprès d'une source externe, vérifier toutes les distributions et les dates/heures des cours et du change. Le raccord VEIEX est antérieur à cette fenêtre. |
| S&P 500 — SPY, US78462F1030 | 2 328 observations ; 37 distributions trimestrielles dans la fenêtre partielle ; aucun split ni gain en capital signalé. Écart relatif maximal TR explicite/AdjClose 8,76 pb. | Même contrôle externe et temporel. L'écart n'a pas été ramené artificiellement à zéro. |
| World — CW8.PA | 2 369 observations EUR brutes ; zéro distribution/split signalé ; valeurs du panel identiques aux clôtures brutes aux dates communes. Aucun cas déclenchant la règle Research de correction à voisin futur dans cette fenêtre. | **21 dates du panel sans observation brute et 62 séances brutes absentes du panel** : le report provient du calendrier US. Certifier le raccord juridique de 2018 et adopter un calendrier/une heure explicites avant simulation. |
| Or — GLD, US78463V1070 | 2 328 observations USD ; zéro distribution/split signalé ; Close et AdjClose normalisés concordent à la précision flottante. | Vérifier indépendamment les clôtures et le change. GLD supporte ses propres frais ; ce n'est pas de l'or physique sans frais. |
| Bitcoin — BTC-EUR | **3 377 dates consécutives**, sans jour manquant ; les 2 328 valeurs du panel sont exactement les clôtures brutes de mêmes dates. Deux mouvements quotidiens absolus >25 % signalés, 07/12/2017 et 12/03/2020 ; aucune correction appliquée. | Corroborer les observations extrêmes, la définition de la clôture et son heure effective de disponibilité ; un libellé de date/« 00:00 UTC » ne suffit pas à exclure une clôture de fin de journée future. |

Aucun doublon, désordre, niveau non fini/non positif ou clôture ajustée invalide constaté sur ces cinq fenêtres ; bornes exactes présentes. Ces résultats valident la structure locale, pas l'exhaustivité au regard de calendriers officiels indépendants ni la qualité économique de chaque observation. L'absence de split dans les fichiers est une déclaration du fournisseur, pas une preuve indépendante d'absence de toute opération.

Identités et politiques corroborées par les émetteurs : [EEM / iShares](https://www.ishares.com/us/literature/fact-sheet/eem-ishares-msci-emerging-markets-etf-fund-fact-sheet-ja-jp.pdf), [SPY / State Street](https://www.ssga.com/us/en/intermediary/etfs/state-street-spdr-sp-500-etf-trust-spy), [GLD / State Street](https://www.ssga.com/us/en/intermediary/etfs/spdr-gold-shares-gld). Pour CW8, [Amundi](https://www.amundietf.fr/pdfDocuments/monthly-factsheet/LU1681043599/ENG/FRA/INSTITUTIONNEL/ETF) documente l'absorption du fonds français le 18/04/2018. Une série Yahoo portant le même ticker de part et d'autre ne certifie pas à elle seule les ajustements de cette opération.

Les EUR/USD normalisés déduits séparément de EEM, SPY et GLD et du panel concordent à environ `7,8e-15` près. C'est un contrôle de cohérence arithmétique, **pas une validation du fixing de change**. Le code Research utilise le change du même jour, avec report et nettoyage d'anomalies dont la règle inspecte l'observation suivante. Le code d'origine n'a pas été modifié ; aucun nettoyage ni report n'a été appliqué par ce nouvel audit.

Les documents de fonds récents ont servi uniquement à identifier les instruments, politiques et événements. Des extraits web comportaient spontanément des chiffres postérieurs à 2023 ; ils n'ont été ni intégrés à un jeu de données ni utilisés pour la simulation. Aucune requête historique ne dépasse la coupure et aucun fichier local TEST n'a été ouvert.

## Ce qui empêche encore le backtest complet

1. Une série CAC 40 à rendement total couvrant toute la fenêtre, avec données quotidiennes lisibles, calendrier vérifié et contrôles indépendants. FR0007080973/LU1681046931 ne résout pas seul ce point à cause de l'absorption et du changement ESG.
2. La validation externe des distributions/ajustements EEM et SPY, du raccord CW8 et des observations GLD/BTC ; la comparaison de deux champs Yahoo n'est pas une seconde source indépendante.
3. Une convention commune et causale Paris/États-Unis/FX/crypto, avec heures de disponibilité démontrées. Le panel US existant ne peut pas être présenté comme un panier exécuté simultanément à Paris. Aucun choix implicite d'intersection, remplissage ou délai n'a été fait.
4. Après résolution, des séries EUR et leur calendrier commun dans `data/v2_1`, avec empreintes et provenance. Les six entrées du catalogue restent non admises ; aucune performance complète n'est produite.

Portfolio Research demeure en lecture seule ; les douze empreintes gelées sont revérifiées avant/après l'audit. TEST 2024–2026 demeure verrouillé. Aucun commit ni push. BRK.B reste hors périmètre.

## Résultats de validation

- Suite complète : **111 tests réussis**, 10,25 s (`python -B -m pytest -q -p no:cacheprovider`).
- `scripts/validate_custom.py` : notebook dans un noyau neuf, nom/allocation exacts, sauvegarde et relecture sur disque, contrôles de poids invalides et blocage historique réussis. Analyses synthétiques et douze empreintes gelées inchangées : PASS. Le notebook source n'a pas été réécrit.
- `scripts/audit_custom_data.py` : audit borné réussi, six empreintes de sources conformes et douze empreintes Research identiques avant/après. Aucune donnée admise automatiquement au backtest.
- `git diff --check` : aucune erreur d'espacement. Modifications et fichiers utilisateur préexistants conservés ; aucune indexation, aucun commit ni push.

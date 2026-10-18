# V2.2 — Admission des données historiques du portefeuille diversifié

Date : 18 octobre 2026. Branche `feature/custom-portfolios-v2-1`, base `30aa848e067f08c6d58b3d3ab656949744516aec`, modifications non commitées.

**Décision finale du 18/10/2026 : Phase A COMPLÈTE.** Les six actifs sont validés : amendements A1–A5 et A3b approuvés, CAC 40 NR admis avec deux corrections officielles déclarées (fichiers bruts intacts). La Phase B est exécutée : `docs/V2_2_PHASE_B_RESULTS.md`. Phase C (BRK.B) non commencée. Aucun backtest historique du portefeuille n'a été exécuté (Phase B), et BRK.B n'a pas été abordé (Phase C). Les statuts d'origine et le détail des amendements figurent en section 10.

| Actif | Source | Statut | Motif principal |
|---|---|---|---|
| Marchés émergents | EEM + distributions, change BCE | **VALIDÉ** | Écart de −0,53 %/an contre MSCI EM NR, corrélation mensuelle 0,984 ; change selon A1. |
| S&P 500 | SPY + distributions, change BCE | **VALIDÉ** | Écart de −0,087 %/an contre le S&P 500 TR ; critères de dérive A2 conformes ; change selon A1. |
| MSCI World | CW8.PA, EUR | **VALIDÉ** | 4/4 contrôles contre MSCI World NR EUR officiel (sans amendement). |
| CAC 40 | NR QS0011131826, export Bourse Direct borné date d'abord ; référence prix `^FCHI` (Yahoo) | **VALIDÉ** (avec corrections, voir « Corrections officielles ») — historique : BLOQUÉ | Calendrier et identité conformes, écart NR − prix +2,31 %/an. Mais le contrôle « NR jamais sous le prix de plus de 1 pb » échoue sur 2 séances qui s'inversent le lendemain : 27/06/2016 (−111 pb) et 19/10/2020 (−27 pb). Il faut une troisième référence (section 7). |
| Or | GLD, change BCE | **VALIDÉ** | 4/4 contrôles contre IAU ; change selon A1. |
| Bitcoin | Composite Bitstamp (A3) ; Yahoo/CMC rejeté | **VALIDÉ** | Consensus par plateforme A3b (Bitfinex, Coinbase) : 16/16 contrôles. La prime de décembre 2017 est propre à Coinbase, ce que confirme Bitfinex EUR. Les 3 échecs A3 restent publiés (sections 10.3 et 10.5). |

## 1. Base de départ reproduite

Avant toute modification, le dépôt était propre et HEAD correspondait à la référence. Les validations V2.1 ont été reproduites à l'identique :

- 111 tests ;
- `validate_v2.py` : 88/88 indicateurs et 10/10 contrôles comptables ;
- `validate_custom.py` : PASS ;
- `audit_custom_data.py` : mêmes 2 328 observations, 20 et 37 distributions, 4,87 et 8,76 pb, 21 et 62 écarts CW8, 3 377 dates BTC ;
- empreintes des 12 artefacts Research identiques.

## 2. Convention temporelle retenue : `euronext_close_snapshot_asof_v1`

Les courbes Research gelées sont sur un calendrier de Paris, avec la clôture américaine de la veille. La comparaison V2.1 exige déjà `research_alignment = validated_paris_session_end`. La convention retenue reprend ce cadre et rend chaque horloge explicite dans [admission.py](../src/portfolio_lab/v2/admission.py).

- **Une valorisation par séance Euronext Paris D**, à 17 h 40 heure de Paris (14 h 10 lors des demi-séances des 24 et 31 décembre). Le calendrier est construit par règles : 1er janvier, Vendredi saint, lundi de Pâques, 1er mai, 25 et 26 décembre. Il compte 2 369 séances.
- **CW8 et CAC 40** : clôture de D. Une séance manquante provoque un échec, sauf exception déclarée.
- **SPY, EEM, GLD** : dernière clôture NYSE disponible, en pratique celle de J−1. 16 h à New York tombe toujours après 17 h 40 à Paris, y compris pendant les semaines où les changements d'heure sont décalés (mars et octobre-novembre). Le calendrier NYSE est construit par règles, y compris Juneteenth depuis 2022 et la fermeture du 05/12/2018. Il coïncide exactement avec les observations de SPY, EEM, GLD, IAU et ^SP500TR.
- **EUR/USD** : dernier cours de référence BCE publié, considéré disponible à 16 h à Francfort. Pendant les demi-séances, c'est le fixing de la veille qui est utilisé.
- **BTC-EUR** : dernière clôture d'un jour UTC, c'est-à-dire la bougie de J−1 clôturée à 0 h UTC. Une corrélation quotidienne de 0,986 le même jour UTC, contre −0,04 et −0,03 avec un décalage de ±1 jour, confirme la convention du fournisseur.
- **Ancienneté maximale** : 5 jours pour les cours US et la BCE, 1 jour pour BTC, 0 jour pour Paris. Au-delà, l'échec est explicite : pas de report silencieux, pas d'interpolation, pas d'intersection de calendriers.
- **Âges observés** : 1 à 4 jours pour les cours US (1 839, 18, 459 et 53 séances) ; 0 jour pour la BCE sur 2 357 séances, 1 jour sur 10 et 3 jours sur 2 (demi-séances) ; toujours 1 jour pour BTC. Chaque niveau garde sa date source et son instant de disponibilité dans `outputs/v2_1/asof/<ACTIF>.csv`.
- **Jours de marché partiel** : à Thanksgiving, la clôture US du mercredi sert le jeudi et le vendredi. Le 1er mai, quand seul le marché US est ouvert, sa clôture est intégrée à la séance de Paris suivante.

Les tests couvrent les 2 369 séances, les changements d'heure, les débuts de mois (par exemple 02/01/2017 : clôture US du 30/12/2016, 3 jours) et une valeur US future empoisonnée, jamais visible.

**Limite assumée :** il s'agit d'une *valorisation causale*, pas d'un ordre de panier exécutable simultanément. Les lignes US sont échangées au dernier cours connu, ce qui est une idéalisation. Le dimensionnement des ordres de Paris utilise la valorisation de l'instantané. Le change de 14 h 15 et les clôtures US de la veille sont combinés de façon causale, mais pas au même instant.

## 3. Constat calendrier : CW8 et calendrier Research gelé

Le calendrier par règles révèle deux anomalies chez le fournisseur, qui se retrouvent dans le calendrier Research de 2 369 dates :

- le **25/12/2019**, Euronext était fermé. La ligne a O = H = L = C = clôture du 24/12, soit une répétition sans information : elle est retirée après vérification ;
- le **31/12/2015**, demi-séance ouverte, aucune ligne n'existe. La clôture du 30/12 est reprise (1 jour). Ce jour-là, MSCI World NR EUR a varié de −0,35 %, soit environ −5 pb de portefeuille décalés d'une séance.

Ces deux exceptions sont déclarées dans `VENDOR_EXCEPTIONS` et testées. Toute autre lacune fait échouer le traitement. **Conséquence pour la Phase B :** le calendrier Research et le calendrier par règles partagent 2 368 dates. La comparaison V2.1, qui exige des index identiques, refusera donc à juste titre. Un adaptateur explicite restreint aux dates communes sera nécessaire. Research n'est pas modifié.

## 4. Tolérances déclarées avant calcul

Elles ont été fixées dans `TOLERANCES` avant toute comparaison externe et sont figées par un test. Les références suivantes sont indépendantes des séries testées par leur émetteur ou leur fournisseur :

| Contrôle | Référence | Limites |
|---|---|---|
| Change | WM/Refinitiv 16 h Londres, déduit de MSCI World NR USD/EUR | Médiane ≤ 15 pb, 99e centile ≤ 80 pb, maximum ≤ 300 pb. Les fixings sont espacés d'environ 2 h 45. |
| SPY | ^SP500TR (S&P DJI), même clôture | Écart annualisé dans [−0,30 %, 0], corrélation quotidienne ≥ 0,999, 99e centile ≤ 20 pb, dates ex-dividende ≤ 25 pb |
| EEM | MSCI EM NR USD officiel | Écart dans [−1,5 %, +0,25 %]/an, corrélation mensuelle ≥ 0,95 (les clôtures asiatiques précèdent New York), écart annuel ≤ 3 % |
| CW8 | MSCI World NR EUR officiel | Écart dans [−1 %, +0,5 %]/an, corrélation mensuelle ≥ 0,95, écart annuel ≤ 3 %, absorption du 18/04/2018 ≤ 100 pb |
| GLD | IAU (iShares, autre sponsor et dépositaire) | Écart dans [−0,40 %, +0,10 %]/an, corrélation quotidienne ≥ 0,99, 99e centile ≤ 50 pb, regroupement IAU du 24/05/2021 ≤ 100 pb |
| BTC | Bitstamp BTC/EUR (dès le 16/04/2016) ; BTC/USD ÷ BCE avant | EUR : médiane ≤ 50 pb et 99e centile ≤ 300 pb. USD : médiane ≤ 100 pb et 99e centile ≤ 500 pb. Corrélation ≥ 0,95 et meilleure le même jour qu'à ±1 jour. Mouvements extrêmes ≤ 5 pp |

## 5. Résultats et analyse des écarts

| Actif | Valeurs mesurées (la limite suit l'écart quand elle n'est pas satisfaite) |
|---|---|
| WORLD | Écart −0,11 %/an ; corrélation mensuelle 0,988 ; écart annuel max 1,51 % ; absorption 2018 : 6,8 pb. **Conforme.** |
| EM | Écart −0,53 %/an ; corrélation mensuelle 0,984 ; écart annuel max 1,56 %. Conforme hors change. |
| GOLD | Écart −0,14 %/an, cohérent avec la différence de frais de 0,15 % ; corrélation 0,997 ; 99e centile 21 pb ; regroupement 6,4 pb. Conforme hors change. |
| SP500 | Écart −0,09 %/an, proche des frais de 0,0945 % ; ex-dividende max 16 pb ; **corrélation 0,99869 < 0,999 ; 99e centile 21,0 > 20 pb.** |
| Change | Médiane 14,7 pb ; **99e centile 102 > 80 pb** ; maximum 267 pb. |
| BTC | Médiane EUR 18,6 pb ; **99e centile EUR 340 > 300 pb** ; avant 2016, médiane 39 et 99e centile 268 pb ; **07/12/2017 : écart de 6,4 pp > 5** ; 12/03/2020 : 1,5 pp. |

L'investigation menée après contrôle ne sert pas de critère :

- **Change.** Les plus gros écarts tombent sur des annonces publiées entre 14 h 15 et 17 h. Il s'agit de conseils BCE (22/01/2015, 22/10/2015, 03/12/2015, 10/03/2016, 08/12/2016, 12/03/2020) et de statistiques US (03/06/2016, 13/09/2022, 10/11/2022). L'autocorrélation est de 0,04. L'écart vaut +3,5 pb au début et −2,7 pb à la fin, soit environ 6 pb d'effet cumulé sur la conversion. Aucune erreur de niveau n'apparaît : c'est un mouvement intrajournalier réel. Le fixing BCE est la source officielle.
- **SPY.** L'autocorrélation des écarts quotidiens est de −0,57 : les écarts s'inversent le lendemain. Exemples : +104 puis −60 pb les 16 et 17/03/2020 ; +61 puis −54 pb lors de la demi-séance du 03/07/2019. Les écarts annuels vont de −26 à +4 pb. Il n'y a pas de dérive des dividendes.
- **BTC.** L'autocorrélation est de 0,7. L'écart de CoinMarketCap face à Bitstamp EUR dépasse 6 % pendant plusieurs jours en décembre 2017 : la série agrégée intègre des plateformes à prime. Au 99e centile, il atteint 539 pb en 2016 et 613 pb en 2017, puis 76 à 101 pb en 2022-2023. L'effet sur le cumul est de −47 pb sur neuf ans, mais le chemin s'écarte d'un prix exécutable en EUR, notamment lors des rééquilibrages de décembre 2017.

**Amendements proposés, non appliqués, car formulés après observation :**

1. Change : remplacer le 99e centile par des critères d'erreur de niveau, à savoir |autocorrélation| < 0,2, écart aux bornes ≤ 10 pb et écarts > 100 pb rattachés à un événement daté.
2. SPY : évaluer la corrélation sur deux séances, qui vaut 0,99931, et garder les critères d'écart annuel et ex-dividende.
3. BTC : choisir une source primaire exécutable en EUR, par exemple Bitstamp BTC/EUR dès 2016 avec une règle explicite avant, et la valider par une autre plateforme.

Ces choix méthodologiques reviennent au propriétaire. Aucun statut n'a été modifié pour débloquer l'interface.

## 6. Distributions, ajustements et devise

- SPY (37 distributions) et EEM (20) : le rendement total est explicite, `(Close + distribution) / Close précédent`, réinvesti brut à la clôture ex-date sans retenue à la source. Une division d'actions dans la fenêtre est refusée. Les écarts avec AdjClose (8,76 et 4,87 pb) viennent de la convention d'ajustement Yahoo et ne sont pas utilisés.
- GLD et IAU ne versent pas de distribution. Le regroupement 1 pour 2 d'IAU du 24/05/2021 est déjà ajusté chez le fournisseur : l'écart du jour avec GLD est de 6,4 pb.
- CW8 est capitalisant et coté en EUR : aucun dividende n'est ajouté et aucune conversion n'est nécessaire.
- Conversion EUR des lignes US : `niveau USD selon l'horloge NYSE / USD par EUR BCE selon l'horloge de publication`. Les niveaux sont normalisés à 100 au 01/10/2014.
- Les frais des ETF et ETC restent incorporés. Aucun rendement fiscal personnel n'est calculé.

## 7. CAC 40 : décision d'acquisition

Deux nouvelles routes bornées ont été essayées, en plus de celles de la V2.1 :

1. Le téléchargement complet Euronext `getFullDownloadAjax` (distinct du `getHistoricalPricePopup` déjà essayé), pour NR et GR. Réponse HTTP 200 avec l'en-tête « From 2014-10-01 to 2023-12-29 » mais **aucune ligne**, y compris pour décembre 2023 seul. Le service public ne sert que l'historique récent.
2. L'API onvista. L'indice officiel est bien identifié : `FRANCE CAC 40(TRG)`, QS0011131834, et `(TRN)`, QS0011131826. L'historique est **refusé (HTTP 403)**, avec un renvoi aux conditions d'utilisation. Ce refus n'a pas été contourné.

Stooq a présenté un défi anti-robot JavaScript : il n'a pas été contourné, et son prix CAC n'aurait de toute façon servi que de référence. Aucune série de prix seule, aucun ETF et aucun raccord FR0007080973/LU1681046931 (passé au CAC 40 ESG en 2022) n'a été substitué.

**Export minimal requis de votre part :**

- Indice CAC 40 **Gross Return QS0011131834** (préféré) ou **Net Return QS0011131826**.
- Clôtures quotidiennes en EUR, **du 2014-10-01 au 2023-12-29 strictement**, exportées avec cette borne de fin.
- Format Euronext « Historical Data » (`;`, jj/mm/aaaa, ligne ISIN au-dessus de l'en-tête `Date;…;Close`).
- Plus une référence indépendante sur la même fenêtre : le CAC 40 prix FR0003500008, ou l'autre variante TR. Elle permet de vérifier que GR ≥ NR ≥ prix chaque séance, à 1 pb près.
- Fournisseur : Euronext Web Services EOD ou Market Data, avec une licence de recherche locale. Les exports bruts restent dans `data/v2_1/raw/cac40/`, ignoré par Git, et ne sont jamais commités.

Commande, depuis la racine avec `PYTHONPATH=src` :

```powershell
.\.venv\Scripts\python.exe -B scripts/import_cac40.py --export <GR.csv> --reference <prix.csv> --provider "Euronext EOD" --license "<référence>" --update-catalog
```

L'import rejette avant toute lecture de valeurs un fichier contenant une date postérieure au 29/12/2023. Les dates `jj/mm` et `mm/jj` sont lues dans les deux ordres, ainsi que le format `Dec 29, 2023`. Il refuse le prix seul, un ISIN inconnu, une séance manquante ou une date hors séance. Sans référence, le statut reste `pending_validation`.

### Pistes du passage de relais (18/10/2026)

**Constat commun.** Investing.com renvoie HTTP 403 à tout accès automatisé, y compris sur sa page de conditions d'utilisation (protection anti-robot). Le téléchargement d'historique y exige un compte connecté. Je ne peux ni contourner cette protection, ni créer de compte, ni me connecter. Je n'ai pas ouvert les pages d'historique Investing ni celle des dividendes Parqet : elles affichent par défaut des cours ou des distributions de 2024–2026. Les deux pistes passent donc par un **export manuel de votre part**, que l'import accepte désormais directement. Investing.com avertit que ses données ne sont pas nécessairement exactes : la vérification indépendante reste obligatoire.

**Piste 1 — indice CAC 40 NR (PX1NR, QS0011131826), recommandée.** Sur la page d'historique Investing.com « CAC 40 NR » :
- fixer la période **01/10/2014 → 29/12/2023** et la fréquence « Daily » **avant** l'export, puis télécharger le CSV (colonnes `Date, Price, Open, High, Low, Vol., Change %`) ;
- faire de même pour l'indice **CAC 40 prix (FR0003500008)**, qui sert de référence. Une référence venant d'un autre fournisseur (Euronext, Boursorama) serait un contrôle plus indépendant.

```powershell
.\.venv\Scripts\python.exe -B scripts/import_cac40.py --isin QS0011131826 --export PX1NR.csv --format investing --date-order mdy --decimal . --reference PX1.csv --reference-isin FR0003500008 --provider "Investing.com, export manuel du <date>" --license "Usage personnel de recherche" --update-catalog
```

Pour un export du site français : `--date-order dmy --decimal ,`. Ces conventions sont déclarées, jamais devinées ; un mauvais ordre échoue au contrôle des séances.

**Piste 2 — ETF distribuant FR0007052782, proxy (moins préférable).** Il faut trois fichiers :
- les **cours de clôture non ajustés** de l'ETF sur la même fenêtre (Investing.com « Lyxor CAC 40 » / Amundi CAC 40 UCITS ETF Dist, en vérifiant l'ISIN sur la page) ;
- **deux registres de distributions indépendants**, au format `ex_date,amount_eur` en `AAAA-MM-JJ`, limités à 2014–2023. L'un vient de l'émetteur (rapports annuels ou avis de distribution Lyxor/Amundi), l'autre de Parqet ou d'une source équivalente ;
- l'indice prix FR0003500008.

Avec `--isin FR0007052782 --distributions emetteur.csv --distributions-check parqet.csv`, l'import :
- exige des ex-dates et montants identiques entre les deux registres (± 0,005 €) ;
- vérifie, contre l'indice prix, que l'ETF baisse bien du rendement distribué à chaque ex-date. Cela prouve que les cours ne sont pas déjà ajustés et que les distributions ne sont pas comptées deux fois ;
- refuse tout saut inexpliqué (division d'actions, mauvaise série) et exige un écart annualisé « rendement total − prix » dans [0,3 %, 5 %].

Ces tolérances `CAC40_ETF` ont été fixées le 18/10/2026, avant toute observation de l'ETF. La série reste étiquetée **proxy ETF**, frais incorporés, et non indice officiel.

### Piste Yahoo Finance `PX1NR.PA` et EODHD (18/10/2026)

**Précautions.**
- Les tolérances de comparaison `CAC40_A5` ont été figées avant tout appel : écart de niveau maximal ≤ 1 pb et médian ≤ 0,1 pb, corrélation quotidienne ≥ 0,9999, au moins 99 % des séances en commun.
- L'adaptateur `yahoo_bounded.py` fixe à l'avance le fuseau horaire, ce qui supprime la requête `range=1d` que yfinance émet sinon pour connaître le fuseau et qui renvoie le dernier cours.
- Il n'autorise que des requêtes « chart » avec `period2` ≤ 30/12/2023 00:00 (heure de Paris, borne exclue) et la poignée de main cookie/crumb.
- Il retire du bloc `meta` les champs de cotation courante (`regularMarketPrice`, `regularMarketTime`, plus haut et plus bas sur 52 semaines, clôture précédente…) avant que yfinance ne lise la réponse.

**Résultat (yfinance 0.2.66) :** `YFPricesMissingError: $PX1NR.PA: possibly delisted; no price data found (1d 2014-10-01 -> 2023-12-30)`.
- La réponse brute était HTTP 200, sans erreur. Elle confirmait l'identité : `CAC 40 NR`, type INDEX, EUR, place PAR, fuseau Europe/Paris.
- Elle contenait **0 horodatage**, avant tout filtrage.
- Une seconde sonde bornée sur 01/07/2023 → 29/12/2023 a donné le même résultat.

Yahoo ne fournit donc aucune observation de cet indice dans la fenêtre autorisée. Je n'ai pas cherché jusqu'où remonte son historique, car cela exigerait des requêtes postérieures à la coupure.

**EODHD, sans abonnement :**
- la clé publique `demo` est refusée (HTTP 403), aussi bien pour la liste des symboles de la place `INDX` que pour une requête historique bornée sur `PX1NR.INDX` ;
- la page publique des indices pris en charge ne mentionne ni « PX1 » ni « CAC 40 NR », sans que cela prouve leur absence (la liste peut être chargée dynamiquement) ;
- vérifier la couverture exige une clé personnelle, donc un compte, que je ne peux pas créer.

**Référence Bourse Direct fournie** (`historic_PX1NR_XPAR_EUR.csv`, format `Date;Open;High;Low;Close;Volume;Currency`). La seule lecture de l'en-tête et du champ date révèle qu'elle couvre le **04/08/2008 → 15/10/2026**, donc la période TEST verrouillée. Aucune valeur n'a été lue.
- Le lecteur `parse_bourse_direct_export` refuse un tel fichier en entier, comme le garde-fou existant. Il ne le tronque pas : tronquer un jeu non borné après coup est exclu par le protocole.
- Pour l'utiliser, il faut soit un nouvel export limité au 01/10/2014 → 29/12/2023, soit une autorisation explicite du propriétaire pour une lecture « date d'abord ». Dans ce cas, les lignes postérieures seraient écartées sans lecture de leurs valeurs, et seul leur nombre serait consigné.
- L'import accepte ce format : `--format bourse-direct --isin QS0011131826`.

### Export Bourse Direct borné et référence `^FCHI` (18/10/2026, lecture « date d'abord » autorisée par le propriétaire)

**Bornage.**
- `scripts/bound_bourse_direct.py` lit l'original en lecture seule (SHA-256 `7a8337b1…`, inchangé après lecture). Pour chaque ligne, seul le texte avant le premier `;` (la date) est lu.
- Résultat : 2 367 lignes dans la fenêtre, recopiées telles quelles ; 718 lignes postérieures au 29/12/2023 écartées **sans découpage ni conversion** ; 1 577 lignes antérieures au 01/10/2014.
- La copie bornée est `data/v2_1/raw/cac40/PX1NR_bourse_direct_2014-10-01_2023-12-29.csv` (SHA-256 `6e872585…`), accompagnée de `PX1NR_bourse_direct_BOUNDING.json`.
- Les heures 01:00 et 02:00 correspondent au minuit UTC affiché à l'heure de Paris (hiver/été) : la date est bien celle de la séance.

**Identité.**
- L'export porte la devise EUR sur chaque ligne et le nom de fichier `PX1NR_XPAR`. L'ISIN QS0011131826 est déclaré (le fichier n'en contient pas).
- Les niveaux sont ceux de l'indice NR, qui réinvestit déjà les dividendes nets : aucun dividende n'est ajouté.
- L'écart annualisé NR − prix vaut **+2,31 %/an**, dans la limite prédéclarée [0,5 % ; 5 %].

**Référence prix.**
- `^FCHI` est obtenu par l'adaptateur Yahoo borné : une seule requête du 01/10/2014 au 30/12/2023 00:00 (heure de Paris, borne exclue), HTTP 200, 2 368 lignes.
- 17 champs de cotation courante ont été retirés avant lecture.
- Le fichier est `data/v2_1/raw/yahoo/FCHI_2014-10-01_2023-12-29.csv`. Yahoo ne fournit pas `PX1NR.PA` sur la fenêtre (voir plus haut).

**Écarts de calendrier, examinés un par un :**

| Date | NR | `^FCHI` | CW8 | Research | Décision |
|---|---|---|---|---|---|
| 31/12/2014 (séance) / 01/01/2015 (férié) | ligne datée du 01/01 | 31/12 présent | 31/12 | 31/12 | **Réétiquetage déclaré** 01/01/2015 → 31/12/2014. Le rendement de la ligne égale celui de `^FCHI` le 31/12 et le lendemain (écart 0,008 pb). |
| 31/12/2015 | absent | absent | absent | absent | **Hors calendrier de valorisation** (`EURONEXT_NO_DATA_DAYS`) : aucune donnée parisienne chez les sources examinées. L'ancienne exception CW8 est supprimée et aucun rendement n'est perdu. |
| 27/07/2016 | absent | présent (volume normal) | présent | présent | **Marque reportée** du 26/07, déclarée. Sur 26/07 → 28/07, NR et `^FCHI` font tous deux +0,587 %. |
| 25/12/2019 | absent | absent | ligne fictive | présent | Férié confirmé. La ligne CW8 est retirée. |

L'écart de 2 367 lignes contre 2 369 dates Research ne correspond donc pas à « deux séances manquantes ». Il se compose d'une ligne mal datée, d'une séance absente chez Bourse Direct, d'un jour sans aucune donnée et d'un férié présent dans Research. Le calendrier de valorisation compte **2 368 séances**, toutes présentes dans le calendrier Research.

**Contrôle non conforme.** Le NR ne peut pas faire moins bien que l'indice prix sur une séance (tolérance prédéclarée de 1 pb). Les comparaisons sont faites sur les dates réellement observées de l'export. Deux séances échouent :

| Séance | NR | `^FCHI` | Écart | Écart le lendemain |
|---|---|---|---|---|
| 27/06/2016 | −2,97 % | −1,86 % | −111 pb | +116 pb |
| 19/10/2020 | −0,13 % | +0,14 % | −27 pb | +27 pb |

Toutes les autres séances respectent la relation (87,6 % sont à 1 pb près). L'inversion exacte le lendemain désigne une valeur erronée **un seul jour** dans l'une des deux sources, sans pouvoir dire laquelle sans troisième référence. Le statut reste **BLOQUÉ** : aucune tolérance n'a été modifiée, aucune valeur corrigée. Aucune de ces deux séances n'est un début de mois.

**Action minimale pour lever le blocage.** Fournir une troisième référence pour ces deux dates : l'indice prix CAC 40 (FR0003500008) ou le CAC 40 GR exporté depuis Bourse Direct (borné, ou avec la même autorisation de lecture « date d'abord »), ou les clôtures officielles Euronext de ces deux séances. Une règle de décision doit être fixée **avant** de lire cette référence, par exemple : la source contredite par les deux autres au-delà de 1 pb est écartée pour ces seules dates.

### Corrections officielles et admission du CAC 40 NR (18/10/2026)

**Vérifications sur les jeux bornés.**
- **27/06/2016.** La clôture officielle de 3 984,72, rapportée à la clôture Yahoo du 24/06 (4 106,73, conforme), donne −2,971 %. C'est exactement le rendement du NR Bourse Direct (−2,9709 %). En partant de 3 984,72, le 28/06 donne +2,6132 % contre +2,6131 % pour le NR. La barre Yahoo du jour est incohérente : son plus bas (4 012,20) est supérieur à la clôture officielle.
- **19/10/2020.** Yahoo `^FCHI` affiche la clôture corrigée (4 942,62). Le NR Bourse Direct garde, lui, une valeur non corrigée. Sur 16/10 → 20/10, l'écart NR − prix est de −0,002 pb, et inférieur à 0,03 pb chaque autre jour d'octobre 2020 : aucun effet de dividende.

**Sources.**
- Page Euronext (HTTP 200, extraits filtrés) : elle confirme « CAC40: 4,942.62 » et l'annulation des transactions postérieures à 17 h 30. Elle renvoie au **tableur officiel des clôtures ajustées** (`live.euronext.com/media/516/download`), archivé dans `data/v2_1/raw/euronext/` (SHA-256 `e42ebf4f…`) et lu sans dépendance supplémentaire.
- Ce tableur donne **QS0011131826 PX1NR 10 521,77**, FR0003500008 PX1 4 942,62 et PX1GR 13 721,79. **Le niveau NR corrigé est donc observé, pas reconstruit.** Une reconstruction par le rendement de l'indice prix, sans dividende, aurait donné 10 521,78 (0,01 point d'écart). Elle n'est utilisée que comme corroboration.
- Dépêche AFP (medias24.com) : HTTP 403, non consultée et non contournée. Le niveau 3 984,72 fourni par le propriétaire est corroboré numériquement par le NR, à 0,01 pb sur deux séances.

**Corrections déclarées** (`OFFICIAL_CORRECTIONS`, appliquées au moment de la validation ; fichiers bruts inchangés ; chaque correction exige la valeur brute attendue) :

| Série | Date | Brut | Corrigé | Nature |
|---|---|---|---|---|
| `^FCHI` (référence) | 27/06/2016 | 4 030,30 | 3 984,72 | Clôture officielle rapportée (AFP) |
| CAC 40 NR (export) | 19/10/2020 | 10 493,36 | 10 521,77 | Clôture officielle observée (Euronext) |

**Contrôles relancés.**
- Données brutes : le contrôle d'origine « NR jamais sous le prix de plus de 1 pb » **échoue toujours (111 pb)**. Ce résultat est publié dans `raw_checks_before_corrections`.
- Données corrigées : **pire écart 0,026 pb**, toutes séances confondues. Les séances voisines des deux dates restent sous 0,05 pb, et l'écart NR − prix vaut +2,31 %/an.
- Les tests de régression couvrent les deux dates et leurs voisines, l'échec brut comme la conformité corrigée.

**CW8, même fichier officiel** : LU1681043599 à 310,30, contre 310,235 chez Yahoo, soit −2,1 pb. C'est dans les tolérances déjà validées pour WORLD, et sans effet mesurable (environ 0,3 pb de portefeuille un seul jour). Aucune correction n'est appliquée ; le constat est seulement consigné.

**Statut : VALIDÉ.** Niveau `levels/CAC40.csv` SHA-256 `8405f581…`, calendrier commun `e9e1ae66…`.

## 8. Provenance et empreintes

- **Sources Research** (lecture seule, `ResearchGuard`) : empreintes et coupure vérifiées avant lecture des valeurs, liste `PINNED_RESEARCH_SOURCES`. IAU est épinglé par le manifeste `research_gold`, ^SP500TR par le manifeste DV2. Aucune entrée n'est ajoutée à la liste d'autorisation de `lab.yaml`.
- **Sources externes**, récupérées le 18/10/2026 dans `data/v2_1/raw/` avec un manifeste SHA-256. Chaque réponse est analysée en mémoire avant écriture et toutes se terminent au 29/12/2023 :
  - BCE EXR.D.USD.EUR.SP00.A : réutilisation libre avec mention ;
  - MSCI 990100 NETR USD/EUR et 891800 NETR USD : usage de recherche local, sans redistribution ;
  - Bitstamp OHLC, 8 pages : usage local.
- **Données admises** : `levels/WORLD.csv` `da841adf02ed4371e688e1d92de777a4b24335693828c1fd72195e300f139c28` et `calendar/euronext_paris_sessions.csv` `ce3d94435f4431fd4226789b224811b122277ff9b1ec82bdce293813382af9e8`, épinglées dans le catalogue et rechargées par `load_validated_panel`.
- **Incident de méthode :** la première version du scanner ne reconnaissait pas le format `AAAAMMJJ`, puis elle a lu une décimale comme un horodatage. Il a été corrigé avant toute lecture de valeurs et la réponse rejetée a été supprimée. Aucune donnée postérieure à la coupure n'a été lue ni enregistrée.

## 9. Reproduire

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
.\.venv\Scripts\python.exe -B scripts/fetch_reference_data.py      # conserve les fichiers existants
.\.venv\Scripts\python.exe -B scripts/prepare_custom_data.py       # contrôles, niveaux admis, rapport JSON
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider
```

Le rapport détaillé est `outputs/v2_1/data_admission.json`. Le catalogue n'est jamais écrit automatiquement, sauf par `import_cac40.py --update-catalog` lorsque tous les contrôles sont conformes.

## 10. Amendements A1–A4 (approuvés le 18/10/2026)

Les tolérances d'origine (`TOLERANCES`) sont inchangées et figées par test. Leurs échecs restent calculés et publiés dans `outputs/v2_1/data_admission.json`, sous `fx_original_thresholds` et `superseded_checks`. Les amendements se trouvent dans `AMENDMENTS` (code), eux aussi figés par test.

### 10.1 A1 — change BCE (seuils choisis **après** observation des données)

Le 99e centile ≤ 80 pb (mesuré 102 pb) est remplacé par des critères qui distinguent une **erreur de niveau** d'une **information arrivée entre 14 h 15 et 17 h**. Mesures sur 2 369 séances :

| Critère | Limite | Mesuré |
|---|---|---|
| Médiane absolue (critère d'origine conservé) | ≤ 15 pb | 14,75 pb |
| Maximum (critère d'origine conservé) | ≤ 300 pb | 267 pb |
| Pente « écart → mouvement du fixing suivant » | [0,7 ; 1,3] | 1,014 |
| Corrélation correspondante | ≥ 0,3 | 0,597 |
| Autocorrélation à 1 jour, en valeur absolue | ≤ 0,2 | 0,038 |
| Écart au début / à la fin | ≤ 10 pb | 5,5 / 2,7 pb |
| Écart moyen signé, en valeur absolue | ≤ 3 pb | 0,5 pb |

Effet du choix BCE plutôt que WM/R de 17 h sur SPY en EUR : +0,34 pb/an de CAGR, +0,09 point de volatilité quotidienne, drawdown maximal plus profond de 0,37 point. Il s'agit d'un bruit absorbé le lendemain, sans biais de rendement.

### 10.2 A2 — SPY (seuils choisis **après** observation des données)

Le rendement total explicite est inchangé. On garde l'écart annualisé dans [−0,30 % ; 0] (mesuré −0,087 %) et l'écart aux dates ex-dividende ≤ 25 pb (16,2 pb). On ajoute, sur l'écart de niveau une fois retirée une dérive linéaire ajustée (−8,0 pb/an pour 9,45 pb de frais) :

| Critère | Limite | Mesuré |
|---|---|---|
| Médiane absolue | ≤ 5 pb | 3,05 pb |
| Moyenne glissante sur 21 séances, maximum en valeur absolue | ≤ 20 pb | 12,98 pb |
| Plus longue série de séances au-delà de 25 pb | ≤ 3 séances | 2 (9 séances au total) |

La corrélation quotidienne (0,99869), le 99e centile (21,0 pb) et l'autocorrélation (−0,57) deviennent des **diagnostics non bloquants**. Limite connue : la borne de 3 séances a été fixée en connaissant la valeur mesurée (2).

### 10.3 A3 — Bitcoin, composite Bitstamp (tolérances fixées **avant** de récupérer Coinbase et Bitfinex)

**Construction.**
- Jusqu'au raccord : Bitstamp BTC/USD divisé par le dernier fixing BCE publié avant la clôture UTC. Le fixing est publié vers 16 h à Francfort, ce qui est causal ; l'âge maximal est de 5 jours.
- Ensuite : Bitstamp BTC/EUR natif.
- **Règle de raccord** : premier jour du premier mois civil complet où chaque bougie EUR dépasse 10 BTC, soit le **01/05/2016** (le carnet EUR présente 6 jours sans volume en avril 2016).
- Une bougie de moins de 1 BTC n'est pas un prix : elle est retirée, jamais remplie. Cela concerne les 06–08/01/2015, sans volume pendant la suspension de Bitstamp après son piratage. Les instantanés des 07–09/01/2015 gardent donc la clôture du 05/01 (âge 2 à 4 jours), au titre d'une exception déclarée et testée.
- Les autres instantanés utilisent la clôture du jour UTC précédent (âge 1). Aucune bougie retenue n'a moins de 10 BTC ; le minimum est de 63,9 BTC.

**Contrôles** (23 sur 26 conformes) :

| Comparaison | Recouvrement | Médiane | 99e centile | Moy. mensuelle max | Corr. | Écart de CAGR |
|---|---|---|---|---|---|---|
| Bitstamp USD vs Bitfinex USD | 30/09/2014 → 30/04/2016 | 25,9 pb | 161 pb | 106 pb | 0,980 | 0,45 % |
| Bitstamp USD vs Coinbase USD | 20/07/2015 → 30/04/2016 | 24,3 pb | 125 pb | 45 pb | 0,991 | **2,08 % > 0,5 %** |
| Bitstamp EUR vs Coinbase EUR | 01/05/2016 → 29/12/2023 | 7,6 pb | **325 pb > 300** | **394 pb > 200** (déc. 2017) | 0,991 | 0,11 % |

Le raccord est conforme : écart médian EUR natif / USD÷BCE de 36 pb sur ±30 jours, saut propre au changement de carnet de 36 pb. Dans chaque comparaison, le même jour UTC est mieux corrélé que J±1. Les limites étaient : médiane ≤ 50 pb, 99e centile ≤ 300 pb, maximum ≤ 1 500 pb, moyenne mensuelle ≤ 200 pb, corrélation ≥ 0,95, écart de CAGR ≤ 0,5 %.

**Analyse menée après le contrôle**, qui ne sert pas de critère :
- **Décembre 2017.** Mesurés contre Bitstamp USD÷BCE, les écarts moyens sont : Bitstamp EUR −65 pb, Bitfinex −63 pb, Coinbase USD +177 pb, Coinbase EUR +346 pb. C'est la **référence Coinbase** qui portait une prime pendant l'euphorie, pas Bitstamp. Sur 2018–2023, Bitstamp et Coinbase EUR ne dépassent 300 pb que 3 jours.
- **Écart de CAGR contre Coinbase USD.** Le recouvrement n'est que de 286 jours. L'écart passe de −37 pb au début à −124 pb le dernier jour : 87 pb deviennent 2,1 % annualisés. Le critère « écart de CAGR » est inadapté aux recouvrements courts.

**Statut A3 : BLOQUÉ**, résultat conservé. La suite figure en 10.5 (option b retenue). Les deux options proposées étaient :
- (a) un amendement A3-bis, à formuler avant tout nouveau calcul. Par exemple : arbitrage par la majorité de deux références indépendantes lorsque la source principale en contredit une seule ; écart de niveau annualisé exigé seulement sur des recouvrements d'au moins 2 ans ;
- (b) l'ajout d'une seconde référence EUR (par exemple Bitfinex BTC/EUR, API bornée), avec les mêmes tolérances A3 déclarées avant sa récupération et une règle de décision fixée d'avance.

### 10.4 A4 — ETF CAC 40 FR0007052782 (fixé avant toute observation de l'ETF)

S'ajoutent aux contrôles déjà en place (registres concordants, résidu aux ex-dates, cours non ajustés, saut ≤ 300 pb, écart rendement total − prix), et sont tous exigés pour une validation :
- **Ancrages VL de l'émetteur** (rapports annuels et semestriels) : au moins 2 par an sur 2015–2023, avec |clôture / VL − 1| ≤ 1 %. Un historique ajusté serait environ 20 % plus bas en 2014.
- **Exhaustivité** : nombre exact de distributions par an selon la politique du prospectus (`--distributions-per-year`).
- **Baisse inexpliquée** : tout écart inférieur à −75 pb face à l'indice, hors ex-date et hors opération déclarée, fait échouer la validation. C'est ainsi qu'est détectée une distribution absente des deux registres.
- **Puissance par événement** : résidu ≤ min(100 pb ; ½ rendement distribué), et la baisse doit être plus proche de l'hypothèse « non ajusté » que de l'hypothèse « ajusté ».
- **Opérations sur titres** : la liste (`date,ratio,description`) est obligatoire, une table vide déclarant explicitement l'absence d'opération. Tout ratio différent de 1 est refusé (ajustement explicite requis). Sur chaque date déclarée, l'écart face à l'indice doit rester ≤ 100 pb. C'est le cas à vérifier pour la fusion Lyxor → Amundi.

L'indice officiel CAC 40 Net Return reste la source préférée : la voie ETF n'est à utiliser que s'il est impossible de l'obtenir.

### 10.5 A3b — consensus par plateforme et Bitfinex BTC/EUR (option b, approuvée le 18/10/2026)

**Ordre des opérations.** Les critères `BTC_A3B` ont été formulés après avoir vu les échecs A3 contre Coinbase, puis figés dans le code **avant** le téléchargement de Bitfinex BTC/EUR (borné du 01/11/2017 au 29/12/2023). Les 21 contrôles A3 par paire, dont les 3 échecs, restent publiés dans `superseded_checks`.

**Une série par plateforme.**
- Pour chaque plateforme et chaque jour UTC, on retient une seule série EUR : la paire EUR native si elle est liquide (≥ 1 BTC), sinon la paire USD divisée par le fixing BCE causal. Deux paires d'une même plateforme ne comptent donc jamais comme deux témoins.
- Les deux carnets de Bitstamp ne se corroborent pas l'un l'autre : leur raccord est un contrôle interne, marqué « non indépendant ».
- Jours d'utilisation : Bitfinex 2 249 jours EUR et 1 151 jours USD/BCE ; Coinbase 3 167 jours EUR et 1 jour USD/BCE.

**Consensus.**
- Les jours où trois plateformes cotent (3 161 jours), Bitstamp est comparé à la médiane journalière des trois. Les autres jours (214), il est comparé à l'autre plateforme seule. Les seuils A3 (médiane, 99e centile, maximum, moyenne mensuelle, corrélation, même jour UTC) sont inchangés.
- **Biais connu** : la médiane inclut Bitstamp. Les jours où il se situe entre les deux autres (42,6 %), son écart vaut zéro par construction. Le diagnostic sans ce biais confirme le résultat : la distance à la plateforme la plus proche a un 99e centile de 184 pb, une moyenne mensuelle maximale de 156 pb, et aucun mois ne dépasse 200 pb.

**Critère de dérive tenant compte de la durée.** Il remplace l'écart de CAGR annualisé, qui reste publié :
- formule : |moyenne des 20 dernières observations − moyenne des 20 premières| ≤ 50 pb/an × durée + 3 erreurs-types ;
- l'erreur-type est calculée à partir de la taille d'échantillon effective AR(1), elle-même mesurée sur les **résidus autour d'une tendance linéaire** ;
- **correction après gel** : la version figée estimait le bruit sur l'écart brut, si bien qu'une vraie dérive gonflait sa propre tolérance. Un test adversarial (300 pb/an acceptés) l'a révélé. La correction ne fait que durcir le critère, et la décision BTC est la même avec les deux versions ;
- sur le recouvrement court qui avait échoué (Bitstamp USD contre Coinbase USD, 286 jours) : dérive de 27,5 pb pour une limite de 89,5 pb. L'ancien critère comparait deux jours isolés et donnait 2,08 %/an.

**Résultats (16/16 conformes) :**

| Contrôle | Mesuré | Limite |
|---|---|---|
| Consensus : médiane / 99e centile / maximum | 1,6 / 154 / 582 pb | 50 / 300 / 1 500 pb |
| Consensus : moyenne mensuelle maximale | 106 pb (09/2014, deux plateformes) | 200 pb |
| Consensus : dérive sur 9,25 ans | 32 pb | ≤ 524 pb |
| Bitstamp vs Bitfinex : corrélation ; dérive | 0,984 ; 34 pb | ≥ 0,95 ; ≤ 758 pb |
| Bitstamp vs Coinbase : corrélation ; dérive | 0,986 ; 38 pb | ≥ 0,95 ; ≤ 562 pb |
| Même jour UTC mieux corrélé que J±1 | oui, pour les deux plateformes | — |
| Raccord interne, liquidité (min 63,9 BTC), causalité | conformes | — |

**Décembre 2017, paires EUR natives (31 jours) :**
- écart moyen Bitstamp EUR / Bitfinex EUR : **+6,5 pb** (médiane +12,9 pb) ;
- écart moyen Coinbase EUR / Bitfinex EUR : **+422,5 pb** ;
- écart moyen Coinbase EUR / Bitstamp EUR : **+394 pb** ;
- Coinbase a la cotation la plus élevée **30 jours sur 31**.

C'est une prime propre à Coinbase, confirmée par une plateforme EUR indépendante.

**Mois où une plateforme s'écarte des deux autres de plus de 200 pb** (diagnostic) :
- Coinbase en 12/2017 ;
- Bitfinex en 04/2017 (paire USD/BCE) puis de 11/2018 à 03/2019.

**Bitstamp n'est jamais la plateforme isolée.** Le composite Bitstamp d'origine est donc conservé sans modification. Empreinte du niveau : `levels/BTC.csv` `d3cadc96918713759713fb0a57caf25c1106fdec7df43e4a5e80e39e79f77665`.

**Date de lancement de Bitfinex BTC/EUR.** L'API renvoie des bougies liquides dès le **01/11/2017**, premier jour demandé (par exemple 128,5 BTC ce jour-là), et non à partir du 22/11/2017. La date réelle d'ouverture n'est pas vérifiée au-delà de ces données. Cela n'affecte pas l'analyse de décembre 2017.

**Suspension de Bitstamp, janvier 2015.** Bitstamp a suspendu ses échanges après son piratage du 04/01/2015 : les bougies du 06 au 08/01/2015 n'ont aucun volume. Les instantanés des 07, 08 et 09/01/2015 reprennent la clôture du 05/01/2015 (âge 2 à 4 jours). Ce sont des **marques de valorisation reportées, pas des cotations exécutables** : aucun ordre n'aurait pu être exécuté à ces prix sur Bitstamp. Ces séances ne sont pas des débuts de mois, donc aucun rééquilibrage mensuel ne les utilise. Les rendements de ces jours sont nuls par construction, et le mouvement de marché de la période apparaît en bloc le 12/01/2015.

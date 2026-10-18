# Portfolio Lab V2.1 — Audit préalable et arrêt sur les données

Date : 18 octobre 2026. **Statut : implémentation suspendue avant développement, faute de série CAC 40 à rendement total validée sur toute la fenêtre demandée.** Aucun résultat de portefeuille personnalisé n'a été produit.

**Suite autorisée après cet audit :** le logiciel V2.1 a été développé et testé sur données synthétiques indépendamment de ce blocage. Seul le backtest historique complet reste suspendu. Voir `V2_1_GUIDE.md` pour l'état actuel ; le présent document conserve les constats de l'audit initial.

## Base de travail et périmètre

- Dépôt de travail : `Trading/portfolio-optimization-v2-clean`, branche `feature/custom-portfolios-v2-1`, créée depuis `1f65eaa29374055eaac4af614f93c6e8f16161f1`.
- Ancien dépôt V1/V2 : `Trading/portfolio-optimization`, consulté uniquement pour son code, sa configuration et les manifestes de caches ; aucun notebook ou résultat historique incertain n'a été ouvert.
- Research : `Trading/Draft/nasdaq_dynamic_exposure_v0`, strictement en lecture seule.
- Aucune fusion de l'historique V1, aucun commit et aucun push. Les branches précédentes sont conservées.

La cible approuvée est « Mon portefeuille diversifié » : émergents 30 %, S&P 500 30 %, MSCI World 15 %, CAC 40 10 %, or 10 %, Bitcoin 5 %. Le protocole impose 100 000 € initiaux, des rendements EUR, sans levier ni flux externes, du 2014-10-01 au 2023-12-29, avec rééquilibrage mensuel et sensibilités annuelle/achat-conservation. Ces poids n'ont pas été ajustés.

## Méthode de contrôle des données

L'inventaire a porté sur les noms de fichiers, les définitions de séries, les constructeurs de données, les registres d'empreintes et les métadonnées parquet. Aucun constructeur ou simulateur Research n'a été importé ou exécuté. Aucun téléchargement n'a été lancé.

Les métadonnées de dates sont vérifiées avant lecture d'observations. Le panel DV1 a ensuite été vérifié par `ResearchGuard` avec son empreinte indépendante enregistrée dans `research_diversification_v2/FREEZE_DV2_PROTOCOL.json`, puis seules les cinq colonnes utiles et la fenêtre autorisée ont été chargées. L'intégrité a été revérifiée après lecture. Les valeurs de prix et les performances ne sont pas reproduites ici.

Les sources connues comme interdites (`data/yahoo_daily_v0_amended.parquet`, `data/irx_daily.parquet`, `ops/`, `reports/` et les archives de sorties) n'ont pas été ouvertes. Les caches de quarantaine ne sont pas une source autorisée pour cette étude.

## Inventaire des six actifs

Le fichier `research_diversification_v1/outputs/research_panel_eur.parquet` contient notamment `WORLD`, `EM`, `SP500`, `GOLD` et `BTC`. Son schéma et ses statistiques parquet établissent une borne maximale au 2023-12-29. Pour chacune de ces cinq colonnes, le contrôle restreint à la fenêtre demandée donne **2 328 observations valides, du 2014-10-01 au 2023-12-29, aucune valeur manquante ou non positive**. Cela valide la couverture sur le calendrier du panel, pas encore la causalité d'une exécution commune aux six actifs.

| Actif | Source locale et convention | Couverture constatée et réserve |
|---|---|---|
| Émergents | DV1 `EM` : EEM, ETF MSCI EM en USD, rendement total reconstruit à partir de clôtures ajustées des splits et distributions, converti en EUR. Le raccord historique VEIEX est antérieur à la fenêtre demandée. | Fenêtre complète dans le panel. **Proxy ETF, pas l'indice MSCI EM NETR officiel.** Les frais du fonds sont incorporés à sa performance. AEEM.PA constitue aussi une piste historique EUR ; PAEEM.PA commence en 2019 et ne suffit pas seul. |
| S&P 500 | DV1 `SP500` : SPY, clôture et distributions en USD, converties en EUR. Autre candidat : `research_diversification_v2/data/raw/YF_SP500TR.parquet`, indice Yahoo `^SP500TR`, en USD, dividendes bruts réinvestis. | Panel SPY complet. Le parquet de l'indice couvre, selon ses métadonnées, 1997-01-02 → 2023-12-29, 6 794 lignes ; son empreinte correspond au manifeste DV2. Ses prix n'ont pas été chargés ; sa qualité et sa conversion restent à valider avant intégration. |
| MSCI World | DV1 `WORLD` : CW8.PA, ETF UCITS capitalisant coté en EUR, exposition World non couverte en change, clôtures nettoyées par Research. | Fenêtre complète dans le panel ; données brutes dès 2009-06-16. **Proxy ETF et frais incorporés, pas niveaux de l'indice NETR officiel.** |
| CAC 40 | Catalogue V1 : `PX1GR.PA`, CAC 40 Gross Return en EUR, dividendes bruts réinvestis, classé `data_issue` pour observations manquantes. | **Aucune série locale complète, vérifiée et autorisée identifiée.** Aucun manifeste de cache courant pour ce symbole, aucune colonne CAC dans le panel DV1, aucune source CAC correspondante trouvée dans les catalogues, constructeurs ou fichiers de données Research inspectés. |
| Or | DV1 `GOLD` : GLD converti en EUR ; le raccord COMEX antérieur au lancement de GLD ne concerne pas 2014–2023. Research utilise aussi GLD sur son calendrier Paris avec décalage des prix US et du change. | Fenêtre complète dans le panel. Proxy de l'ETC investissable ; frais GLD incorporés. Les séries « même date US » et « dernier cours connu à Paris » ne doivent pas être mélangées. |
| Bitcoin | Source Research `research_v7_global/data/BTC_EUR.parquet` : BTC-EUR Yahoo/CoinMarketCap, quotidien, convention annoncée 00:00 UTC, historique dès 2014-09-17 ; reprise dans DV1 `BTC`. | Fenêtre complète dans le panel, déjà en EUR. Le calendrier crypto 7 j/7 est ramené aux séances du panel. L'heure de disponibilité de la clôture doit être explicite pour les ordres et la valorisation. |

### Caches de l'optimiseur V1

Les manifestes courants identifiés donnent :

- MSCI World `990100`, variante `NETR`, date finale demandée 2019-12-31 ;
- MSCI Emerging Markets `891800`, variantes `NETR` et `GRTR`, date finale demandée 2019-12-31 ;
- `^SP500TR` et `GC=F`, requêtes Yahoo avec fin exclusive 2020-01-01 ;
- EURUSD `DEXUSEU`, requête FRED jusqu'au 2019-12-31.

Ces caches ne fournissent donc pas, à eux seuls, les années 2020–2023. Aucun de leurs prix n'a été ouvert pour tenter de contourner cette limite. Le script temporaire V1 d'audit CAC contient des requêtes allant jusqu'en 2026 : il a été lu comme code, **jamais exécuté**, et ses sorties n'ont pas été consultées.

L'absence d'une série complète CAC ne permet ni de remplacer silencieusement le CAC par un indice de prix, ni de reporter son poids sur un autre actif, ni de compléter les trous avec des informations futures. Les proxies EEM/CW8 ne doivent pas être présentés comme les indices NETR officiels ; leur acceptabilité économique devra être explicite si ces alternatives sont retenues.

## Provenance et empreintes contrôlées

| Fichier candidat | Empreinte SHA-256 attendue et vérifiée |
|---|---|
| `research_diversification_v1/outputs/research_panel_eur.parquet` | `35e80e58c779adb834e910c4fa7d8befd6bcd5c657964cb0d201f17255fe4656` |
| `research_diversification_v2/data/raw/YF_SP500TR.parquet` | `68e53d04e61f8464aece0595bb685e4b65a289ad74352a1ec3636e770a7266bc` |

Le premier est contrôlé contre le snapshot DV1 gelé dans DV2 ; le second contre `research_diversification_v2/data/raw/manifest.json`. Les empreintes existantes de `config/v2/lab.yaml` n'ont pas été modifiées. Aucun nouvel artefact n'a été ajouté à la liste d'autorisation de production.

## Calendriers, change et rendement total

- Le panel DV1 est sur le calendrier US/QQQ : 2 328 séances dans la fenêtre. Les courbes V2 gelées sont sur le calendrier Paris : 2 369 séances. Une comparaison quotidienne nécessite une convention commune et une nouvelle vérification des métriques ; une simple concaténation serait incorrecte.
- `v11data.research_set_long()` et les séries de recherche DV1 emploient des conversions USD/EUR de même date pour certains actifs. `v10data.lagged_usd_to_eur()` emploie, pour le simulateur Paris, la clôture US précédente et le fixing EURUSD précédent. Ce second mécanisme est causal à la clôture européenne ; utiliser la clôture US du soir pour une exécution européenne antérieure ne le serait pas.
- EURUSD est coté USD par EUR : division du niveau USD par le taux. Le module V1 `currency.to_eur` confirme le sens de conversion et refuse les taux invalides ; il ne résout pas à lui seul l'alignement horaire.
- Les reconstructions américaines ajoutent les distributions aux clôtures ajustées des splits. Il ne faut pas y rajouter les dividendes à une série déjà en rendement total ni déduire deux fois les frais incorporés.
- Les remplissages par la dernière valeur connue doivent rester rétrospectifs, sans `bfill` ni inventer de prix avant lancement. Rééquilibrages mensuels/annuels : décisions et ordres à définir sur des informations disponibles avant l'exécution, avec prise en compte des fermetures de marchés.

## Composants réutilisables et limites

| Composant | Réemploi pertinent |
|---|---|
| V2 `guard.py`, `settings.py` | Autorisation, empreintes, chemins, coupure et validation stricte ; futur catalogue séparé de séries personnalisées, sans assouplir le contexte gelé existant. |
| V2 `metrics.py` | Rendements quotidiens, volatilité, Sharpe/Sortino, drawdown, récupération et années calendaires. Le CAGR calculé sur la trajectoire personnalisée doit rester **économique avant fiscalité de liquidation**. |
| V2 `formatting.py`, `charts.py`, `tables.py`, `ui.py` | Formatage français, thème, sélection commune et vues Plotly. L'adaptateur actuel suppose des références fiscales et 11 identités gelées : ne pas fabriquer ces champs pour un portefeuille personnalisé. |
| V1 `currency.py`, `returns.py`, `simulation.py` | Conventions de change et de détention utiles comme référence. **Pas de réemploi direct du chemin V1 sur 2020–2023** : son verrou à 2020 reste intact. |
| V1 `static_policy_returns` | Référence achat/dérive annuelle ; insuffisant pour le besoin : pas de rééquilibrage mensuel, pas de journal de cash explicite, coût approximatif au premier ordre et convention de fin d'année différente. Un petit moteur exact et autofinancé serait nécessaire. |
| Research `dv1data`, `v10data`, `v11data` | Définitions de données à suivre, sans importer automatiquement les chaînes de chargement ou dupliquer leur simulateur fiscal. |

Les règles de frais Bourse Direct et la comptabilité fiscale du moteur Research ne sont pas des coûts indiciels génériques. La V2.1 devra afficher les coûts proportionnels réellement modélisés ; les champs « CAGR net après liquidation » et « patrimoine net fiscal » du portefeuille personnalisé devront rester **Non calculé**. Les valeurs fiscales gelées de N07, D2_25 et des benchmarks restent inchangées. Une comparaison économique avec les trajectoires Research après frais et impôts intermédiaires devra signaler cette asymétrie ; aucun classement commun brut/net non étiqueté n'est acceptable.

## Condition précise de reprise

Obtenir ou identifier une série **CAC 40 GR ou NR en EUR**, avec niveaux positifs, dividendes explicitement traités, couverture du 2014-10-01 au 2023-12-29, calendrier et source/version documentés, et empreinte vérifiable. Elle doit être physiquement limitée à la période autorisée ou fournie sous une forme dont l'isolation sûre est garantie avant toute lecture de valeurs.

La série de prix `^FCHI` n'est pas un substitut acceptable à un CAC 40 à dividendes réinvestis. Les sorties historiques incertaines et les fichiers mixtes comprenant TEST ne seront pas exploités pour compléter la série manquante.

Si les indices MSCI officiels sont exigés plutôt que les proxies ETF disponibles, il manque également leurs historiques NETR autorisés pour 2020–2023. Aucune acquisition automatique n'a été entreprise : la consigne prévoit l'arrêt lorsque les jeux requis ne sont pas disponibles.

Une fois ces prérequis levés : catalogue gardé et spécification portable ; moteur à frais proportionnels/cash exact ; validation indépendante sur exemples synthétiques ; adaptateur de comparaison économique ; interface française légère ; robustesse prédéfinie et notebook 04. Ces travaux **ne sont pas commencés** dans cet audit.

## Validation et état de livraison

La suite existante `tests/test_v2.py` a été relancée sur cette base : **50 tests réussis, aucun échec, en 80,21 secondes**. Les 12 empreintes d'artefacts gelés correspondent à la validation précédente. Les modules, configurations gelées, garde-fous et notebooks sont inchangés ; le seul nouveau fichier de travail est ce rapport, non indexé. Aucun commit ni push n'a été effectué.

Aucun moteur V2.1, formulaire de création, fichier de portefeuille utilisateur ou backtest partiel n'est livré. Cet arrêt est la conséquence du prérequis de données explicitement demandé, et non une conclusion sur l'intérêt de l'allocation.

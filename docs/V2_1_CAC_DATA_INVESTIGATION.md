# V2.1 — Investigation ciblée de la source CAC 40

Date : 18 octobre 2026. Branche : `feature/custom-portfolios-v2-1`, base `1f65eaa29374055eaac4af614f93c6e8f16161f1`.

**Décision : rester arrêté avant implémentation et simulation. Aucune série CAC 40 quotidienne complète et utilisable n'a été validée dans cet environnement. Cela ne prouve pas que l'historique n'existe pas chez Euronext.**

**Mise à jour après nouvelle autorisation :** l'arrêt concerne désormais le backtest historique complet, pas le développement logiciel. Le moteur et le constructeur sont décrits dans `V2_1_GUIDE.md`. Deux nouvelles requêtes ETF courtes et bornées ont renvoyé la même enveloppe opaque, sans intégration de données.

Cette investigation complète `V2_1_PRELIMINARY_AUDIT.md`. L'autorisation nouvelle accepte explicitement les proxies ETF MSCI pour l'exploration, sous réserve d'étiquetage et de vérification indépendante ; leur caractère non officiel ne bloque donc plus à lui seul la V2.1. La disponibilité du CAC 40 à rendement total reste bloquante.

## Requêtes historiques effectuées

Le client public R [EN_HistData](https://raw.githubusercontent.com/cran/Euronext/master/R/EN_HistData.R) fournit la forme du POST vers `https://live.euronext.com/en/ajax/getHistoricalPricePopup/{ISIN}-XPAR`.

Chaque POST historique a explicitement envoyé les paramètres suivants, sans redirection automatique :

```text
adjusted=Y
startdate=2014-10-01
enddate=2023-12-29
nbSession=10
```

`nbSession=10` reprend la forme du client avec dates explicites : aucune interprétation en fenêtre complète n'est présumée sans contrôle des dates et du nombre de lignes retournées.

| Instrument demandé | Nombre de POST | Réponse constatée | Conclusion |
|---|---:|---|---|
| CAC 40 NR, QS0011131826 | 2 | HTTP 200, JSON avec clés `ct`, `iv`, `s`, environ 2,8 Ko | Objet opaque compatible avec une enveloppe chiffrée ; aucun tableau ni date exploitable identifié. |
| CAC 40 GR, QS0011131834 | 1 | Même structure | Même limite. |
| ETF CAC 40 distribuant, FR0007052782 | 1 | Même structure | Aucun historique ETF validé. |

Aucun de ces corps n'a été déchiffré, converti en prix, utilisé dans un calcul ou enregistré comme jeu de données. Le premier essai NR a recherché un tableau HTML directement ; le second a établi la structure JSON. Les champs de l'enveloppe ne permettent pas d'affirmer que les dates demandées sont honorées. HTTP 200 n'établit ni la couverture, ni les droits d'utilisation, ni la qualité des observations. Le client R contient une restriction aux deux dernières années : c'est une restriction du client, pas une preuve de la profondeur réellement disponible sur le serveur.

Les pages de cotation et historiques par défaut des instruments recherchés n'ont pas été ouvertes. Aucun accès à une session authentifiée, aucune tentative de contournement d'accès et aucun téléchargement Yahoo Chart n'ont été effectués. Ce dernier pourrait exposer des métadonnées de cours courants malgré des bornes historiques.

## Voie officielle documentée

La [spécification Euronext Web Services EOD, version 1.0 de mai 2016](https://connect2.euronext.com/sites/default/files/documentation/data/ews_api_-_historical_data_client_specification.pdf) décrit un service d'historiques quotidiens pour les indices. Il accepte notamment un ISIN, un MIC, une date de début et une date de fin. L'adresse de service, la clé et le jeton d'accès sont fournis au client par Euronext. Aucun accès client à ce service n'a été utilisé dans cette investigation. Cette documentation ancienne doit être confirmée par le fournisseur avant intégration.

La [présentation officielle des Web Services](https://www.euronext.com/en/data/how-access-market-data/web-services) décrit une offre personnalisable, notamment par période et usage. La voie la plus solide est donc un export ou accès client Euronext expressément limité au 2014-10-01–2023-12-29, avec confirmation de l'historique disponible et des droits de recherche locale. Les droits de redistribution dans Git ne sont pas établis ; aucune donnée externe ne doit être publiée sur cette seule base. Aucun formulaire de contact n'a été envoyé.

## Méthodologie et contrôles encore nécessaires

Le [règlement CAC 40 de février 2017, sections 4.2 et 4.3](https://www.euronext.com/sites/www.euronext.com/files/cac_40_governance_rule_book_version_17-01_february_2017_0.pdf) établit l'EUR comme devise de base. Le NR réinvestit les dividendes après retenue à la source applicable ; le GR réinvestit les dividendes bruts. Ces conventions ne constituent pas la fiscalité personnelle après liquidation d'un portefeuille. Les règles de conversion des dividendes étrangers y sont également décrites.

La spécification EOD indique une disponibilité des mises à jour à 17 h 50 CET pour les indices. Il s'agit d'un horaire de diffusion documenté, pas d'une garantie que toutes les données de toutes les places sont connues à une même heure. Pour le futur moteur, les décisions et l'exécution devront respecter les décalages Paris/États-Unis, les observations FX disponibles et l'horodatage Bitcoin.

Sans série lisible, les points suivants restent **non vérifiés** pour NR, GR et le proxy ETF :

- Première et dernière observations effectives, nombre de lignes, unicité et ordre des dates.
- Exhaustivité par rapport aux séances officielles de calcul Euronext, jours fériés et demi-séances ; un simple calendrier lundi–vendredi serait insuffisant.
- Absence de valeurs nulles, non positives, doublons et ruptures inexpliquées ; absence de toute observation après le 2023-12-29.
- Identité NR/GR, devise réellement retournée, conventions d'ajustement et traitement historique des opérations.
- Contrôle indépendant d'un échantillon de niveaux et rendements autorisés ; comparaison des écarts NR/GR ou indice/ETF et explication des différences.
- Empreinte SHA-256, version, date de récupération, requête exacte, licence et provenance archivées à côté d'une éventuelle série locale.

## Solution de repli ETF

Le DIC officiel [Amundi CAC 40 UCITS ETF Dist, FR0007052782](https://www.amundietf.fr/pdfDocuments/prospectus/FR0010655746/FRA/FRA) confirme une part EUR et une politique de distribution/capitalisation selon le prospectus. Les métadonnées de l'émetteur identifient une première VL en 2000 : cela fournit un candidat antérieur à 2014, **pas une preuve de couverture quotidienne 2014–2023**.

Pour accepter ce proxy distribuant, il faudrait obtenir les VL ou cours ajustés des splits et toutes les distributions de la fenêtre, puis vérifier indépendamment le réinvestissement. Un historique de clôtures seules ne suffit pas. Frais du fonds, écarts de suivi et retenues effectivement subies resteraient incorporés au proxy et devraient être explicités. La seule existence du fonds ne valide aucune performance historique.

Une part capitalisante plus récente telle que FR0013380607 ne doit pas être extrapolée avant son lancement sans série prédécesseur documentée. Aucun raccord, aucune reconstruction et aucun remplacement par le CAC 40 prix `^FCHI` n'ont été réalisés.

## Incident de recherche documentaire et limite de la déclaration TEST

Des résultats de recherche ont renvoyé spontanément des extraits de cotations et de reporting postérieurs à 2023, dont des éléments sans rapport avec les séries demandées. Même certaines requêtes visant un document réglementaire précis ont renvoyé une fiche mensuelle récente. Ces extraits sont apparus dans les réponses du moteur de recherche ; ils n'ont pas été utilisés, recopiés ici, enregistrés dans un dataset ou exploités pour une performance. Il serait donc inexact d'affirmer qu'aucune information postérieure à la coupure n'est apparue pendant la navigation. Les recherches ont été arrêtées ; il faudra privilégier des URL de documentation ou des exports bornés dont le contrat est établi, plutôt que des recherches susceptibles de produire des cotations courantes.

Aucun fichier local TEST n'a été ouvert ; aucune requête historique n'a demandé une observation après le 2023-12-29. Portfolio Research n'a reçu aucune écriture. Aucun code, configuration de stratégie, notebook ou sortie existante n'a été modifié. Aucun commit ni push.

## Vérifications finales

- Suite sûre publiée : `python -B -m pytest -q -p no:cacheprovider tests/test_v2.py`, avec le `src` du dépôt propre dans `PYTHONPATH` : **50 tests réussis en 51,18 s**. Aucune régression détectée dans cette suite. Les dix échecs historiques de configuration V1 ne font pas partie de ce dépôt propre ; ils n'ont pas été relancés ni corrigés ici.
- **14/14 empreintes conformes** aux références : les douze artefacts autorisés par la configuration V2, le panel DV1 et le fichier brut SP500TR identifiés dans l'audit précédent. Ce contrôle lit des octets pour les hacher, sans charger de valeurs de marché.
- Aucun changement de fichier suivi ou indexé dans le dépôt propre. Seuls les deux documents d'audit sont non suivis. Dans l'ancien dépôt, la modification préexistante de `notebooks/02_robustesse_historique.ipynb` est conservée et son contenu n'a pas été ouvert.

## Suite prioritaire

1. Obtenir un export officiel NR limité à la fenêtre autorisée avec droits d'usage et convention de date ; sinon demander GR dans les mêmes conditions.
2. À défaut, obtenir un export ETF explicitement total return avec preuve de couverture et distributions, puis le contrôler indépendamment.
3. Passer les contrôles ci-dessus avant d'autoriser cette source dans le catalogue V2.1.
4. Seulement ensuite développer le moteur et l'interface prévus, sans modifier les stratégies gelées ni calculer un faux rendement fiscal net.

Les cinq autres actifs inventoriés dans l'audit préalable restent des candidats ; l'acceptation des proxies MSCI n'équivaut pas encore à la validation indépendante de tous les ajustements et conventions de temps.

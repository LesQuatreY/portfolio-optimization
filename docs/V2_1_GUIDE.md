# Portfolio Lab V2.1 — Construire et simuler une allocation fixe

## État de la livraison

L'[audit du workflow et des six sources](V2_1_CUSTOM_WORKFLOW_AUDIT.md) vérifie la sauvegarde/relecture exacte sans données et détaille les obstacles restants. Le candidat capitalisant FR0007080973 a été absorbé en 2018 ; son successeur est passé au CAC 40 ESG le 21/03/2022. L'audit numérique des cinq autres séries ne suffit pas encore à les admettre au backtest.

La [validation finale de publication](V2_1_RELEASE_VALIDATION.md) remplace le bilan logiciel initial de 109 tests ci-dessous : **111 tests réussis**, quatre notebooks vérifiés. Le dépôt canonique est `Trading/portfolio-optimization` ; aucun historique de performance personnalisé complet n'est ajouté par cette publication.

Le moteur réutilisable, l'éditeur français, la sauvegarde JSON et les analyses sont disponibles. **Aucun backtest historique complet à six actifs n'est annoncé.** Le portefeuille « Mon portefeuille diversifié » reste EM 30 %, S&P 500 30 %, World 15 %, CAC 40 10 %, or 10 %, Bitcoin 5 %, sur 2014-10-01–2023-12-29, avec 100 000 € et rééquilibrage mensuel. Sa configuration est enregistrée dans `config/v2/portfolios/mon_portefeuille_diversifie.json`.

Le CAC 40 à rendement total est manquant. Les cinq autres sources locales sont inventoriées mais encore en attente de vérifications indépendantes et de synchronisation temporelle. Aucun actif manquant n'est remplacé par des liquidités, un rendement nul ou un indice de prix ; les poids ne sont jamais renormalisés. Les simulations de validation utilisent uniquement des données artificielles clairement identifiées.

## Utilisation

1. Ouvrir `notebooks/04_portefeuilles_personnalises.ipynb` avec l'environnement Python du projet et exécuter ses cellules.
2. Choisir les actifs, modifier les pourcentages, le nom, le capital, la fréquence et les frais. Un actif sélectionné doit avoir un poids positif et le total doit être 100 %.
3. Cliquer **Enregistrer** pour créer une configuration JSON versionnée et portable. Un identifiant SHA-256 représente tous les paramètres ; un fichier existant différent n'est jamais écrasé. **Charger** restaure un fichier du dossier dédié.
4. Le bouton **Simuler l'historique** reste désactivé si les sources sélectionnées sont manquantes ou à vérifier. Modifier l'allocation efface les résultats précédents pour éviter d'afficher une ancienne simulation sous un nouveau nom.
5. Lorsque les données auront été validées, les résultats donneront patrimoine, drawdowns, glissants, années, allocations, frais, rotation, crises, sensibilités, provenance et transactions. Le sélecteur Research propose les onze stratégies gelées, dont les six références demandées par défaut.

Le constructeur ne télécharge rien. L'ouverture, l'édition et la sauvegarde ne lisent aucune observation de marché. Les fichiers de comptes personnels restent hors de ce mécanisme. Un export HTML statique ne remplace pas le noyau Python nécessaire aux interactions ipywidgets.

## Convention financière du moteur

`custom.simulate(spec, panel)` reçoit des niveaux positifs de rendement total en EUR, déjà validés et synchronisés sur un calendrier explicite. Il refuse les trous, doublons, dates non triées, bornes incomplètes, actifs absents et toute date après la coupure. Il n'effectue ni intersection implicite, ni interpolation, ni remplissage des prix. Le calendrier attendu permet de détecter aussi une séance supprimée sur toutes les colonnes.

La cible et la fréquence sont fixées avant la séance. L'achat initial intervient à la première clôture admissible ; les rééquilibrages mensuels ou annuels ont lieu à la première séance du nouveau mois ou de la nouvelle année. L'achat-conservation n'effectue que le déploiement initial. Il n'existe aucun signal calculé sur la clôture du jour. Un test de préfixe et une perturbation de prix futurs vérifient l'absence de dépendance au futur.

**Convention d'exécution idéalisée** : panier simultané en fractions de richesse à une clôture commune, unités fractionnaires déterminées par les prix d'exécution. Cela suppose un panier en valeur et non des quantités d'ordres de courtier calculées la veille. Les niveaux d'indices/ETF à rendement total représentent des unités économiques réinvesties, pas nécessairement des titres directement négociables. Aucun arrondi de parts, spread, glissement ni contrainte de microstructure n'est simulé. Une exécution réelle nécessiterait un autre modèle validé.

La préparation des séries doit démontrer que chaque observation et chaque change est disponible à l'heure commune retenue. Une clôture américaine future ne peut servir à un ordre exécuté auparavant à Paris. L'égalité des dates civiles ne suffit pas ; les conventions Paris/US/FX/Bitcoin doivent être auditées avant l'admission des sources.

Les frais sont proportionnels à chaque achat et vente, achat initial compris. Pour une richesse avant ordres `V`, les valeurs anciennes `h`, les poids cibles `w` et le taux `c`, le moteur résout `v + c × somme(|w × v − h|) = V`. Les positions finales valent `w × v`. Cette équation inclut exactement le financement des frais et évite l'approximation au premier ordre de la V1. Aucun levier, dépôt, retrait ou emprunt n'est ajouté. Le résidu de liquidités représente seulement l'arrondi flottant, contrôlé par une tolérance comptable. Aucun intérêt n'est attribué à ce résidu.

Le registre fournit valeur avant ordres, NAV après frais, liquidités, frais, notionnel absolu et rotation. **Rotation = achats + ventes divisés par la richesse avant ordres**, achat initial inclus ; ce n'est pas la demi-rotation. Les transactions conservent quantités signées, montants et frais. Aucune liquidation finale ni fiscalité personnelle n'est simulée.

## Mesures et comparabilité

Les fonctions V2 `path_returns`, `drawdown`, `recovery`, `years` et `cagr`, ainsi que le thème Plotly, sont réutilisés. La première variation inclut les frais de déploiement. Annualisation : 252 séances pour volatilité et rendement arithmétique ; durée CAGR de Research, jours calendaires inclusifs divisés par 365,25. Le Sharpe personnalisé utilise explicitement un taux de référence de 0 % par défaut ; il n'est pas présenté comme le Sharpe officiel Research basé sur EONIA/€STR. Une variance nulle donne un Sharpe indisponible.

Les glissants de trois et cinq ans utilisent la dernière observation disponible au plus tard à la date anniversaire passée et la durée réellement écoulée. La comparaison de fréquences se limite aux trois modes prédéfinis ; aucun choix de poids ou de mode gagnant n'est optimisé. Les analyses de fenêtres distinguent 2014–2018, 2019–2023, T4 2018, le choc COVID du 19 février au 23 mars 2020 et l'année 2022. Elles décrivent rendements, risques, récupération et corrélations quand au moins vingt observations sont disponibles.

La comparaison Research requiert les mêmes dates et le même calendrier ; une démonstration synthétique est refusée. Les courbes Research incluent leurs frais et impôts intermédiaires gelés ; le personnalisé n'inclut que ses frais proportionnels et les coûts incorporés à ses proxies. Les titres, tableaux et infobulles signalent cette différence. Le graphique rendement/risque utilise les CAGR des trajectoires, avec sélection volatilité/MaxDD : il ne constitue pas une frontière fiscale commune. Les valeurs nettes fiscales gelées de Research sont conservées séparément ; **CAGR net fiscal personnalisé : Non calculé**.

## Admission future d'une source réelle

`config/v2/custom_assets.yaml` conserve aujourd'hui six entrées non validées. Passer une entrée à `validated` nécessite une revue humaine préalable, pas seulement une modification de ce mot : provenance et licence, EUR, dividendes, couverture, calendrier, heure d'information, contrôle indépendant et empreinte SHA-256. Les proxies MSCI doivent rester étiquetés ETF, jamais MSCI NETR officiel.

Le chargeur local attend, pour chaque actif, un CSV/parquet `Date,level` dans `data/v2_1/`, avec `path`, `sha256`, `source`, `currency`, `dividends`, `independent_check`, `calendar`, `clock`, `calendar_path`, `calendar_sha256`. Le calendrier commun est un CSV à seule colonne `Date`, lui aussi épinglé. Toutes les sources doivent partager le calendrier et la convention temporelle. Les contrôles `ResearchGuard` existants sont appelés avant et après lecture, sans modification de leur code. Les chemins échappant au dossier local sont refusés. Le dossier de données et les exports restent ignorés par Git ; aucun artefact Research n'y a été copié.

Pour le CAC 40, priorité au NR officiel, puis GR officiel, puis ETF FR0007052782 avec réinvestissement vérifié. Les deux essais complémentaires ETF de cette livraison (2014-10-01–2014-10-03 et 2023-12-27–2023-12-29) renvoient toujours l'enveloppe JSON opaque déjà décrite dans `V2_1_CAC_DATA_INVESTIGATION.md`. Aucun prix n'a été inspecté ou intégré. Une recherche ciblée sur le code d'export public n'a fourni aucun résultat exploitable. Il n'existe donc toujours pas de preuve de complétude, de distributions ou de contrôle indépendant permettant d'utiliser cette série.

## Validation

```powershell
python -B -m pytest -q -p no:cacheprovider
python -B scripts/validate_custom.py --render
```

Utiliser le Python contenant les dépendances du projet, avec ce dépôt `src` dans `PYTHONPATH` si le paquet n'est pas installé. La deuxième commande exécute le notebook dans un noyau neuf, vérifie les interactions bloquantes, puis exporte des figures **SYNTHÉTIQUES** en HTML, PNG et SVG dans `outputs/v2_1/`. Les exports ne modifient pas le notebook source. Les empreintes des douze artefacts gelés sont comparées avant/après.

Les tests financiers comprennent un oracle rationnel indépendant : 100 € répartis à 50/50, niveaux A/B `10/10`, `20/10`, `20/20`, `10/20`. En mensuel sans frais, NAV attendues `100, 150, 225, 187,5`. En achat-conservation `100, 150, 200, 150`. Avec 10 % de frais par notionnel, les deux premières NAV sont exactement `1000/11` puis `1450/11`, obtenues à la main et non par un second appel au moteur.

La validation logicielle ne valide aucune performance historique. Portfolio Research reste strictement en lecture seule, ses stratégies et empreintes restent inchangées et TEST reste verrouillé. Aucun commit ni push n'est effectué.

## Résultat des contrôles de cette livraison

- Suite complète : **109 tests réussis en 35,66 s**, soit les **50 tests V2 conservés et 59 nouveaux tests**. Aucun échec. Les dix échecs historiques V1 de configuration ne font pas partie du dépôt propre et n'ont pas été modifiés.
- Notebook 04 exécuté dans un noyau neuf ; contrôle des poids invalides, du blocage des données et du rechargement de configuration réussi. Le notebook source conserve zéro sortie enregistrée.
- Huit vues exportées en HTML local et en PNG/SVG aux largeurs 640 et 1 050 pixels : 16 PNG et 16 SVG. Contrôle visuel des allocations, de la cible, des glissants et des années ; les performances de validation portent un titre « Validation synthétique ».
- Douze empreintes Research gelées identiques avant/après. Aucun module existant V2, garde-fou, stratégie ou artefact Research modifié. Le notebook déjà modifié dans l'ancien dépôt reste conservé.
- Comparaison temporelle : au-delà de l'égalité des calendriers, l'adaptateur exige `research_alignment: validated_paris_session_end` dans la provenance de chaque actif. Cette attestation reste à établir lors de la validation des sources ; aucune comparaison réelle n'a été produite ici.
- Travail non indexé sur `feature/custom-portfolios-v2-1`, sans commit ni push. Les données locales futures et les exports sont ignorés par Git.

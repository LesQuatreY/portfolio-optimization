# Portfolio Lab V2.1 — Validation finale de publication

Validation du 18 octobre 2026, depuis le dépôt canonique `Trading/portfolio-optimization`, branche `feature/custom-portfolios-v2-1`. Remote vérifié : `https://github.com/LesQuatreY/portfolio-optimization.git`. Cette livraison prolonge le checkpoint `918d286`, sans réécriture d'historique. Les résultats ci-dessous concernent la validation locale préalable à la publication.

## Fonctionnalités livrées

- Notebook 04 : création et nommage de portefeuilles, édition des poids, capital et frais ; interface interactive française.
- Sauvegarde JSON et relecture exacte, y compris depuis une nouvelle instance, indépendantes de la disponibilité des historiques. Les fichiers sont limités au dossier de configurations du Lab ; aucun fichier Research n'est écrit.
- Moteur à poids cibles fixes : mensuel, annuel et achat-conservation ; financement exact des frais proportionnels et unités fractionnaires. Vérification sur des oracles et données synthétiques explicitement étiquetées.
- Configuration initiale « Mon portefeuille diversifié » : EM 30 %, S&P 500 30 %, World 15 %, CAC 40 10 %, or 10 %, Bitcoin 5 %, EUR, 100 000 €, mensuel, 2014-10-01–2023-12-29.
- Blocage explicite de la simulation historique si les sources sont absentes ou non validées ; aucune renormalisation, substitution ou fabrication de rendements.

## Contrôles exécutés

| Contrôle | Résultat |
|---|---|
| Suite complète pytest | **111 réussis, 0 échec**, 9,15 s : 50 tests V2 et 61 tests personnalisés |
| Notebook 01, noyau neuf | PASS, 8 cellules de code ; interactions de sélection vérifiées |
| Notebook 02, noyau neuf | PASS, 8 cellules de code ; interactions de sélection vérifiées |
| Notebook 03, noyau neuf | PASS, 7 cellules de code ; interactions de sélection vérifiées |
| Notebook 04, noyau neuf | PASS ; allocation et nom exacts, sauvegarde/relecture sur disque, poids invalides et historique indisponible |
| Reproduction Research gelée | 11 portefeuilles, **88 indicateurs** et **10 contrôles comptables** conformes |
| Intégrité Research | **12/12 SHA-256** conformes aux références et identiques avant/après les validateurs |
| TEST 2024–2026 | Coupure dure **2023-12-29**, tests adverses réussis ; aucun fichier local TEST ouvert |
| Quatre notebooks sources | Aucune sortie, aucun compteur d'exécution, aucun état de widgets sauvegardé |

Les validations ont été réalisées sans téléchargement de données ni nouvelle recherche de marché. Les avertissements techniques du noyau Jupyter n'ont pas empêché les exécutions. Les contrôles synthétiques du moteur ne valident aucune performance historique réelle. Aucun nouveau rendu PNG/SVG ni audit de données de marché n'a été lancé pour cette finalisation.

## Reproduire les contrôles

Depuis la racine du dépôt, avec l'environnement décrit dans le README :

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider
.\.venv\Scripts\python.exe -B scripts/validate_v2.py
.\.venv\Scripts\python.exe -B scripts/validate_custom.py
git diff --check
```

Research doit être disponible au chemin configuré dans `config/v2/lab.yaml`, avec les empreintes gelées attendues. Les validateurs refusent toute altération et n'importent pas le moteur Research. Les exports sont écrits uniquement dans `outputs/v2/` et `outputs/v2_1/`, ignorés par Git. Les notebooks exécutés ne remplacent pas les sources.

## Périmètre Git

Publication des sources, configurations JSON/YAML, tests et documentation uniquement. La configuration secondaire `custom portfolio` reprend les mêmes six poids, le capital normalisé et la fenêtre de développement ; elle ne contient aucune donnée de compte personnel ni observation de marché.

Les sorties préexistantes du notebook 04 ont été conservées dans `outputs/v2_1/prepublication/`, puis retirées de la source. Les exclusions Git couvrent sorties, caches, environnements, checkpoints Jupyter, données locales V2.1 et fichier de comptes personnels. Aucun fichier de cours, rapport HTML généré ou figure n'est ajouté. Le manifeste de publication V2 est historique et n'est pas réécrit pour prétendre couvrir cette livraison.

Le push autorisé vise uniquement `refs/heads/feature/custom-portfolios-v2-1` sur `origin`, sans force ni fusion dans `main`, sans modification de branche par défaut et sans suppression de sauvegardes. Le SHA publié est celui du commit contenant ce rapport ; il se retrouve dans l'historique Git de cette branche.

## Blocages conservés pour la prochaine phase

Le backtest historique complet à six actifs reste **indisponible**. Le CAC 40 à rendement total manque encore sous une forme quotidienne complète et validée. FR0007080973 a été absorbé en 2018, puis son successeur a adopté le CAC 40 ESG au 21/03/2022 : il ne constitue pas une continuité CAC 40 homogène jusqu'à fin 2023. Les cinq autres séries restent en attente de contrôles externes et d'une convention causale commune Paris/États-Unis/change/Bitcoin, notamment pour les distributions, raccords et calendriers.

Voir [l'audit détaillé existant](V2_1_CUSTOM_WORKFLOW_AUDIT.md) et le [guide du constructeur](V2_1_GUIDE.md). Aucune source n'est promue au statut `validated` pour permettre artificiellement la simulation. BRK.B demeure un projet séparé, non commencé ici.

# Publication autonome de Portfolio Lab V2

## Publication V2.1 depuis le dépôt canonique

Le dépôt de travail canonique est désormais `Trading/portfolio-optimization`. La branche `feature/custom-portfolios-v2-1` prolonge les commits V2 existants, sans recréer de racine ni réécrire l'historique. La publication V2.1 vise uniquement la branche homonyme sur `https://github.com/LesQuatreY/portfolio-optimization.git`, sans force, fusion dans `main` ni changement de branche par défaut. Les procédures de création initiale d'un dépôt distinct ci-dessous sont des archives de la publication V2, pas des instructions pour la V2.1.

La [validation finale V2.1](V2_1_RELEASE_VALIDATION.md) couvre les 111 tests, les quatre notebooks sans sorties, les empreintes Research et le verrou TEST. Les fichiers générés restent dans `outputs/` et les données locales dans `data/v2_1/`, ignorés par Git. Le manifeste de publication initial reste une référence historique ; il ne constitue pas la liste ni les empreintes des ajouts V2.1.

## Historique de la publication initiale V2

La branche `portfolio-lab-v2-clean` est reconstruite à partir d'une liste explicite de fichiers du commit local `ff544ba`, sans parent Git. Aucun ancien commit n'est son ancêtre ; les identifiants cités dans la documentation sont des références textuelles et ne rendent pas leurs objets accessibles depuis cette branche.

## Préservation et provenance

La branche locale `portfolio-lab-v2` et ses checkpoints, notamment `6e0a11a` et `ff544ba`, restent inchangés. Les sorties du notebook ouvert restent dans le dépôt de travail d'origine. La publication est préparée dans un dossier distinct avec un dépôt Git neuf : aucun objet de l'ancien dépôt n'y est partagé ou importé.

Les dix modules V2, le fichier d'initialisation du paquet, les deux configurations, les trois notebooks sans sorties, le test V2, le validateur et les fichiers de dépendances sont copiés à l'identique. Le [manifeste](PUBLICATION_MANIFEST.json) contient les SHA-256 des 25 fichiers sélectionnés dans le commit source.

Seuls le README et les deux documents V2 ont été adaptés pour expliquer le périmètre de publication et éviter les liens vers les fichiers V1 exclus. Ce document et le manifeste sont des pièces de traçabilité nouvelles. Aucun calcul financier ni fonctionnalité n'a changé.

## Exclusions

- Tous les notebooks d'archives et les notebooks historiques V1.
- Les anciennes versions de notebooks et tous les commits parents.
- Les sorties de notebook, les rapports générés et le registre d'expériences historique.
- Les données ou moteurs Portfolio Research, les fichiers de comptes personnels, les secrets, les caches et environnements locaux.
- Le moteur V1, ses tests, sa configuration et son lanceur, qui sont préservés localement.

## Contrôles de publication

Avant le push : comparaison des fichiers fonctionnels avec leurs empreintes source, vérification des cellules et de l'absence de sorties/widgets sauvegardés dans les trois notebooks, contrôle de la liste des fichiers et de tous les objets Git accessibles depuis la nouvelle branche. La branche doit contenir exactement un commit racine sans parent, avec uniquement les fichiers autorisés.

Les 50 tests V2 s'exécutent depuis le dossier de publication, en chargeant explicitement son paquet Python. Ils couvrent les 88 indicateurs, les réconciliations comptables, les dates, l'intégrité, les entrées adverses synthétiques et les interactions des widgets. Seuls les artefacts de développement autorisés sont lus dans Research, avec empreintes vérifiées avant/après. Aucun notebook ou résultat TEST n'est ouvert, copié ou exécuté.

Résultat avant création du commit : **50 tests réussis, aucun échec**, en 18,44 secondes. Les 22 fichiers non documentaires sont identiques octet pour octet au commit source ; les trois notebooks ne contiennent ni sorties ni état de widgets sauvegardé.

Le push doit créer uniquement `origin/portfolio-lab-v2-clean`, sans force et sans modification de `main` ou d'une branche distante existante. La vérification finale compare le commit annoncé par le serveur au commit local audité.

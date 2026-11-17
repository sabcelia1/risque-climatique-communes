# Journal d'analyse

Ce journal trace la démarche : observations, hypothèses, tests et décisions, y compris les pistes qui se révèlent fausses.

**Légende des statuts :** ✅ validée · ❌ rejetée · 🔍 à vérifier · 📌 décision

---

## Étape 1 — Ingestion et qualité

### 📌 Choix de la source principale

- **Base GASPAR** du ministère de la Transition écologique, la source officielle des reconnaissances CatNat depuis 1982.
- Une version retraitée existe aussi sur data.gouv.fr (« Arrêtés de catastrophe naturelle par commune », 260 601 lignes, enrichie des découpages territoriaux, mise à jour en septembre 2025). Elle est écartée : on lui préfère la **source primaire**, plus récente et dont on maîtrise le nettoyage.

### Défauts connus avant même le premier téléchargement

Les discussions publiques du jeu de données ([data.gouv.fr](https://www.data.gouv.fr/datasets/base-nationale-de-gestion-assistee-des-procedures-administratives-relatives-aux-risques-gaspar/discussions)) signalent :

- des **doublons** : lignes répétées 2 ou 3 fois (avril 2025), puis encore dans la base du 03/11/2025 ;
- des **accents mal encodés** dans les libellés de communes et de périls (juillet 2024) ;
- des **dates incohérentes** : fin postérieure à la publication de l'arrêté, durées de plus d'un an hors sécheresse (juillet 2024), dates décalées d'un jour par rapport aux arrêtés publiés (novembre 2025) ;
- des **noms de fichiers et de colonnes qui changent** entre versions (2025-2026) ;
- le fichier ne contient que les **reconnaissances accordées**, pas les demandes refusées.

📌 **Décision :** l'ingestion et le nettoyage sont conçus pour résister à ces variations (détection du format, table de correspondance des colonnes, dédoublonnage tracé), et des tests unitaires les vérifient.

### Points d'attention pour la modélisation (étape 3)

- **Biais de sélection :** seules les reconnaissances accordées figurent dans la base. Une commune sans reconnaissance peut avoir subi un événement dont la demande a été refusée, ou pas déposée. Le modèle prédira donc la **probabilité d'une reconnaissance**, pas celle d'un événement climatique.
- **Délais de publication :** un arrêté est publié plusieurs mois après l'événement. Les années les plus récentes sont donc incomplètes, et il faudra les exclure de l'évaluation ou en tenir compte.
- **Évolution des critères :** les règles de reconnaissance, notamment pour la sécheresse, ont changé au fil du temps. Une validation **temporelle** (entraîner sur le passé, tester sur les années récentes) s'impose.

### Hypothèses de départ

| # | Hypothèse | Statut |
|---|---|---|
| H1 | La part des reconnaissances « sécheresse » augmente nettement depuis 2015 | ✅ validée : 6 % → 26 % → 51 % |
| H2 | Les reconnaissances sont très concentrées : une minorité de communes en cumule la majorité | ❌ rejetée : les 10 % de communes les plus touchées n'en concentrent que 24 % |
| H3 | Une part non négligeable des codes communes correspond à des communes fusionnées depuis | ❌ rejetée : 582 lignes, soit 0,2 % |
| H4 | La quasi-disparition des reconnaissances « vent » et « mouvement de terrain » après 2000 reflète un changement de règles ou de libellés, pas une évolution du climat | 🔍 à vérifier |

---

## Résultats sur les données réelles (extraction GASPAR du 2 novembre 2026)

### Vue d'ensemble

- **247 140 lignes** brutes, **247 139** après suppression d'un doublon exact, de 1982 à 2025.
- **98,9 %** des communes actuelles ont eu au moins une reconnaissance depuis 1982.
- Colonnes de cette version : `id_gaspar`, `code_commune`, `libelle_commune`, `num_risque_jo`, `lib_risque_jo`, `date_debut`, `date_fin`, `date_signature_arrete`, `date_publication_jo`, `date_modification`. Les noms ont changé par rapport aux versions décrites dans les discussions publiques (`cod_commune`, `dat_deb`…), ce qui confirme l'intérêt d'une détection robuste.

### ❌ Erreur corrigée : de faux doublons au premier passage

- **Constat :** au premier passage, le nettoyage avait supprimé **1 050 « doublons » exacts**. Au second, après une meilleure reconnaissance des colonnes, il n'en reste qu'**un seul**.
- **Explication :** au premier passage, les colonnes de dates d'arrêté et de publication n'étaient pas reconnues et étaient donc ignorées. Des lignes qui ne différaient que par ces dates paraissaient identiques.
- **Ce que sont ces lignes :** le même événement (même commune, même péril, mêmes dates) apparaît plusieurs fois avec des dates d'arrêté différentes, probablement des arrêtés rectificatifs ou modificatifs.
- 📌 **Décision :** ces lignes sont **conservées** et marquées (`evenement_repete`). Les agrégats comptent des **événements distincts** (commune × péril × dates) et non des lignes, pour ne pas compter deux fois le même sinistre.
- **Leçon :** un dédoublonnage « exact » dépend des colonnes qu'on regarde. Le rapport qualité liste désormais les colonnes reconnues, pour rendre ce type d'erreur visible.

### H1 — Montée de la sécheresse ✅

Répartition des reconnaissances par famille de péril (%) :

| Période | Inondation | Sécheresse | Mouvement de terrain | Vent/tempête | Séisme | Autre |
|---|---:|---:|---:|---:|---:|---:|
| 1982-1999 | 58,9 | **6,3** | 19,8 | 10,1 | 0,3 | 4,6 |
| 2000-2014 | 61,0 | **25,5** | 5,6 | 0,1 | 0,3 | 7,5 |
| 2015 et après | 45,5 | **50,9** | 2,6 | 0,1 | 0,2 | 0,7 |

- Depuis 2015, **la sécheresse est le premier péril reconnu**, devant l'inondation.
- **Limite :** il s'agit de nombres de reconnaissances, pas de montants d'indemnisation, et une partie de la hausse peut venir de l'évolution des critères de reconnaissance de la sécheresse.
- **Note :** ce tableau a été calculé avant le reclassement des « chocs mécaniques liés à l'action des vagues » (6 720 lignes) de « autre » vers « vent/tempête » ; les colonnes « vent/tempête » et « autre » seront légèrement modifiées au prochain passage.

### H2 — Concentration ❌, mais un effet de taille

- Les 10 % de communes les plus touchées ne concentrent que **24,2 %** des reconnaissances. Le risque est **diffus** : presque toutes les communes sont concernées.
- Les communes les plus touchées sont de **grandes villes** (Nice 83, Marseille 51, Bordeaux 50, Toulouse 49) et **trois communes nouvelles issues de fusions** (Gennes-Val-de-Loire, Doué-en-Anjou, Bassillac et Auberoche), qui cumulent l'historique de plusieurs anciennes communes.
- 📌 **Décision pour la modélisation :** une grande commune a mécaniquement plus de chances qu'une partie de son territoire soit touchée. Le modèle devra tenir compte de la **taille** (superficie, population), sinon il prédira surtout… la taille des communes.

### Données récentes incomplètes

| Année de l'événement | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Reconnaissances | 4 022 | 2 838 | 8 089 | 3 454 | 3 277 | **555** | **0** |

- Délai entre le début de l'événement et l'arrêté : **40 jours en médiane**, mais **483 jours** pour 90 % des cas. Ce long délai vient probablement des sécheresses, dont la reconnaissance demande un recul sur toute la saison : à vérifier avec le délai par famille de péril (ajouté à `explorer.py`).
- **Aucun événement de 2026** dans une extraction du 2 novembre 2026, alors que la moitié des arrêtés sont pris en moins de 40 jours : l'export semble arrêté aux événements de 2025, voire en retard. À vérifier sur la prochaine version.
- 📌 **Décision :** **2025 est exclue** de l'apprentissage et de l'évaluation, car elle est incomplète. La période de modélisation s'arrête à 2024.

### H4 — Vent et mouvements de terrain : changement de règles ? 🔍

- **Observation :** les reconnaissances « vent/tempête » passent de 10,1 % à 0,1 % après 2000, et les « mouvements de terrain » de 19,8 % à 2,6 %.
- **Hypothèse :** ces baisses brutales ressemblent davantage à des changements de règles de prise en charge ou de libellés qu'à une évolution du climat. Le vent relève en général d'autres garanties d'assurance que le régime CatNat, mais ce point reste à vérifier dans les textes.
- **Conséquence :** le modèle sera construit **par famille de péril**, en commençant par la sécheresse et l'inondation, qui représentent l'essentiel des reconnaissances récentes. Les années anciennes seront utilisées avec prudence.

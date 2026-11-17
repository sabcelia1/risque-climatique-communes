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
| H1 | La part des reconnaissances « sécheresse » augmente nettement depuis 2015 | ✅ validée : 6,3 % → 25,4 % → 50,9 % |
| H2 | Les reconnaissances sont très concentrées : une minorité de communes en cumule la majorité | ❌ rejetée : les 10 % de communes les plus touchées n'en concentrent que 24,1 % |
| H3 | Une part non négligeable des codes communes correspond à des communes fusionnées depuis | ❌ rejetée : 582 lignes, soit 0,2 % |
| H4 | La quasi-disparition des reconnaissances « vent » et « mouvement de terrain » reflète un changement de règles ou de libellés, pas une évolution du climat | 🔍 à vérifier |
| H5 | Les sécheresses sont reconnues bien plus tard que les autres périls | ✅ validée : 533 jours en médiane, contre 34 pour l'inondation |

---

## Résultats sur les données réelles (extraction GASPAR du 2 novembre 2026)

### Vue d'ensemble

- **247 140 lignes**, aucun doublon strict, de 1982 à 2025.
- **246 088 événements reconnus distincts** (commune × péril × dates) : 1 052 lignes répètent un même événement, probablement des arrêtés rectificatifs.
- **98,9 %** des communes actuelles ont eu au moins une reconnaissance depuis 1982.
- Colonnes de cette version : `id_gaspar`, `code_commune`, `libelle_commune`, `num_risque_jo`, `lib_risque_jo`, `date_debut`, `date_fin`, `date_signature_arrete`, `date_publication_jo`, `date_modification`. Elles diffèrent des versions décrites dans les discussions publiques (`cod_commune`, `dat_deb`…), ce qui justifie une détection robuste.
- Répartition des lignes : inondation 57,0 %, sécheresse 17,6 %, mouvement de terrain 14,2 %, vent/tempête 9,2 %, autre 1,7 %, séisme 0,3 %.

### ❌ Deux erreurs de dédoublonnage, détectées et corrigées

Le nettoyage a été exécuté quatre fois sur les données réelles. Deux erreurs successives ont été repérées grâce au rapport de qualité.

**Erreur 1 : de faux doublons « exacts »**
- Au premier passage, le script supprimait **1 050 lignes** strictement identiques.
- **Cause :** les colonnes de dates d'arrêté et de publication n'étaient pas encore reconnues, donc ignorées. Des lignes qui ne différaient que par ces dates semblaient identiques.
- Une fois ces colonnes reconnues, **aucun** doublon strict ne subsiste. Les 1 050 lignes correspondent en fait aux **1 052 répétitions d'un même événement** avec des dates d'arrêté différentes.

**Erreur 2 : un identifiant supposé unique qui ne l'est pas**
- Une fois `id_gaspar` reconnu, le script supprimait les lignes partageant le même identifiant, la même commune et le même péril : **5 679 lignes** retirées.
- **Cause :** l'hypothèse « un identifiant = une reconnaissance » n'avait pas été vérifiée. En réalité, **10 953 lignes** partagent un identifiant avec une autre ligne de la même commune et du même péril, mais avec des **dates différentes** : plusieurs périodes reconnues par un même arrêté (fréquent pour la sécheresse) ou anciennes communes regroupées sous un même code.
- **Signal d'alerte :** des communes nouvelles comme Gennes-Val-de-Loire avaient disparu du classement des communes les plus touchées.

📌 **Décisions :**
- On ne supprime **que** les doublons stricts, sur toutes les colonnes.
- Les répétitions d'un même événement sont **conservées et marquées** (`evenement_repete`) ; les agrégats comptent des **événements distincts**.
- Le rapport qualité liste les colonnes reconnues, et un **test de non-régression** vérifie que deux périodes d'un même arrêté restent deux événements.

**Leçon :** un dédoublonnage dépend des colonnes qu'on regarde et des hypothèses faites sur les identifiants. Il faut le vérifier sur les données, pas le supposer.

### H1 — Montée de la sécheresse ✅

Répartition des événements reconnus par famille de péril (%) :

| Période | Inondation | Sécheresse | Mouvement de terrain | Vent/tempête | Séisme | Autre |
|---|---:|---:|---:|---:|---:|---:|
| 1982-1999 | 58,7 | **6,3** | 19,9 | 12,1 | 0,3 | 2,7 |
| 2000-2014 | 61,1 | **25,4** | 5,6 | 7,5 | 0,3 | 0,1 |
| 2015 et après | 45,5 | **50,9** | 2,6 | 0,8 | 0,2 | 0,0 |

- Depuis 2015, **la sécheresse est le premier péril reconnu**, devant l'inondation.
- **Limite :** ce sont des nombres de reconnaissances, pas des montants d'indemnisation, et une partie de la hausse peut venir de l'évolution des critères de reconnaissance de la sécheresse.

### H5 — Délais de reconnaissance ✅

| Famille de péril | Délai médian (jours) | Délai pour 90 % des cas (jours) |
|---|---:|---:|
| Vent/tempête | 12 | 46 |
| Mouvement de terrain | 4 | 112 |
| Inondation | 34 | 159 |
| Séisme | 140 | 358 |
| Autre | 59 | 175 |
| **Sécheresse** | **533** | **1 531** |

- Une sécheresse est reconnue en **un an et demi en médiane**, et jusqu'à **plus de 4 ans** pour 90 % des cas : la reconnaissance demande un recul sur toute la saison, voire plusieurs années.

### Données récentes incomplètes

| Année de l'événement | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Événements reconnus | 4 012 | 2 832 | 8 087 | 3 442 | 3 260 | **555** | **0** |

- **Aucun événement de 2026** dans une extraction du 2 novembre 2026, alors que la moitié des arrêtés sont pris en moins de 40 jours : l'export semble arrêté aux événements de 2025. À vérifier sur la prochaine version.
- 📌 **Décisions pour la modélisation (étape 3) :**
  - **2025 exclue** partout, car incomplète.
  - **Inondation :** 90 % des reconnaissances arrivent en moins de 159 jours, donc les années jusqu'à **2024** sont exploitables.
  - **Sécheresse :** 90 % arrivent en 4,2 ans, donc les années **2022 à 2024 sont encore incomplètes**. Le modèle sécheresse sera évalué sur des années antérieures, sinon il serait pénalisé à tort sur des sécheresses pas encore reconnues.

### H2 — Concentration ❌, mais un effet de taille et de territoire

- Les 10 % de communes les plus touchées ne concentrent que **24,1 %** des événements : le risque est **diffus**.
- Médiane : **6 événements** par commune touchée depuis 1982 ; maximum : **82** (Nice).
- Les dix communes les plus touchées : Nice (82), Cagnes-sur-Mer (65), Antibes (52), Cannes (52), Marseille (51), Gennes-Val-de-Loire (49), Bordeaux (48), Toulouse (48), Villeneuve-Loubet (43), Èze (42).
- **Deux effets se superposent :**
  - un **effet de taille** : grandes villes, et communes nouvelles comme Gennes-Val-de-Loire qui cumulent l'historique de plusieurs anciennes communes ;
  - un **effet de territoire** : **6 des 10** communes les plus touchées sont dans les **Alpes-Maritimes**.
- 📌 **Décision :** le modèle tiendra compte de la taille (superficie, population) et de la localisation, sinon il prédira surtout la taille des communes.

### H4 — Vent et mouvements de terrain : changement de règles ? 🔍

- **Observation :** les reconnaissances « vent/tempête » passent de 12,1 % à 0,8 %, et les « mouvements de terrain » de 19,9 % à 2,6 %.
- **Hypothèse :** des baisses aussi brutales ressemblent davantage à des changements de règles de prise en charge ou de libellés qu'à une évolution du climat. Le vent relève en général d'autres garanties d'assurance que le régime CatNat, mais ce point reste à vérifier dans les textes.
- **Conséquence :** le modèle sera construit **par famille de péril**, en commençant par la **sécheresse** et l'**inondation**, qui représentent 96 % des événements reconnus depuis 2015.

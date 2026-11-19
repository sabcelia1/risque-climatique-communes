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

---

## Étape 2 — Data engineering

### 📌 Choix d'architecture

- **dbt** pour toutes les transformations SQL : chaque table est versionnée, documentée et testée, et ses dépendances sont explicites.
- **Deux cibles pour le même code :** DuckDB en local (aucun compte cloud, tests rapides) et BigQuery en production. Le SQL évite les fonctions propres à une seule base, et les rares différences passent par une macro (`serie_annees`).
- **Rechargement complet à chaque exécution** plutôt qu'incrémental : la base GASPAR est republiée en entier (et corrigée rétroactivement), elle reste petite (≈ 250 000 lignes), et le bac à sable BigQuery n'autorise pas les mises à jour ligne à ligne (`MERGE`).
- **Aucune clé, nulle part :** la création de clés de compte de service est bloquée par la règle de sécurité par défaut de l'organisation Google Cloud (`iam.disableServiceAccountKeyCreation`). Plutôt que de lever cette protection, le pipeline s'authentifie par **fédération d'identité** (Workload Identity Federation) : GitHub présente un jeton temporaire signé, accepté uniquement pour ce dépôt, et le compte de service n'a que deux droits BigQuery. Il n'y a aucun secret à stocker ni à renouveler.

### 📌 Une grille complète, zéros compris

Pour calculer « le nombre d'événements des 5 dernières années », une fenêtre SQL compte des **lignes**, pas des années. Si les années sans reconnaissance n'existent pas dans la table, « 5 lignes précédentes » peut couvrir 20 ans. `int_grille_commune_annee` crée donc **toutes** les combinaisons commune × année × péril, avec 0 les années sans événement (≈ 35 000 communes × 43 ans × 2 périls ≈ 3 millions de lignes).

### 📌 Interdire la fuite de données

Le risque principal d'un modèle de prévision : utiliser, sans s'en rendre compte, une information de l'année que l'on cherche à prédire. Les performances semblent excellentes, puis s'effondrent en conditions réelles.

- Toutes les variables de `mart_features_risque` s'arrêtent à l'**année précédente** (fenêtres `... and 1 preceding`, taux départemental de `t-1`).
- Un **test dbt** recalcule ces variables par une autre méthode (jointure) et échoue à la moindre différence.
- **Le test a été lui-même testé :** en remplaçant volontairement une fenêtre par une version qui inclut l'année courante, il échoue (549 lignes en erreur sur les données d'essai).
- Les totaux de `dim_commune` couvrent toute la période : ils sont réservés à la description et **exclus** des variables du modèle.

### 📌 Années évaluables

Les décisions de l'étape 1 sont codées une seule fois, dans `dbt_project.yml` :

| Famille | Dernière année évaluable | Raison |
|---|---:|---|
| Inondation | 2024 | 90 % des reconnaissances en moins de 159 jours |
| Sécheresse | 2021 | 90 % des reconnaissances en moins de 4,2 ans |

La colonne `annee_evaluable` signale les autres lignes, que l'étape 3 n'utilisera ni pour l'entraînement ni pour l'évaluation. `historique_complet` signale les années disposant de 10 ans de recul (à partir de 1992).

### Limites assumées

- **Communes fusionnées :** les 0,2 % de lignes dont le code a disparu du référentiel (H3) sont écartées des modèles plutôt que rattachées, faute de table de passage simple à maintenir. Effet négligeable vu leur volume.
- **Population actuelle :** la population et la superficie sont celles d'aujourd'hui, appliquées à toutes les années. C'est acceptable pour un ordre de grandeur (effet de taille), mais ce n'est pas la population de chaque année.

---

## Étape 3 — Machine learning

### 📌 Protocole

- **Un modèle par péril** (inondation, sécheresse), cible : « au moins une reconnaissance dans l'année ».
- **Découpage temporel**, années évaluables seulement (décision de l'étape 1) :

| Péril | Entraînement | Validation (choix du modèle) | Test (une seule fois) |
|---|---|---|---|
| Inondation | 1992-2018 | 2019-2020 | 2021-2024 |
| Sécheresse | 1992-2014 | 2015-2016 | 2017-2021 |

- **Deux références** à battre : l'historique de la commune (fréquence depuis 1982) et une régression logistique.
- **Métriques par année :** le niveau global d'une année dépend de sa météo, inconnue au 1er janvier. On mesure donc la capacité à **classer** les communes au sein d'une même année : AUC, et part des communes touchées captée par les 10 % de communes jugées les plus à risque (« top 10 % » ; un ciblage au hasard en capte 10 %).
- Les essais ont été faits sur une branche séparée ([`experiences`](https://github.com/sabcelia1/risque-climatique-communes/tree/experiences)), et **seule la validation** a servi à décider.

### ❌ Fuite de données n° 2 : des informations pas encore disponibles

- **Observation :** au 1er janvier, **0 %** des sécheresses de l'année précédente sont déjà reconnues, contre 81,5 % des inondations (délai médian de 533 jours, H5).
- **Problème :** la première version comptait tous les événements des années passées, y compris ceux dont l'arrêté n'avait pas encore été signé. Le modèle s'entraînait donc avec une information qu'il n'aurait jamais au moment de prédire, et ses prédictions réelles (où les années récentes sont incomplètes) auraient été biaisées.
- 📌 **Décision :** variables **« à date »** (`int_historique_a_date`) : un événement n'est compté que si son arrêté est signé avant le 1er janvier de l'année prédite. Le test anti-fuite a été réécrit avec une logique inverse (chaque événement projeté en avant) et vérifié en réintroduisant volontairement la fuite (2 001 lignes en erreur sur les données d'essai).
- **Effet :** dans les essais (protocole identique), l'AUC de test de la sécheresse baisse d'environ 0,01 : la première version était un peu trop optimiste.

### Essais écartés (décidés sur la validation)

| Essai | Effet en validation | Décision |
|---|---|---|
| Régularisation plus forte | ± 0,005 d'AUC | Écarté : pas d'effet net |
| Entraînement sur les 12 dernières années seulement | + 0,01 inondation, - 0,01 sécheresse | Écarté : effet contradictoire |
| Plans de prévention (PPR) et atlas des zones inondables, datés | + 0,003 à + 0,009 | Écarté pour le modèle : gain dans le bruit, l'historique contient déjà l'information. Utile pour les fiches de l'étape 4. |

- **Le bruit :** le seul changement d'ordre des lignes fait varier l'AUC d'environ 0,01. Les écarts plus faibles que cela ne justifient pas d'ajouter de la complexité.
- Les communes couvertes par un PPR sont pourtant **deux fois** plus souvent reconnues (inondation : 7,2 % contre 3,6 % par an sur 2015-2021 ; sécheresse : 11,4 % contre 4,9 %). Un fort lien isolé n'apporte rien au modèle s'il est déjà capté par d'autres variables.

### Résultats

| Péril | Modèle | AUC validation | AUC test | Top 10 % test |
|---|---|---:|---:|---:|
| Inondation | **LightGBM** | **0,742** | **0,667** | 23,2 % |
| | Régression logistique | 0,656 | 0,627 | 21,2 % |
| | Historique de la commune | 0,695 | 0,644 | 23,0 % |
| Sécheresse | **LightGBM** | **0,903** | **0,752** | 25,4 % |
| | Régression logistique | 0,890 | 0,733 | 30,8 % |
| | Historique de la commune | 0,867 | 0,710 | 28,6 % |

- **LightGBM est retenu pour les deux périls**, d'après la validation.
- En test, il garde la meilleure AUC, mais **pour la sécheresse, la régression logistique capte davantage de communes touchées dans le top 10 %** (30,8 % contre 25,4 %). Ce résultat est conservé tel quel : changer de modèle après avoir vu le test reviendrait à l'utiliser pour choisir.

### Ce que disent les résultats

**1. Une année ne ressemble pas à l'autre.**

| Sécheresse | 2017 | 2018 | 2019 | 2020 | 2021 |
|---|---:|---:|---:|---:|---:|
| Communes reconnues | 6,0 % | 11,6 % | 8,3 % | 7,4 % | 0,7 % |
| AUC LightGBM | 0,88 | 0,70 | 0,72 | 0,68 | 0,80 |
| Top 10 % | 52 % | 13 % | 18 % | 18 % | 26 % |

- En 2017, les sécheresses touchent les zones habituelles : le modèle les trouve très bien.
- En 2018-2020, des sécheresses de grande ampleur touchent surtout des communes que l'historique **ne classait pas** parmi les plus exposées : seules 13 % à 18 % des communes reconnues figuraient dans le top 10 %.
- L'inondation 2024 est elle aussi difficile à prévoir (AUC 0,59), alors que c'est l'année de test où le plus de communes ont été reconnues (7,9 %).

**2. La géographie domine la sécheresse.** Latitude et longitude sont les deux variables les plus influentes (SHAP) : elles servent de substitut à la nature du sol, qui manque au modèle. C'est aussi pour cela que le modèle généralise mal quand les sécheresses se déplacent.

**3. Les probabilités ne sont pas calibrées en absolu.** Sur 2017-2021, le modèle sécheresse annonce en moyenne des probabilités bien inférieures aux fréquences observées, car la sécheresse progresse plus vite que pendant les années d'entraînement (H1). Le modèle est donc utilisé comme un **classement** (`percentile_national`), pas comme une probabilité à prendre au pied de la lettre.

### Limites et pistes

- **Exposition physique :** ajouter la carte d'exposition au retrait-gonflement des argiles (BRGM) et les zones inondables, plutôt que la latitude et la longitude. Ce sont des polygones à croiser avec les contours des communes, d'où un traitement géographique plus lourd.
- **Recalibrer** les probabilités sur les années récentes, pour les rendre utilisables en tarification.
- **Horizon pluriannuel :** prédire « au moins une reconnaissance dans les 5 ans » serait moins dépendant de la météo d'une année, et plus proche des besoins d'un assureur.

---

## Étape 3 bis — Améliorer le modèle

Trois pistes, testées dans cet ordre : l'exposition physique des sols, la calibration des probabilités, puis des horizons de prédiction à 3 et 5 ans.

### 1. Exposition aux argiles ✅

- **Hypothèse :** pour la sécheresse, la latitude et la longitude servaient de substitut à la nature du sol. La vraie information devrait faire mieux.
- **Source :** le zonage d'exposition au retrait-gonflement des argiles du BRGM (2019, 122 222 zones, 3 niveaux). Le service statistique du ministère publie des agrégats, mais par intercommunalité seulement, ce qui est trop grossier.
- **Méthode :** 200 points tirés au hasard dans chaque commune (contours Etalab 2025), puis croisés avec les zones. La part des points donne la part du territoire par niveau d'exposition. Le calcul (7 millions de points, 13 minutes) tourne une seule fois sur GitHub Actions ; le résultat (34 881 communes) est versionné comme table de référence dbt (`seeds/exposition_argiles.csv`).
- **Contrôle de vraisemblance :** le Gers (91 % de surface en exposition forte), le Lot-et-Garonne et la Haute-Garonne sont en tête, comme attendu dans le Sud-Ouest argileux. La Bretagne et la Corse sont peu exposées. Paris n'est pas couvert par la carte.
- **Résultat :** la part en exposition forte devient **la variable la plus influente** du modèle sécheresse, devant la latitude.

| Sécheresse | AUC validation sans → avec | AUC test sans → avec |
|---|---:|---:|
| 1 an | 0,906 → 0,916 | 0,738 → 0,759 |
| 3 ans | 0,902 → 0,918 | 0,722 → 0,751 |
| 5 ans | 0,910 → 0,920 | 0,778 → 0,808 |

- Pour l'inondation, l'effet est nul, ce qui est logique : ce n'est pas le bon phénomène physique. Les variables sont gardées pour la simplicité (un seul jeu de variables), sans dégrader les résultats.
- **Limite :** le zonage date de 2019 et s'appuie en partie sur des sinistres passés. Pour les années de test 2017-2018, une petite part d'information postérieure est possible. La géologie, elle, ne change pas.
- **Non fait pour l'inondation :** il n'existe pas de carte nationale unique des zones inondables en open data (les enveloppes EAIP sont publiées région par région). Les plans de prévention et atlas datés de GASPAR avaient déjà été testés sans gain.

### 2. Horizons de 3 et 5 ans

- **Cible :** au moins une reconnaissance entre l'année t et l'année t + h - 1.
- **Découpage :** une fenêtre de 5 ans démarrant en 2018 couvre 2018-2022. Pour qu'aucune année de cible ne soit partagée, l'entraînement s'arrête 5 ans avant le début de la validation, et la validation 5 ans avant le test (test unitaire dédié). Seules les fenêtres entièrement évaluables sont utilisées (sécheresse : jusqu'en 2021).

#### ❌ Une anomalie : l'inondation à 5 ans sous le hasard

- **Observation :** au premier essai, l'AUC de validation de l'inondation à 5 ans valait **0,47**, pire que le hasard, alors que l'historique seul faisait 0,61.
- **Diagnostic :** par année de départ, l'historique est un bon prédicteur (AUC 0,6 à 0,7)… sauf pour les fenêtres qui contiennent **1999**, où il s'inverse (AUC 0,37 à 0,43).
- **Cause :** en 1999, **77,9 %** des communes ont été reconnues en inondation, contre 1 à 16 % les autres années (tempêtes de décembre). Les communes jamais touchées l'ont été aussi. Les fenêtres de 1995 à 1999 contiennent toutes cette année, avec plus de 80 % de communes « touchées », et elles pèsent lourd dans l'entraînement à 5 ans (1992-2007). Le modèle y apprenait « moins une commune a d'historique, plus elle est à risque ».
- **Vérification (validation) :** en entraînant à partir des fenêtres de 2000, l'AUC de validation passe de 0,46 à 0,63. Avec la règle finale ci-dessous, qui ne retire que les fenêtres contenant 1999, elle vaut 0,625.
- 📌 **Décision :** une règle explicite plutôt qu'un cas codé à la main. Une année où plus de 50 % des communes sont reconnues est « exceptionnelle », et les fenêtres d'entraînement qui la contiennent sont écartées. Seule 1999 (inondation) est concernée. La règle améliore aussi l'horizon d'un an (validation 0,746 → 0,790).

#### Résultats

| Péril | Horizon | Communes touchées (test) | AUC validation | AUC test | Historique (test) | Régression logistique (test) |
|---|---|---:|---:|---:|---:|---:|
| Inondation | 1 an | 5,2 % | 0,790 | 0,657 | 0,644 | 0,659 |
| | 3 ans | 12,2 % | 0,642 | 0,676 | 0,658 | 0,661 |
| | 5 ans | 19,3 % | 0,625 | **0,694** | 0,666 | 0,640 |
| Sécheresse | 1 an | 6,8 % | 0,916 | 0,759 | 0,710 | 0,753 |
| | 3 ans | 18,1 % | 0,918 | 0,751 | 0,663 | 0,715 |
| | 5 ans | 23,7 % | 0,920 | **0,808** | 0,697 | 0,776 |

- **Plus l'horizon est long, mieux le modèle classe** : le hasard météo d'une année se lisse sur plusieurs années.
- LightGBM bat l'historique à tous les horizons, et la régression logistique à 3 et 5 ans. À 1 an pour l'inondation, les trois approches se valent.

### 3. Calibration des probabilités ❌ (résultat négatif, conservé)

- **Méthode :** recalage de Platt (deux paramètres sur le score du modèle) appris sur les années de validation, puis mesuré en test. Le classement des communes ne change pas.
- **Résultat :**

| Péril | Horizon | Prédit avant → après recalage | Observé | Score de Brier avant → après |
|---|---|---:|---:|---:|
| Inondation | 1 an | 5,7 % → 2,9 % | 5,2 % | 0,0492 → 0,0499 |
| | 3 ans | 14,4 % → 14,8 % | 12,2 % | 0,1034 → 0,1035 |
| | 5 ans | 24,7 % → 20,8 % | 19,3 % | 0,1485 → 0,1452 |
| Sécheresse | 1 an | 1,6 % → 2,2 % | 6,8 % | 0,0650 → 0,0652 |
| | 3 ans | 5,5 % → 2,2 % | 18,1 % | 0,1595 → 0,1697 |
| | 5 ans | 8,9 % → 8,3 % | 23,7 % | 0,1790 → 0,1829 |

- **Le recalage n'aide qu'à 5 ans pour l'inondation.** Ailleurs, il est neutre ou dégrade la calibration.
- **Pourquoi :**
  - le taux de communes reconnues varie d'un facteur 10 d'une année à l'autre selon la météo (sécheresse : 0,7 % en 2021, 11,6 % en 2018). Recaler sur deux années revient à recaler sur deux tirages : l'inondation 2019-2020 (2,6 % et 3,4 %) a tiré les probabilités vers le bas, juste avant des années plus fortes ;
  - la sécheresse suit en plus une **tendance de fond** (H1) : les années de recalage sont toujours en retard sur le niveau actuel.
- 📌 **Décision :** le recalage reste dans le pipeline de production, appris sur les fenêtres les plus récentes, mais les probabilités sont présentées comme **indicatives**. Le résultat fiable, c'est le **classement** (`percentile_national`). Changer de méthode maintenant, après avoir vu le test, reviendrait à l'utiliser pour choisir.
- **Piste :** recaler sur une période plus longue (5 à 10 ans) pour lisser la météo, et modéliser explicitement la tendance de la sécheresse.

### Bilan

| | Avant | Après |
|---|---|---|
| Sécheresse, meilleur horizon | 0,75 (1 an) | **0,81 (5 ans)** |
| Inondation, meilleur horizon | 0,67 (1 an) | **0,69 (5 ans)** |
| Variable n° 1, sécheresse | latitude | **exposition forte aux argiles** |

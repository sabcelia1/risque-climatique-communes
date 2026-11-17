# 🌧️ Risque climatique par commune : prédire les catastrophes naturelles

> Prévoir quelles communes françaises risquent une catastrophe naturelle reconnue (inondation, sécheresse, mouvement de terrain…), expliquer pourquoi, et produire des fiches de risque lisibles par un assureur grâce à l'IA générative.

**Statut :** 🚧 en cours — étape 1/5 (ingestion et qualité)

---

## 🎯 Problématique

En France, le régime des catastrophes naturelles (CatNat) indemnise les sinistrés lorsqu'un arrêté interministériel reconnaît l'état de catastrophe naturelle d'une commune. Pour un assureur, anticiper **où** ces reconnaissances vont se produire permet d'ajuster la tarification, la prévention et les provisions.

Ce projet construit, à partir de données publiques :

1. un **pipeline de données** fiable et automatisé ;
2. un **modèle de machine learning** qui estime la probabilité d'une reconnaissance CatNat par commune, avec des **explications** pour chaque prédiction ;
3. une **IA générative** qui rédige des fiches de risque par commune, **ancrées dans les données** et contrôlées automatiquement.

## 🗺️ Feuille de route

- [ ] **Étape 1** — Ingestion et qualité : base GASPAR, référentiel des communes, tests automatiques
- [ ] **Étape 2** — Data engineering : modèles dbt dans BigQuery, mise à jour automatique (GitHub Actions)
- [ ] **Étape 3** — Machine learning : prédiction du risque, validation temporelle, explicabilité (SHAP)
- [ ] **Étape 4** — IA générative : fiches de risque contrôlées, assistant en langage naturel
- [ ] **Étape 5** — Application Streamlit en ligne, documentation

## 📁 Sources de données

| Source | Producteur | Contenu | Licence |
|---|---|---|---|
| [Base GASPAR](https://www.data.gouv.fr/datasets/base-nationale-de-gestion-assistee-des-procedures-administratives-relatives-aux-risques-gaspar) | Ministère de la Transition écologique | Arrêtés de catastrophe naturelle par commune depuis 1982 | Licence Ouverte |
| [API Découpage administratif](https://geo.api.gouv.fr/decoupage-administratif) | Etalab | Communes, population, superficie, coordonnées | Licence Ouverte |
| [API Géorisques](https://www.data.gouv.fr/dataservices/api-georisques) *(étape 3)* | Ministère de la Transition écologique, BRGM | Exposition aux inondations et aux argiles | Licence Ouverte |

## 🧹 Qualité des données

La base GASPAR présente plusieurs défauts signalés publiquement par ses utilisateurs ([discussions data.gouv.fr](https://www.data.gouv.fr/datasets/base-nationale-de-gestion-assistee-des-procedures-administratives-relatives-aux-risques-gaspar/discussions)). Le nettoyage (`src/clean.py`) les traite explicitement, et chaque contrôle est chiffré dans [`reports/qualite_donnees.md`](reports/qualite_donnees.md) :

| Défaut connu | Traitement |
|---|---|
| Fichier publié tantôt en CSV, tantôt en ZIP aux noms variables (`catnat_gaspar.csv.csv`…) | Détection automatique, extraction de la table CatNat |
| Colonnes renommées entre versions | Noms connus (`SYNONYMES`), puis détection par mots-clés (`MOTS_CLES`) ; colonnes trouvées listées dans le rapport |
| Lignes répétées 2 ou 3 fois | Dédoublonnage, nombre de lignes supprimées tracé |
| Accents mal encodés (« SÃ©cheresse ») | Réparation automatique |
| Dates incohérentes (fin avant début, événements de plus d'un an hors sécheresse) | Mises à vide ou signalées, jamais supprimées en silence |
| Codes de communes fusionnées depuis | Signalés, rattachement aux communes actuelles à l'étape 2 |
| Libellés de périls très détaillés | Regroupement en 6 familles (inondation, sécheresse, mouvement de terrain, vent/tempête, séisme, autre) |

Les règles de nettoyage sont couvertes par des **tests unitaires** (`tests/`), exécutés avant chaque traitement.

## 🚀 Reproduire le projet

**Windows :** double-cliquez sur `lancer.bat` (environnement, tests, téléchargement, nettoyage, exploration).

**Manuellement :**

```bash
git clone https://github.com/sabcelia1/risque-climatique-communes.git
cd risque-climatique-communes
python -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate
pip install -r requirements.txt

python -m pytest -q                # tests
python src/ingest.py               # téléchargement
python src/clean.py                # nettoyage + rapport qualité
python src/explorer.py             # chiffres clés -> reports/exploration.md
```

## 🛠️ Stack

Python (pandas, pytest) · SQL · Google BigQuery · dbt · GitHub Actions · scikit-learn · SHAP · Gemini · Streamlit

---

👤 **Célia Monga** — Ingénieure Data & IA · [Projet précédent : recharge électrique en France](https://github.com/sabcelia1/recharge-ve-france) · [LinkedIn](https://www.linkedin.com/in/c%C3%A9lia-monga-a48b48242/)

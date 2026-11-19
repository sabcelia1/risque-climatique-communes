# Guide : connecter le projet à Google BigQuery, sans clé

Ce guide se fait **une seule fois** (environ 10 minutes). Sans lui, le pipeline fonctionne déjà en local avec DuckDB ; avec lui, les tables sont aussi construites dans BigQuery, chaque semaine, automatiquement.

## Pourquoi « sans clé » ?

La méthode classique consiste à télécharger une clé de compte de service (un fichier JSON) et à la confier à GitHub. Mais une clé est un mot de passe permanent : si elle fuit, n'importe qui peut l'utiliser. Google bloque d'ailleurs leur création par défaut dans les organisations récentes (règle `iam.disableServiceAccountKeyCreation`), ce qui est le cas de ce projet.

Le projet utilise donc la **fédération d'identité de charge de travail** (*Workload Identity Federation*) :

1. À chaque exécution, GitHub délivre au pipeline un **jeton signé et valable quelques minutes**, qui atteste « je suis le dépôt `sabcelia1/risque-climatique-communes` ».
2. Google vérifie ce jeton et, s'il provient bien de **ce** dépôt, accorde un accès temporaire au compte de service `pipeline-risque`.
3. Ce compte n'a que deux droits : écrire des tables BigQuery et lancer des requêtes.

**Il n'existe donc aucun secret à stocker, à transmettre ou à faire tourner.** Les valeurs écrites dans `.github/workflows/pipeline.yml` (identifiant du projet, nom du compte de service, fournisseur d'identité) sont des identifiants publics, pas des mots de passe.

---

## 1. Lancer le script de configuration dans Cloud Shell

1. Ouvrez [console.cloud.google.com](https://console.cloud.google.com) et sélectionnez le projet **risques-climatiuqes-communes**.
2. En haut à droite, cliquez sur l'icône **Activer Cloud Shell** (`>_`). Un terminal s'ouvre en bas de la page (cliquez sur **Autoriser** si on vous le demande).
3. Copiez **tout** le contenu de [`scripts/configurer_gcp.sh`](../scripts/configurer_gcp.sh), collez-le dans le terminal et appuyez sur Entrée.
4. Le script crée le compte de service (ou garde celui qui existe), lui donne ses deux rôles BigQuery, puis crée la fédération d'identité limitée à ce dépôt. Il se termine par une ligne :
   ```
   GCP_WIF_PROVIDER: projects/123456789/locations/global/workloadIdentityPools/github/providers/github-repo
   ```

Le script peut être relancé sans risque : ce qui existe déjà est conservé.

## 2. Renseigner le fournisseur dans le workflow

Dans `.github/workflows/pipeline.yml`, la ligne `GCP_WIF_PROVIDER` reçoit la valeur affichée à la fin du script (déjà fait pour ce dépôt). Cette valeur n’est pas secrète.

## 3. Lancer et vérifier

Onglet **Actions** du dépôt → **Pipeline de données** → **Run workflow**. Les étapes « Connexion à Google Cloud », « Chargement dans BigQuery » et « Modèles dbt et tests (BigQuery) » ne sont plus ignorées, et la console BigQuery affiche les jeux de données `risque_raw` et `risque`.

Le pipeline tourne ensuite **chaque lundi**. Le **bac à sable BigQuery** (sans carte bancaire) suffit : il supprime les tables au bout de 60 jours, mais la mise à jour hebdomadaire les recrée.

---

## Optionnel : BigQuery depuis votre ordinateur

Ce n'est pas nécessaire : en local, `lancer.bat` construit les mêmes tables dans DuckDB. Pour interroger BigQuery depuis votre poste :

1. Installez [Google Cloud CLI](https://cloud.google.com/sdk/docs/install).
2. Dans un terminal : `gcloud auth application-default login`, puis connectez-vous dans le navigateur.
3. Relancez `lancer.bat` : les étapes 5 et 6 (chargement et dbt dans BigQuery) s'exécutent avec votre propre compte.

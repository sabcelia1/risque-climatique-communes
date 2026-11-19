# Guide : connecter le projet à Google BigQuery

Ce guide se fait **une seule fois** (environ 15 minutes). Sans lui, le pipeline fonctionne déjà en local avec DuckDB ; avec lui, les tables sont aussi construites dans BigQuery, chaque semaine, automatiquement.

> ⚠️ **Sécurité : la clé du compte de service est un mot de passe.**
> - Ne l'envoyez **à personne** (ni par mail, ni dans une conversation, ni à une IA).
> - Ne la déposez **jamais** sur GitHub : le dossier `secrets/` est exclu de Git, gardez-la uniquement là.
> - Elle ne va qu'à deux endroits : `secrets/cle-gcp.json` sur votre ordinateur, et le secret GitHub `GCP_SA_KEY`, que vous collez vous-même.
> - Si elle fuit par erreur : console Google Cloud → compte de service → onglet **Clés** → supprimez-la, puis créez-en une nouvelle.

---

## 1. Choisir le projet Google Cloud

1. Ouvrez [console.cloud.google.com](https://console.cloud.google.com).
2. En haut, sélectionnez le projet utilisé pour [recharge-ve-france](https://github.com/sabcelia1/recharge-ve-france) : on peut le réutiliser, les tables de ce projet vont dans des jeux de données à part (`risque_raw` et `risque`).
   *Ou* créez un nouveau projet (« Nouveau projet », nom : `risque-climatique`).
3. Notez l'**ID du projet** (sous le nom, par exemple `risque-climatique-123456`).

Le **bac à sable BigQuery** (sans carte bancaire) suffit. Il supprime les tables au bout de 60 jours, mais la mise à jour hebdomadaire les recrée.

## 2. Créer un compte de service

Un compte de service est un « utilisateur robot » qui n'a que les droits nécessaires au pipeline.

1. Menu ☰ → **IAM et administration** → **Comptes de service** → **Créer un compte de service**.
2. Nom : `pipeline-risque`, puis **Créer et continuer**.
3. Ajoutez deux rôles :
   - **Éditeur de données BigQuery** (`BigQuery Data Editor`) : créer et remplacer des tables ;
   - **Utilisateur de tâche BigQuery** (`BigQuery Job User`) : lancer des requêtes.
4. **Continuer**, puis **OK**.

## 3. Créer la clé et la ranger

1. Cliquez sur le compte `pipeline-risque` → onglet **Clés** → **Ajouter une clé** → **Créer une clé** → **JSON** → **Créer**. Un fichier `.json` se télécharge.
2. Dans le dossier du projet, créez un dossier **`secrets`**, et déplacez-y le fichier en le renommant **`cle-gcp.json`** :
   ```
   risque-climatique-communes\
   └── secrets\
       └── cle-gcp.json
   ```
3. Supprimez la copie restée dans *Téléchargements*.

> Si la console refuse de créer une clé (« la création de clés est désactivée par une règle d'administration »), votre compte dépend d'une organisation qui l'interdit : dites-le-moi, on passera par une autre méthode d'authentification (fédération d'identité GitHub, sans clé).

## 4. Vérifier en local

Double-cliquez sur `lancer.bat`. Les étapes 5 et 6 apparaissent :

```
=== Etape 5 : chargement dans BigQuery
  <projet>.risque_raw.communes : 34 9xx lignes
  <projet>.risque_raw.catnat : 247 xxx lignes
=== Etape 6 : modeles dbt et tests dans BigQuery
...
Done. PASS=25 WARN=0 ERROR=0
```

Dans la console BigQuery, les jeux de données `risque_raw` et `risque` sont apparus.

## 5. Activer la mise à jour automatique (GitHub Actions)

1. Ouvrez `secrets\cle-gcp.json` avec le Bloc-notes, **sélectionnez tout** (Ctrl + A) et copiez (Ctrl + C).
2. Sur GitHub, dans le dépôt : **Settings** → **Secrets and variables** → **Actions** → **New repository secret**.
3. Name : **`GCP_SA_KEY`** ; Secret : collez le contenu ; **Add secret**. Fermez le Bloc-notes sans rien enregistrer.
4. Onglet **Actions** → **Pipeline de données** → **Run workflow**.

Le pipeline tourne ensuite **chaque lundi** : téléchargement de la dernière base GASPAR, nettoyage, tests, chargement dans BigQuery, modèles dbt et leurs tests. Une coche verte dans l'onglet Actions signifie que tout est passé ; les rapports de qualité sont téléchargeables dans le résumé de chaque exécution (« Artifacts »).

GitHub masque automatiquement le secret dans les journaux d'exécution, et personne (pas même vous) ne peut le relire après l'avoir enregistré.

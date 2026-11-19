# Guide : connecter Gemini (IA générative)

L'étape 4 utilise l'API Gemini de Google, dans son **niveau gratuit** (modèles « Flash »). Ce guide se fait une seule fois, en 5 minutes.

> ⚠️ **La clé API est un mot de passe.** Ne l'envoyez à personne (ni par mail, ni dans une conversation, ni à une IA), et ne la déposez jamais sur GitHub. Elle ne va qu'à deux endroits : le secret GitHub `GEMINI_API_KEY`, et éventuellement le fichier `secrets/gemini.env` sur votre ordinateur (dossier exclu de Git). En cas de fuite : supprimez-la dans Google AI Studio et créez-en une autre.
>
> Au niveau gratuit, Google peut utiliser les requêtes pour améliorer ses produits. Ce projet n'envoie que des données publiques (open data), jamais de données personnelles.

## 1. Créer la clé

1. Ouvrez [Google AI Studio](https://aistudio.google.com/apikey) et connectez-vous avec votre compte Google.
2. **Create API key** (Créer une clé API). Si on vous demande un projet, choisissez `risques-climatiuqes-communes` ou laissez AI Studio en créer un.
3. Copiez la clé affichée.

## 2. La confier à GitHub

1. Dépôt GitHub → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**.
2. Name : **`GEMINI_API_KEY`** ; Secret : collez la clé ; **Add secret**.

## 3. Lancer l'IA générative

Onglet **Actions** → **IA générative** → **Run workflow**. En une dizaine de minutes, le workflow :

- rédige des fiches de risque d'exemple → [`docs/fiches_exemples.md`](fiches_exemples.md) ;
- évalue l'assistant SQL sur des questions de référence et des tentatives d'attaque → [`docs/evaluation_assistant.md`](evaluation_assistant.md) ;

puis enregistre ces deux fichiers dans le dépôt.

## Optionnel : sur votre ordinateur

Créez le fichier `secrets\gemini.env` contenant une seule ligne :

```
GEMINI_API_KEY=votre_clé
```

Puis, dans une console ouverte dans le dossier du projet :

```
.venv\Scripts\python.exe src\fiches.py 32013 06088
.venv\Scripts\python.exe src\assistant_sql.py "Quelles communes du Gers sont les plus exposées aux argiles ?"
```

Le modèle utilisé peut être imposé avec la variable `GEMINI_MODEL` ; par défaut, le premier modèle Flash gratuit disponible est choisi.

# Guide : mettre l'application en ligne (Streamlit Community Cloud)

L'application est hébergée gratuitement par Streamlit Community Cloud, directement depuis ce dépôt GitHub. Ce guide se fait une seule fois (10 minutes).

## Comment l'application obtient ses données

L'application ne recalcule rien. Chaque semaine, le workflow **Pipeline de données** produit un export compact (`app.duckdb`, quelques Mo) et le publie dans la Release GitHub **`donnees-app`** du dépôt. Au démarrage, l'application télécharge cet export, puis le recharge une fois par jour.

## 1. Déployer

1. Ouvrez [share.streamlit.io](https://share.streamlit.io) et connectez-vous avec votre compte **GitHub**.
2. **Create app** → **Deploy a public app from GitHub**.
3. Renseignez :
   - Repository : `sabcelia1/risque-climatique-communes`
   - Branch : `main`
   - Main file path : `app/streamlit_app.py`
   - App URL : par exemple `risque-catnat` (l'adresse sera `https://risque-catnat.streamlit.app`)
4. **Advanced settings** → Python **3.12**, puis dans **Secrets**, collez :
   ```toml
   GEMINI_API_KEY = "votre_clé_gemini"
   ```
   C'est le seul endroit, avec le secret GitHub, où la clé est enregistrée. Elle n'apparaît jamais dans le code. Sans elle, l'application fonctionne, mais sans fiches ni assistant.
5. **Deploy**. Le premier démarrage prend quelques minutes (installation des librairies listées dans `app/requirements.txt`).

## 2. Protection du quota Gemini

L'application étant publique, chaque visiteur est limité à **5 fiches** et **10 questions** par visite, et les réponses sont mises en cache (une même question ne consomme le quota qu'une fois). Les fiches d'exemple, déjà générées, s'affichent sans appel à Gemini.

## 3. En local

Après avoir lancé `lancer.bat` une fois, double-cliquez sur **`lancer_application.bat`** : l'application s'ouvre dans le navigateur (http://localhost:8501). Pour activer Gemini en local, voir [`guide_gemini.md`](guide_gemini.md).

## En cas de problème

- **« Données indisponibles »** : l'export n'a pas encore été publié. Lancez le workflow **Pipeline de données** depuis l'onglet Actions.
- **L'application s'est endormie** : Community Cloud met en veille les applications inutilisées pendant plusieurs jours ; un clic sur « Yes, get this app back up » la relance en une minute.

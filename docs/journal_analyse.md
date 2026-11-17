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

### Hypothèses à tester sur les données réelles

| # | Hypothèse | Statut |
|---|---|---|
| H1 | La part des reconnaissances « sécheresse » augmente nettement depuis 2015 | 🔍 à vérifier |
| H2 | Les reconnaissances sont très concentrées : une minorité de communes en cumule la majorité | 🔍 à vérifier |
| H3 | Une part non négligeable des codes communes correspond à des communes fusionnées depuis | 🔍 à vérifier |

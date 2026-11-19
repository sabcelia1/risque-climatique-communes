"""Page « Méthode » : d'où viennent les chiffres, ce que vaut le modèle, ses limites."""

import pandas as pd
import streamlit as st

import donnees as d
import style

GITHUB = f"https://github.com/{d.DEPOT}"


def page():
    style.bandeau("Méthode et limites", "D'où viennent les chiffres, ce que vaut le modèle, "
                  "et ce qu'il ne sait pas faire.", surtitre="Transparence")
    st.markdown(f"""
**Les données.** Base [GASPAR](https://www.data.gouv.fr/datasets/base-nationale-de-gestion-assistee-des-procedures-administratives-relatives-aux-risques-gaspar)
des arrêtés de catastrophe naturelle (ministère de la Transition écologique, depuis 1982), référentiel des
communes (Etalab), zonage d'exposition au retrait-gonflement des argiles (BRGM, 2019). Le pipeline est mis à
jour chaque semaine par GitHub Actions : nettoyage contrôlé, modèles dbt testés dans BigQuery.

**Le modèle.** Pour chaque commune et chaque péril, un modèle LightGBM estime le risque d'au moins une
reconnaissance dans 1, 3 ou 5 ans, à partir de ce qui était connu au 1er janvier (seuls les arrêtés déjà
signés sont comptés). Il est évalué sur des années jamais vues pendant l'entraînement.
""")
    m = d.json_publie("metriques_modele.json").get("metriques", {})
    if m:
        lignes = []
        for peril, par_h in m.items():
            for h, x in par_h.items():
                t = x["resultats"]["test"]
                lignes.append({"Péril": {"secheresse": "Sécheresse", "inondation": "Inondation"}[peril],
                               "Horizon": f"{h} an{'s' if int(h) > 1 else ''}",
                               "AUC du modèle": f"{t['LightGBM']['auc_moyen_par_annee']:.2f}".replace(".", ","),
                               "AUC de l'historique seul":
                                   f"{t['Historique de la commune']['auc_moyen_par_annee']:.2f}".replace(".", ",")})
        st.dataframe(pd.DataFrame(lignes), hide_index=True, width="stretch")
        st.caption("AUC de test, par année : 0,5 = hasard, 1 = classement parfait des communes touchées.")
    st.markdown(f"""
**Les limites.**
- Une reconnaissance dépend d'abord de la météo de l'année, inconnue à l'avance : le modèle **classe** bien les
  communes, mais ses probabilités ne sont qu'indicatives.
- La base ne contient que les reconnaissances **accordées** : le modèle prédit une reconnaissance, pas un sinistre.
- Les fiches rédigées par l'IA ne contiennent aucun chiffre absent des données, mais l'attribution d'un chiffre à
  un facteur peut être imparfaite : le tableau des facteurs fait foi.

**Pour aller plus loin :** [le code et la documentation]({GITHUB}) ·
[le journal d'analyse]({GITHUB}/blob/main/docs/journal_analyse.md) (hypothèses, erreurs corrigées, choix) ·
[l'évaluation de l'assistant]({GITHUB}/blob/main/docs/evaluation_assistant.md)

Projet réalisé par **Célia Monga**, ingénieure Data & IA —
[LinkedIn](https://www.linkedin.com/in/c%C3%A9lia-monga-a48b48242/) · [GitHub](https://github.com/sabcelia1)
""")

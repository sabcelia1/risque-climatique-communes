"""Page « Une commune » : classement, facteurs, historique et fiche rédigée par Gemini."""

import math

import altair as alt
import pandas as pd
import streamlit as st

import donnees as d

PERILS = {"secheresse": "Sécheresse", "inondation": "Inondation"}
COULEURS = {"inondation": "#1f6f8b", "secheresse": "#d08c2b", "mouvement_terrain": "#7a6a58",
            "vent_tempete": "#8fa3ad", "seisme": "#a14a3b", "autre": "#c9c9c9"}
NOMS_PERILS = {"inondation": "Inondation", "secheresse": "Sécheresse", "mouvement_terrain": "Mouvement de terrain",
               "vent_tempete": "Vent, tempête", "seisme": "Séisme", "autre": "Autre"}
COMMUNE_PAR_DEFAUT = "32013"       # Auch


def top(percentile: float) -> str:
    haut = max(1, math.ceil(round((1 - percentile) * 100, 6)))
    return f"Top {haut} %" if haut <= 50 else "Moitié basse"


def choisir_commune() -> pd.Series:
    liste = d.communes()
    etiquettes = liste["nom_commune"] + " (" + liste["code_departement"] + ")"
    code = st.query_params.get("commune", COMMUNE_PAR_DEFAUT)
    index = int(liste.index[liste["code_insee"] == code][0]) if (liste["code_insee"] == code).any() else 0
    choix = st.selectbox("Commune", range(len(liste)), index=index, format_func=lambda i: etiquettes.iloc[i],
                         help="Tapez le début du nom pour chercher parmi les 34 969 communes.")
    commune = liste.iloc[choix]
    st.query_params["commune"] = commune["code_insee"]
    return commune


def page():
    st.title("Risque de catastrophe naturelle par commune")
    st.caption("Reconnaissances CatNat depuis 1982, exposition des sols aux argiles et risque prédit à 1, 3 et 5 ans.")
    c = choisir_commune()
    code = c["code_insee"]
    info = d.requete("select * from communes where code_insee = ?", [code]).iloc[0]
    preds = d.requete("select * from predictions_facteurs where code_insee = ?", [code])
    evts = d.requete("select annee, famille_peril, libelle_peril, date_debut, date_arrete "
                     "from evenements where code_insee = ? order by date_debut desc", [code])

    st.subheader(f"{c['nom_commune']} · {c['nom_departement']} ({c['code_departement']})")
    st.caption(f"{c['nom_region']} · {int(info['population']):,} habitants · ".replace(",", "\u202f")
               + f"{info['surface_km2']:.1f} km²".replace(".", ",")
               if pd.notna(info["population"]) else c["nom_region"])

    k1, k2, k3, k4 = st.columns(4)
    for col, peril in ((k1, "secheresse"), (k2, "inondation")):
        p5 = preds[(preds["famille_peril"] == peril) & (preds["horizon_ans"] == 5)]
        col.metric(f"{PERILS[peril]}, 5 ans", top(p5["percentile_national"].iloc[0]) if len(p5) else "—",
                   help="Rang national de la commune : « Top 3 % » = parmi les 3 % de communes les plus exposées.")
    k3.metric("Reconnaissances depuis 1982", int(info["nb_evenements_total"]))
    k4.metric("Sol argileux, exposition forte",
              "Non cartographié" if pd.isna(info["part_argile_fort"]) else f"{round(100 * info['part_argile_fort'])} %",
              help="Part du territoire en exposition forte au retrait-gonflement des argiles (BRGM, 2019).")

    gauche, droite = st.columns([1.1, 1])
    with gauche:
        st.markdown("##### Risque prédit")
        tableau = preds.pivot_table(index="famille_peril", columns="horizon_ans", values="percentile_national")
        tableau = tableau.rename(index=PERILS, columns=lambda h: f"{h} an{'s' if h > 1 else ''}").map(top)
        tableau.index.name, tableau.columns.name = "Péril", None
        st.dataframe(tableau, width="stretch")
        st.caption("Classement national (le résultat fiable du modèle). Les probabilités brutes sont indicatives : "
                   "voir la page Méthode.")
        peril = st.radio("Facteurs explicatifs", list(PERILS), format_func=PERILS.get, horizontal=True)
        ligne = preds[(preds["famille_peril"] == peril) & (preds["horizon_ans"] == 5)]
        if len(ligne):
            ligne = ligne.iloc[0]
            from fiches import LIBELLES_FACTEURS, valeur_facteur
            for k in (1, 2, 3):
                nom = ligne[f"facteur_{k}"]
                libelle = LIBELLES_FACTEURS.get(nom, (nom,))[0]
                valeur = valeur_facteur(nom, ligne[f"valeur_{k}"])
                sens = "▲ augmente" if ligne[f"contribution_{k}"] > 0 else "▼ diminue"
                st.markdown(f"{sens} le risque — **{libelle}**{' : ' + valeur if valeur else ''}")
            st.caption("Les 3 variables qui pèsent le plus dans la prédiction à 5 ans (valeurs SHAP).")
    with droite:
        st.markdown("##### Reconnaissances par année")
        if evts.empty:
            st.info("Aucune reconnaissance CatNat depuis 1982.")
        else:
            par_an = evts.groupby(["annee", "famille_peril"]).size().rename("n").reset_index()
            par_an["Péril"] = par_an["famille_peril"].map(NOMS_PERILS)
            graphique = alt.Chart(par_an).mark_bar(size=7).encode(
                x=alt.X("annee:Q", title=None, scale=alt.Scale(domain=[1981, 2026]),
                        axis=alt.Axis(format="d", values=list(range(1985, 2026, 5)))),
                y=alt.Y("n:Q", title="Reconnaissances", axis=alt.Axis(tickMinStep=1)),
                color=alt.Color("Péril:N", scale=alt.Scale(domain=[NOMS_PERILS[k] for k in COULEURS],
                                                           range=list(COULEURS.values())),
                                legend=alt.Legend(orient="bottom", title=None, columns=3)),
                tooltip=["annee", "Péril", "n"]).properties(height=260)
            st.altair_chart(graphique, width="stretch")

    st.divider()
    fiche_gemini(c, code)

    with st.expander(f"Les {min(len(evts), 20)} dernières reconnaissances"):
        st.dataframe(evts.head(20).rename(columns={"annee": "Année", "libelle_peril": "Péril",
                                                   "date_debut": "Début", "date_arrete": "Arrêté"})
                     [["Année", "Péril", "Début", "Arrêté"]], hide_index=True, width="stretch")


def fiche_gemini(c, code):
    from fiches import dossier, en_markdown, rediger

    st.markdown("##### Fiche de risque rédigée par l'IA")
    st.caption("Gemini rédige à partir d'un dossier factuel construit par le pipeline. Chaque nombre écrit est "
               "vérifié automatiquement : un nombre absent des données entraîne un second essai, puis le rejet.")
    cle = f"fiche_{code}"
    exemple = d.json_publie("fiches_exemples.json").get(c["nom_commune"])
    if exemple and exemple["faits"].get("departement", "").endswith(f"({c['code_departement']})"):
        st.session_state.setdefault(cle, exemple)
    if cle not in st.session_state:
        if not d.cle_gemini_disponible():
            st.info("La rédaction par Gemini n'est pas activée sur cette installation.")
            return
        if st.button("✍️ Rédiger la fiche avec Gemini", type="primary"):
            if not d.compteur("nb_fiches", d.LIMITE_FICHES):
                st.warning(f"Limite de {d.LIMITE_FICHES} fiches par visite atteinte (quota gratuit de Gemini).")
                return
            with st.spinner("Rédaction et vérification des chiffres… (jusqu'à une minute si Gemini est saturé)"):
                try:
                    st.session_state[cle] = rediger(d.gemini(), dossier(d.base().cursor(), code))
                except Exception as e:                   # quota, réseau
                    st.error(f"Gemini est indisponible pour le moment ({type(e).__name__}). Réessayez plus tard.")
                    return
    if cle in st.session_state:
        r = st.session_state[cle]
        with st.container(border=True):
            st.markdown(en_markdown(r).replace("### ", "#### "))
        with st.expander("Dossier factuel transmis à Gemini"):
            st.json(r["faits"])

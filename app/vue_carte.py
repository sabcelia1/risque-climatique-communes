"""Page « Carte » : le risque prédit de toutes les communes de France métropolitaine."""

import pydeck as pdk
import streamlit as st

import donnees as d
import style
from vue_commune import PERILS, top

# Classes de risque (rang national), du plus exposé au moins exposé : couleurs de la légende
CLASSES = [
    (0.99, "Top 1 %", [122, 15, 46]),
    (0.95, "Top 5 %", [198, 42, 42]),
    (0.90, "Top 10 %", [232, 98, 44]),
    (0.75, "Top 25 %", [249, 165, 74]),
    (0.50, "Top 50 %", [253, 211, 138]),
    (0.00, "Moitié basse", [226, 221, 208]),
]


def couleur(p: float) -> list[int]:
    for seuil, _, rgb in CLASSES:
        if p >= seuil:
            return rgb + ([235] if seuil >= 0.5 else [150])
    return CLASSES[-1][2] + [150]


@st.cache_data(ttl=24 * 3600)
def points(peril: str, horizon: int):
    df = d.requete("""select c.code_insee, c.nom_commune, c.nom_departement, c.latitude, c.longitude,
                             p.percentile_national
                      from predictions p join communes c using (code_insee)
                      where p.famille_peril = ? and p.horizon_ans = ? and c.latitude is not null
                        and c.code_departement not like '97%'""", [peril, horizon])
    df["couleur"] = df["percentile_national"].map(couleur)
    df["rang"] = df["percentile_national"].map(top)
    return df


def page():
    style.bandeau("Carte du risque prédit", "Chaque point est une commune, coloré selon son rang national : "
                  "les plus exposées en rouge sombre. Survolez un point pour voir la commune.")
    g, m = st.columns(2)
    peril = g.radio("Péril", list(PERILS), format_func=PERILS.get, horizontal=True)
    horizon = m.radio("Horizon", [1, 3, 5], index=2, format_func=lambda h: f"{h} an{'s' if h > 1 else ''}",
                      horizontal=True)
    df = points(peril, horizon)
    style.legende("Rang national", [(lib, rgb) for _, lib, rgb in CLASSES])
    couche = pdk.Layer("ScatterplotLayer", df, get_position=["longitude", "latitude"], get_fill_color="couleur",
                       get_radius=1000, radius_min_pixels=1.4, radius_max_pixels=7, pickable=True)
    vue = pdk.ViewState(latitude=46.6, longitude=2.4, zoom=4.6)
    st.pydeck_chart(pdk.Deck(layers=[couche], initial_view_state=vue, map_style="light",
                             tooltip={"text": "{nom_commune} ({nom_departement})\n{rang}"}), height=560)
    st.caption("« Top 5 % » : parmi les 5 % de communes les plus exposées de France pour ce péril et cet horizon.")
    st.markdown(f"##### Les 20 communes les plus exposées — {PERILS[peril].lower()}, {horizon} an{'s' if horizon > 1 else ''}")
    tete = df.sort_values("percentile_national", ascending=False).head(20)
    st.dataframe(tete[["nom_commune", "nom_departement", "rang"]].rename(
        columns={"nom_commune": "Commune", "nom_departement": "Département", "rang": "Classement"}),
        hide_index=True, width="stretch")

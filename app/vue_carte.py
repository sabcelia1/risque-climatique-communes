"""Page « Carte » : le risque prédit de toutes les communes de France métropolitaine."""

import pydeck as pdk
import streamlit as st

import donnees as d
from vue_commune import PERILS, top

# Dégradé du jaune pâle (faible) au rouge sombre (communes les plus exposées)
PALETTE = [(255, 237, 160), (254, 178, 76), (240, 59, 32), (128, 0, 38)]


def couleur(p: float) -> list[int]:
    p = min(max(p, 0), 1) ** 3                       # contraste sur le haut du classement
    i = min(int(p * (len(PALETTE) - 1)), len(PALETTE) - 2)
    t = p * (len(PALETTE) - 1) - i
    return [int(a + (b - a) * t) for a, b in zip(PALETTE[i], PALETTE[i + 1])] + [200]


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
    st.title("Carte du risque prédit")
    g, m = st.columns(2)
    peril = g.radio("Péril", list(PERILS), format_func=PERILS.get, horizontal=True)
    horizon = m.radio("Horizon", [1, 3, 5], index=2, format_func=lambda h: f"{h} an{'s' if h > 1 else ''}",
                      horizontal=True)
    df = points(peril, horizon)
    couche = pdk.Layer("ScatterplotLayer", df, get_position=["longitude", "latitude"], get_fill_color="couleur",
                       get_radius=900, radius_min_pixels=1.2, radius_max_pixels=6, pickable=True)
    vue = pdk.ViewState(latitude=46.6, longitude=2.4, zoom=4.6)
    st.pydeck_chart(pdk.Deck(layers=[couche], initial_view_state=vue, map_style="light",
                             tooltip={"text": "{nom_commune} ({nom_departement})\n{rang}"}), height=560)
    st.caption("Chaque point est une commune ; plus il est rouge, plus elle est haut dans le classement national. "
               "Survolez un point pour voir la commune.")
    st.markdown(f"##### Les 20 communes les plus exposées — {PERILS[peril].lower()}, {horizon} an{'s' if horizon > 1 else ''}")
    tete = df.sort_values("percentile_national", ascending=False).head(20)
    st.dataframe(tete[["nom_commune", "nom_departement", "rang"]].rename(
        columns={"nom_commune": "Commune", "nom_departement": "Département", "rang": "Classement"}),
        hide_index=True, width="stretch")

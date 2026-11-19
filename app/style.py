"""Identité visuelle de l'application : typographie, bandeau d'en-tête, cartes, barre latérale."""

import html

import streamlit as st

ENCRE = "#14232e"
OCEAN = "#1f6f8b"
OCRE = "#c9822b"
SABLE = "#f6f3ee"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Source+Serif+4:opsz,wght@8..60,600;8..60,700&display=swap');

html, body, .stApp, .stMarkdown, .stDataFrame, button, input, textarea {{
  font-family: 'Inter', system-ui, sans-serif;
}}
/* Les icônes gardent leur police (sinon leur nom s'affiche en toutes lettres) */
[data-testid="stIconMaterial"], .material-symbols-rounded, span[class*="material"] {{
  font-family: 'Material Symbols Rounded' !important;
}}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stMain"] {{ background: {SABLE}; }}
[data-testid="stMainBlockContainer"] {{ padding-top: 2.2rem; max-width: 1180px; }}
h1, h2, h3, h4, h5 {{ font-family: 'Source Serif 4', Georgia, serif !important; color: {ENCRE}; letter-spacing: -0.01em; }}
h5 {{ font-size: 1.12rem !important; margin-top: .4rem; }}

/* Bandeau d'en-tête */
.bandeau {{
  background: linear-gradient(120deg, {ENCRE} 0%, #1d4f63 55%, {OCEAN} 100%);
  border-radius: 18px; padding: 1.7rem 2rem 1.5rem; margin: .6rem 0 1.4rem; color: #fff;
  box-shadow: 0 10px 30px rgba(20, 35, 46, .18); position: relative; overflow: hidden;
}}
.bandeau::after {{
  content: ""; position: absolute; right: -60px; top: -60px; width: 240px; height: 240px;
  border-radius: 50%; background: radial-gradient(circle, rgba(201,130,43,.55), rgba(201,130,43,0) 70%);
}}
.bandeau .surtitre {{ text-transform: uppercase; letter-spacing: .14em; font-size: .72rem; opacity: .75; font-weight: 600; }}
.bandeau h1 {{ color: #fff !important; font-size: 2.1rem; margin: .25rem 0 .35rem; padding: 0; line-height: 1.15; }}
.bandeau p {{ margin: 0; opacity: .85; font-size: .98rem; max-width: 46rem; }}

/* Indicateurs en cartes */
[data-testid="stMetric"] {{
  background: #fff; border: 1px solid #e6e1d8; border-top: 4px solid {OCEAN};
  border-radius: 14px; padding: .9rem 1.1rem .8rem; box-shadow: 0 2px 10px rgba(20,35,46,.05);
}}
[data-testid="column"]:nth-child(1) [data-testid="stMetric"], [data-testid="stColumn"]:nth-child(1) [data-testid="stMetric"] {{ border-top-color: {OCRE}; }}
[data-testid="stMetricLabel"] p {{ font-size: .8rem !important; color: #5b6b75; font-weight: 600; text-transform: uppercase; letter-spacing: .04em; }}
[data-testid="stMetricValue"] {{ font-family: 'Source Serif 4', Georgia, serif; font-size: 1.9rem !important; color: {ENCRE}; }}

/* Blocs encadrés, tableaux, menus dépliants */
[data-testid="stVerticalBlockBorderWrapper"] {{ background: #fff; border-radius: 14px !important; border-color: #e6e1d8 !important; }}
[data-testid="stDataFrame"] {{ border-radius: 12px; overflow: hidden; border: 1px solid #e6e1d8; }}
[data-testid="stExpander"] details {{ background: #fff; border-radius: 12px; border-color: #e6e1d8; }}
[data-testid="stCaptionContainer"] {{ color: #6b7a83; }}
.stButton > button {{ border-radius: 10px; border: 1px solid #d9d3c8; font-weight: 500; }}
.stButton > button[kind="primary"] {{ background: {OCEAN}; border-color: {OCEAN}; }}
hr {{ border-color: #e6e1d8 !important; }}

/* Barre latérale */
[data-testid="stSidebar"] {{ background: {ENCRE}; }}
[data-testid="stSidebar"] * {{ color: #e9eef1 !important; }}
[data-testid="stSidebarNav"] a {{ border-radius: 10px; padding: .45rem .7rem; }}
[data-testid="stSidebarNav"] a:hover {{ background: rgba(255,255,255,.08); }}
[data-testid="stSidebarNav"] a[aria-current="page"] {{ background: rgba(201,130,43,.25); }}
[data-testid="stSidebar"] hr {{ border-color: rgba(255,255,255,.15) !important; }}
.signature {{ font-size: .82rem; line-height: 1.5; opacity: .85; }}
.signature a {{ color: #f0c58a !important; text-decoration: none; }}

/* Légende de la carte */
.legende {{ display: flex; flex-wrap: wrap; gap: .35rem 1.1rem; align-items: center; margin: .2rem 0 .6rem; font-size: .85rem; color: #45535c; }}
.legende .pastille {{ display: inline-block; width: 14px; height: 14px; border-radius: 50%; margin-right: .4rem; vertical-align: -2px; border: 1px solid rgba(0,0,0,.08); }}
.legende .titre {{ font-weight: 600; color: {ENCRE}; margin-right: .3rem; }}

@media (max-width: 640px) {{
  .bandeau {{ padding: 1.2rem 1.2rem 1.1rem; }}
  .bandeau h1 {{ font-size: 1.45rem; }}
  .bandeau p {{ font-size: .9rem; }}
}}
#MainMenu, footer {{ visibility: hidden; }}
</style>
"""


def appliquer():
    st.markdown(CSS, unsafe_allow_html=True)


def bandeau(titre: str, texte: str, surtitre: str = "Risque climatique par commune"):
    st.markdown(f"""<div class="bandeau"><div class="surtitre">{html.escape(surtitre)}</div>
<h1>{html.escape(titre)}</h1><p>{html.escape(texte)}</p></div>""", unsafe_allow_html=True)


def legende(titre: str, elements: list[tuple[str, list[int]]]):
    pastilles = "".join(
        f'<span><span class="pastille" style="background: rgb({r},{g},{b})"></span>{html.escape(lib)}</span>'
        for lib, (r, g, b, *_) in elements)
    st.markdown(f'<div class="legende"><span class="titre">{html.escape(titre)}</span>{pastilles}</div>',
                unsafe_allow_html=True)

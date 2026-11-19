"""Application Streamlit : risque de catastrophe naturelle par commune.

Lancement local : streamlit run app/streamlit_app.py
"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

import vue_assistant  # noqa: E402
import vue_carte  # noqa: E402
import vue_commune  # noqa: E402
import vue_methode  # noqa: E402

st.set_page_config(page_title="Risque CatNat par commune", page_icon="🌧️", layout="wide")

navigation = st.navigation([
    st.Page(vue_commune.page, title="Une commune", icon="🏘️", default=True),
    st.Page(vue_carte.page, title="Carte", icon="🗺️", url_path="carte"),
    st.Page(vue_assistant.page, title="Assistant", icon="💬", url_path="assistant"),
    st.Page(vue_methode.page, title="Méthode", icon="📐", url_path="methode"),
])
with st.sidebar:
    st.markdown("**Risque climatique par commune**")
    st.caption("Projet portfolio de Célia Monga — données publiques, mises à jour chaque semaine.")
navigation.run()

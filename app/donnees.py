"""Chargement des données et des services partagés par toutes les pages de l'application."""

import json
import os
import sys
import tempfile
from pathlib import Path

import requests
import streamlit as st

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "src"))

from base_ia import base_isolee  # noqa: E402

DEPOT = "sabcelia1/risque-climatique-communes"
URL_EXPORT = f"https://github.com/{DEPOT}/releases/download/donnees-app/{{fichier}}"
FICHIERS = ["app.duckdb", "metriques_modele.json", "fiches_exemples.json"]
LIMITE_FICHES, LIMITE_QUESTIONS = 5, 10          # par visiteur : protège le quota Gemini gratuit


@st.cache_resource(ttl=24 * 3600, show_spinner="Chargement des données…")
def dossier_donnees() -> Path:
    """Export local (après lancer.bat ou src/exporter_app.py), sinon dernière version publiée."""
    local = RACINE / "app" / "donnees"
    if (local / "app.duckdb").exists():
        return local
    cible = Path(tempfile.mkdtemp(prefix="risque_"))
    for fichier in FICHIERS:
        r = requests.get(URL_EXPORT.format(fichier=fichier), timeout=120)
        if r.ok:
            (cible / fichier).write_bytes(r.content)
        elif fichier == "app.duckdb":
            st.error("Données indisponibles : l'export n'a pas encore été publié.")
            st.stop()
    return cible


@st.cache_resource(ttl=24 * 3600)
def base(avec_facteurs: bool = True):
    """Base isolée en lecture seule (voir src/base_ia.py) ; utiliser .cursor() à chaque requête."""
    return base_isolee(dossier_donnees() / "app.duckdb", avec_facteurs=avec_facteurs)


def requete(sql: str, params=None):
    return base().cursor().execute(sql, params or []).df()


@st.cache_data(ttl=24 * 3600)
def communes():
    return requete("""select code_insee, nom_commune, code_departement, nom_departement, nom_region,
                             population, latitude, longitude
                      from communes order by nom_commune, code_departement""")


@st.cache_data(ttl=24 * 3600)
def json_publie(fichier: str) -> dict:
    chemin = dossier_donnees() / fichier
    return json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}


def cle_gemini_disponible() -> bool:
    try:
        if "GEMINI_API_KEY" in st.secrets:
            os.environ.setdefault("GEMINI_API_KEY", st.secrets["GEMINI_API_KEY"])
    except Exception:                                   # pas de fichier de secrets
        pass
    from llm import cle_api
    return bool(cle_api())


@st.cache_resource
def gemini():
    from llm import Gemini
    return Gemini()


def compteur(nom: str, limite: int) -> bool:
    """Vrai si le visiteur peut encore utiliser Gemini pour cette fonction ; incrémente."""
    n = st.session_state.get(nom, 0)
    if n >= limite:
        return False
    st.session_state[nom] = n + 1
    return True

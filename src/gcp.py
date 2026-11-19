"""Accès à Google Cloud, sans clé stockée dans le projet.

Les identifiants sont ceux de l'environnement (« Application Default Credentials ») :
  - sur GitHub Actions : fédération d'identité (Workload Identity Federation),
    GitHub prouve à Google qu'il s'agit bien de ce dépôt, aucune clé n'existe ;
  - sur un ordinateur : `gcloud auth application-default login` (optionnel).
Une clé dans secrets/cle-gcp.json est encore acceptée si une organisation l'autorise.
"""

import json
import os
import sys
from pathlib import Path

from config import ROOT_DIR

PROJET_PAR_DEFAUT = "risques-climatiuqes-communes"   # identifiant public, pas un secret
CLE_LOCALE = ROOT_DIR / "secrets" / "cle-gcp.json"
DATASET_RAW = "risque_raw"      # tables chargées depuis Python
DATASET_DBT = "risque"          # tables construites par dbt
LOCALISATION = "EU"


def identifiant_projet() -> str:
    """GCP_PROJECT_ID, sinon le projet de la clé locale, sinon le projet par défaut."""
    if os.environ.get("GCP_PROJECT_ID"):
        return os.environ["GCP_PROJECT_ID"]
    if CLE_LOCALE.exists():
        projet = json.loads(CLE_LOCALE.read_text(encoding="utf-8")).get("project_id")
        if projet:
            return projet
    return PROJET_PAR_DEFAUT


def configurer() -> str | None:
    """Prépare l'environnement ; renvoie l'id du projet, ou None sans identifiants."""
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") and CLE_LOCALE.exists():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(CLE_LOCALE)
    try:
        import google.auth
        google.auth.default()
    except Exception:
        return None
    os.environ["GCP_PROJECT_ID"] = identifiant_projet()
    return os.environ["GCP_PROJECT_ID"]


if __name__ == "__main__":
    # Code retour 0 si BigQuery est accessible (utilisé par lancer.bat)
    sys.exit(0 if configurer() else 1)

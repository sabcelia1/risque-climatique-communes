"""Accès à Google Cloud : localisation de la clé du compte de service.

La clé n'est JAMAIS versionnée. Elle est cherchée, dans l'ordre :
  1. dans la variable d'environnement GOOGLE_APPLICATION_CREDENTIALS
     (c'est ce que fait GitHub Actions) ;
  2. dans secrets/cle-gcp.json (sur votre ordinateur ; dossier exclu de Git).
L'identifiant du projet est lu dans GCP_PROJECT_ID, sinon dans la clé elle-même.
"""

import json
import os
from pathlib import Path

from config import ROOT_DIR

CLE_LOCALE = ROOT_DIR / "secrets" / "cle-gcp.json"
DATASET_RAW = "risque_raw"      # tables chargées depuis Python
DATASET_DBT = "risque"          # tables construites par dbt
LOCALISATION = "EU"


def chemin_cle() -> Path | None:
    env = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if env and Path(env).exists():
        return Path(env)
    return CLE_LOCALE if CLE_LOCALE.exists() else None


def configurer() -> str | None:
    """Renseigne les variables d'environnement attendues ; renvoie l'id du projet."""
    cle = chemin_cle()
    if cle is None:
        return None
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(cle)
    projet = os.environ.get("GCP_PROJECT_ID") or json.loads(cle.read_text(encoding="utf-8")).get("project_id")
    if projet:
        os.environ["GCP_PROJECT_ID"] = projet
    return projet

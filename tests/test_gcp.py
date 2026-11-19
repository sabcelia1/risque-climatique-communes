"""Tests de la configuration Google Cloud (sans connexion réelle)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import gcp  # noqa: E402


def test_projet_par_defaut(tmp_path, monkeypatch):
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    monkeypatch.setattr(gcp, "CLE_LOCALE", tmp_path / "absente.json")
    assert gcp.identifiant_projet() == gcp.PROJET_PAR_DEFAUT


def test_projet_variable_d_environnement_prioritaire(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT_ID", "autre-projet")
    assert gcp.identifiant_projet() == "autre-projet"


def test_projet_lu_dans_la_cle(tmp_path, monkeypatch):
    cle = tmp_path / "cle-gcp.json"
    cle.write_text(json.dumps({"type": "service_account", "project_id": "mon-projet"}))
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    monkeypatch.setattr(gcp, "CLE_LOCALE", cle)
    assert gcp.identifiant_projet() == "mon-projet"


def test_sans_identifiants_rien_n_est_configure(tmp_path, monkeypatch):
    import google.auth
    from google.auth.exceptions import DefaultCredentialsError

    def refuser(*a, **k):
        raise DefaultCredentialsError("aucun identifiant")
    monkeypatch.setattr(google.auth, "default", refuser)
    monkeypatch.setattr(gcp, "CLE_LOCALE", tmp_path / "absente.json")
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    assert gcp.configurer() is None

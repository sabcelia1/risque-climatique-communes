"""Tests de la configuration Google Cloud (sans connexion réelle)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import gcp  # noqa: E402


def test_sans_cle_rien_n_est_configure(tmp_path, monkeypatch):
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.setattr(gcp, "CLE_LOCALE", tmp_path / "absente.json")
    assert gcp.configurer() is None


def test_projet_lu_dans_la_cle(tmp_path, monkeypatch):
    cle = tmp_path / "cle-gcp.json"
    cle.write_text(json.dumps({"type": "service_account", "project_id": "mon-projet"}))
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    monkeypatch.setattr(gcp, "CLE_LOCALE", cle)
    assert gcp.configurer() == "mon-projet"
    import os
    assert os.environ["GOOGLE_APPLICATION_CREDENTIALS"] == str(cle)

"""Tests du modèle : découpage temporel, métriques et explications."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import modele  # noqa: E402


def table_factice(n_communes=60, annees=range(1992, 2026), graine=0):
    rng = np.random.default_rng(graine)
    lignes = []
    for famille in ("inondation", "secheresse"):
        for c in range(n_communes):
            risque = rng.uniform(0, 0.4)
            for a in annees:
                lignes.append({
                    "code_insee": f"{c:05d}", "code_departement": "01", "annee": a,
                    "famille_peril": famille, "cible": int(rng.random() < risque),
                    "nb_evt_depuis_debut": int(risque * (a - 1982)), "nb_evt_1an": 0,
                    "nb_evt_5ans": int(risque * 5), "nb_evt_10ans": int(risque * 10),
                    "annees_depuis_derniere": np.nan, "nb_evt_autres_perils_10ans": 0,
                    "taux_dept_5ans": 0.1, "population": 1000, "surface_km2": 10.0,
                    "densite_hab_km2": 100.0, "latitude": 45.0, "longitude": 2.0,
                    "annee_evaluable": a <= (2024 if famille == "inondation" else 2021),
                    "historique_complet": True, "annee_a_predire": a == 2025})
    return modele.preparer(pd.DataFrame(lignes))


@pytest.mark.parametrize("famille", ["inondation", "secheresse"])
def test_decoupage_temporel_sans_recouvrement(famille):
    parts = modele.decouper(table_factice(), famille)
    assert parts["entrainement"]["annee"].max() < parts["validation"]["annee"].min()
    assert parts["validation"]["annee"].max() < parts["test"]["annee"].min()
    assert parts["test"]["annee_evaluable"].all()          # jamais d'année incomplète en test
    assert not parts["test"]["annee_a_predire"].any()


def test_secheresse_testee_avant_2022():
    parts = modele.decouper(table_factice(), "secheresse")
    assert parts["test"]["annee"].max() <= 2021


def test_part_captee():
    y = np.array([1, 1, 0, 0, 0, 0, 0, 0, 0, 0])
    assert modele.part_captee(y, np.arange(10)[::-1], part=0.2) == 1.0   # les 2 touchées en tête
    assert modele.part_captee(y, np.arange(10), part=0.2) == 0.0         # classement inversé


def test_taux_historique_ramene_a_une_frequence():
    df = modele.preparer(pd.DataFrame({"annee": [1992, 2022], "nb_evt_depuis_debut": [5, 20],
                                       "cible": [0, 1], **{v: [0, 0] for v in modele.VARIABLES
                                                           if v != "taux_historique"}}))
    assert df["taux_historique"].tolist() == [0.5, 0.5]


def test_shap_explique_exactement_la_prediction():
    df = table_factice()
    parts = modele.decouper(df, "inondation")
    lgbm = modele.entrainer_lgbm(parts["entrainement"], parts["validation"])
    X = parts["test"]
    shap = modele.contributions_shap(lgbm, X)
    brut = lgbm.predict(X[list(modele.VARIABLES)], raw_score=True)
    assert np.allclose(shap.sum(axis=1), brut)              # somme des contributions = prédiction
    facteurs = modele.principaux_facteurs(shap, X)
    assert set(facteurs["facteur_1"]) <= set(modele.VARIABLES)
    assert (facteurs["contribution_1"].abs() >= facteurs["contribution_2"].abs()).all()

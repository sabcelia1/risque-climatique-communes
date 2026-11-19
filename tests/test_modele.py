"""Tests du modèle : découpages temporels, métriques, calibration et explications."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import modele  # noqa: E402


def table_factice(n_communes=40, annees=range(1992, 2026), graine=0):
    rng = np.random.default_rng(graine)
    lignes = []
    for famille in ("inondation", "secheresse"):
        derniere = modele.DERNIERE_ANNEE_EVALUABLE[famille]
        for c in range(n_communes):
            risque = rng.uniform(0, 0.4)
            evts = {a: int(rng.random() < risque) for a in annees}
            for a in annees:
                fen = lambda h: int(any(evts.get(a + k, 0) for k in range(h)))
                lignes.append({
                    "code_insee": f"{c:05d}", "code_departement": "01", "annee": a,
                    "famille_peril": famille, "cible": evts[a], "cible_3ans": fen(3), "cible_5ans": fen(5),
                    "nb_evt_depuis_debut": int(risque * (a - 1982)), "nb_evt_1an": 0,
                    "nb_evt_5ans": int(risque * 5), "nb_evt_10ans": int(risque * 10),
                    "annees_depuis_derniere": np.nan, "nb_evt_autres_perils_10ans": 0,
                    "taux_dept_5ans": 0.1, "population": 1000, "surface_km2": 10.0,
                    "densite_hab_km2": 100.0, "latitude": 45.0, "longitude": 2.0,
                    "annee_evaluable": a <= derniere, "annee_evaluable_3ans": a + 2 <= derniere,
                    "annee_evaluable_5ans": a + 4 <= derniere,
                    "historique_complet": True, "annee_a_predire": a == 2025})
    return modele.preparer(pd.DataFrame(lignes))


@pytest.mark.parametrize("famille", ["inondation", "secheresse"])
@pytest.mark.parametrize("horizon", [1, 3, 5])
@pytest.mark.parametrize("production", [False, True])
def test_aucune_annee_de_cible_partagee(famille, horizon, production):
    parts = modele.decouper(table_factice(), famille, horizon, production)
    noms = list(parts)
    for avant, apres in zip(noms, noms[1:]):
        fin_fenetre = parts[avant]["annee"].max() + horizon - 1      # dernière année de cible
        assert fin_fenetre < parts[apres]["annee"].min()
    derniere = modele.DERNIERE_ANNEE_EVALUABLE[famille]
    for p in parts.values():                                          # fenêtres complètes seulement
        assert p["annee"].max() + horizon - 1 <= derniere
        assert not p["annee_a_predire"].any()


def test_horizon_1an_inchange():
    assert modele.periodes("secheresse", 1)["test"] == (2017, 2021)
    assert modele.periodes("inondation", 1)["test"] == (2021, 2024)


def test_part_captee():
    y = np.array([1, 1, 0, 0, 0, 0, 0, 0, 0, 0])
    assert modele.part_captee(y, np.arange(10)[::-1], part=0.2) == 1.0
    assert modele.part_captee(y, np.arange(10), part=0.2) == 0.0


def test_taux_historique_ramene_a_une_frequence():
    df = modele.preparer(pd.DataFrame({"annee": [1992, 2022], "nb_evt_depuis_debut": [5, 20],
                                       "cible": [0, 1], **{v: [0, 0] for v in modele.VARIABLES
                                                           if v != "taux_historique"}}))
    assert df["taux_historique"].tolist() == [0.5, 0.5]


def test_calibration_recale_le_niveau_sans_changer_le_classement():
    rng = np.random.default_rng(1)
    score = rng.normal(-3, 1, 5000)                           # le modèle sous-estime...
    y = (rng.random(5000) < 1 / (1 + np.exp(-(score + 1.5)))).astype(int)   # ...le vrai risque
    calib = modele.Calibrateur(score, y)
    p = calib(score)
    assert abs(p.mean() - y.mean()) < 0.01
    assert (np.argsort(p) == np.argsort(score)).all()


def test_shap_explique_exactement_la_prediction():
    df = table_factice()
    noms = list(modele.variables(df))
    parts = modele.decouper(df, "inondation", 1)
    lgbm = modele.entrainer_lgbm(parts["entrainement"], parts["validation"], noms)
    X = parts["test"]
    shap = modele.contributions_shap(lgbm, X, noms)
    brut = lgbm.predict(X[noms], raw_score=True)
    assert np.allclose(shap.sum(axis=1), brut)
    facteurs = modele.principaux_facteurs(shap, X, noms)
    assert (facteurs["contribution_1"].abs() >= facteurs["contribution_2"].abs()).all()


def test_exposition_ajoutee_si_disponible():
    df = table_factice().assign(part_argile_fort=0.2)
    assert "part_argile_fort" in modele.variables(df)
    assert "part_argile_fort" not in modele.variables(table_factice())

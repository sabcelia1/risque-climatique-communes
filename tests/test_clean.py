"""Tests unitaires du nettoyage : lancer avec `python -m pytest`."""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from clean import (corriger_encodage, famille_peril, harmoniser_colonnes,  # noqa: E402
                   lire_dates, normaliser_code_insee)


@pytest.mark.parametrize("libelle, attendu", [
    ("Inondations et coulées de boue", "inondation"),
    ("Inondations par remontées de nappe phréatique", "inondation"),
    ("Mouvements de terrain différentiels consécutifs à la sécheresse et à la réhydratation des sols", "secheresse"),
    ("Sécheresse", "secheresse"),
    ("Mouvements de terrain", "mouvement_terrain"),
    ("Glissement de terrain", "mouvement_terrain"),
    ("Tempête", "vent_tempete"),
    ("Vents cycloniques", "vent_tempete"),
    ("Séisme", "seisme"),
    ("Secousse sismique", "seisme"),
    ("Avalanche", "autre"),
    ("", "inconnu"),
    (None, "inconnu"),
])
def test_famille_peril(libelle, attendu):
    assert famille_peril(libelle) == attendu


def test_corriger_encodage():
    abime = "Sécheresse".encode("utf-8").decode("latin-1")   # « SÃ©cheresse »
    assert corriger_encodage(abime) == "Sécheresse"
    assert corriger_encodage("Inondations") == "Inondations"
    assert corriger_encodage(None) is None


def test_normaliser_code_insee():
    codes = pd.Series(["1001", "2a004", "75108", "69381", "13201", "ABCDE", None])
    assert normaliser_code_insee(codes).tolist() == [
        "01001", "2A004", "75056", "69123", "13055", pd.NA, pd.NA]


def test_lire_dates_deux_formats():
    iso = lire_dates(pd.Series(["2023-10-31", "1999-12-25"]))
    fr = lire_dates(pd.Series(["31/10/2023", "25/12/1999 00:00:00"]))
    assert iso.dt.year.tolist() == [2023, 1999]
    assert fr.dt.month.tolist() == [10, 12]


def test_harmoniser_colonnes_versions():
    ancienne = pd.DataFrame(columns=["cod_nat_catnat", "cod_commune", "lib_commune",
                                     "lib_risque_jo", "dat_deb", "dat_fin", "dat_pub_arrete", "dat_pub_jo"])
    nouvelle = pd.DataFrame(columns=["CODE COMMUNE", "Libellé risque JO", "Date début"])
    assert {"code_insee", "libelle_peril", "date_debut", "id_reconnaissance"} <= set(
        harmoniser_colonnes(ancienne).columns)
    assert set(harmoniser_colonnes(nouvelle).columns) == {"code_insee", "libelle_peril", "date_debut"}


def test_harmoniser_colonnes_libelles_longs():
    cols = ["Code National CATNAT", "Code INSEE Commune", "Libellé Commune", "num_risque_jo",
            "Libellé Risque JO", "Date Début Evt", "Date Fin Evt",
            "Date Publication Arrêté", "Date Publication JO", "dat_maj"]
    out = harmoniser_colonnes(pd.DataFrame(columns=cols))
    attendu = {"id_reconnaissance": "Code National CATNAT", "code_insee": "Code INSEE Commune",
               "nom_commune": "Libellé Commune", "libelle_peril": "Libellé Risque JO",
               "date_debut": "Date Début Evt", "date_fin": "Date Fin Evt",
               "date_arrete": "Date Publication Arrêté", "date_jo": "Date Publication JO"}
    df = pd.DataFrame([cols], columns=cols)
    out = harmoniser_colonnes(df)
    for cible, source in attendu.items():
        assert out[cible].iloc[0] == source, cible


def test_harmoniser_colonnes_manquantes():
    with pytest.raises(SystemExit):
        harmoniser_colonnes(pd.DataFrame(columns=["foo", "bar"]))

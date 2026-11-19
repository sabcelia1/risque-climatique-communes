"""Inventaire détaillé des tables PPRN et AZI de l'archive GASPAR."""
import io, sys, zipfile
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from config import SOURCES
from ingest import telecharger

contenu = telecharger(SOURCES["gaspar"]["url"])
z = zipfile.ZipFile(io.BytesIO(contenu))
lire = lambda motif: pd.read_csv(z.open(next(n for n in z.namelist() if motif in n)), sep=";", dtype=str)
pprn = lire("pprn_")
print("PPRN colonnes :", list(pprn.columns))
print("PPRN lignes :", len(pprn), "communes :", pprn["CODE INSEE COMMUNE"].nunique())
for c in ["LIBELLE MODELE", "LIBELLE RISQUE 2", "LIBELLE RISQUE 3", "ETAT PROCEDURE" if "ETAT PROCEDURE" in pprn else pprn.columns[-6]]:
    print(f"\n{c}:\n", pprn[c].value_counts().head(25).to_string())
dates = [c for c in pprn.columns if any(k in c.upper() for k in ("PRESCRIPTION", "APPROBATION", "DATE", "DAT"))]
print("\nColonnes de dates PPRN, taux de remplissage et min/max :")
for c in dates:
    d = pd.to_datetime(pprn[c], errors="coerce")
    print(f"  {c}: {d.notna().mean():.0%}  {d.min()} -> {d.max()}")
print("\nExemple ligne :", pprn.iloc[0].dropna().to_dict())
azi = lire("azi_")
print("\nAZI lignes :", len(azi), "communes :", azi["cod_commune"].nunique())
for c in ["dat_diffusion", "dat_realisation", "dat_program_deb"]:
    d = pd.to_datetime(azi[c], errors="coerce"); print(f"  {c}: {d.notna().mean():.0%}  {d.min()} -> {d.max()}")
ddrm = lire("ddrm_")
print("\nDDRM libellés :\n", ddrm["lib_risque"].value_counts().head(30).to_string())

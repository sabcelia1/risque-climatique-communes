"""Exposition de chaque commune au retrait-gonflement des argiles (aléa BRGM).

Calcul ponctuel (la géologie ne change pas) : on tire des points au hasard dans
chaque commune, et on regarde dans quelle zone d'aléa ils tombent. La part des
points donne la part du territoire en aléa faible, moyen ou fort.

Sources (Licence Ouverte) :
  - aléa retrait-gonflement des argiles, BRGM / Géorisques ;
  - contours des communes, Etalab (découpage administratif).
Résultat : data/reference/exposition_argiles.csv, versionné dans le dépôt.

Usage (lourd : ~1 Go à télécharger, lancé par GitHub Actions) :
    python src/exposition_argiles.py
"""

import io
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from config import DATA_DIR
from ingest import telecharger

URL_ALEA = "https://files.georisques.fr/argiles/AleaRG_Fxx_L93.zip"
URL_COMMUNES = ("https://etalab-datasets.geo.data.gouv.fr/contours-administratifs/"
                "2025/geojson/communes-100m.geojson.gz")
POINTS_PAR_COMMUNE = 200
SORTIE = DATA_DIR / "reference" / "exposition_argiles.csv"
NIVEAUX = {1: "faible", 2: "moyen", 3: "fort"}


def niveau_alea(gdf):
    """Trouve la colonne du niveau d'aléa (1/2/3 ou faible/moyen/fort)."""
    for col in gdf.columns:
        if col == "geometry":
            continue
        valeurs = set(gdf[col].dropna().astype(str).str.lower().unique()[:50])
        if valeurs and valeurs <= {"1", "2", "3", "1.0", "2.0", "3.0"}:
            return gdf[col].astype(float).astype(int)
        if valeurs and valeurs <= {"faible", "moyen", "fort", "moyenne", "forte", "a priori nul"}:
            texte = gdf[col].astype(str).str.lower()
            return texte.map({"faible": 1, "moyen": 2, "moyenne": 2, "fort": 3, "forte": 3}).fillna(0).astype(int)
    raise SystemExit(f"Colonne d'aléa introuvable : {list(gdf.columns)}")


def main() -> int:
    import geopandas as gpd

    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        print("Téléchargement de l'aléa argiles (BRGM)...")
        with zipfile.ZipFile(io.BytesIO(telecharger(URL_ALEA))) as z:
            z.extractall(tmp)
        shp = sorted(Path(tmp).rglob("*.shp"), key=lambda p: p.stat().st_size)[-1]
        alea = gpd.read_file(shp, engine="pyogrio")
        print(f"  {shp.name} : {len(alea):,} zones, colonnes {list(alea.columns)}, {alea.crs}")
        alea["niveau"] = niveau_alea(alea)
        print("  zones par niveau :", alea["niveau"].value_counts().to_dict())
        alea = alea[alea["niveau"] > 0][["niveau", "geometry"]].to_crs(2154)

    print("Téléchargement des contours des communes...")
    communes = gpd.read_file(io.BytesIO(telecharger(URL_COMMUNES)))
    code = next(c for c in ("code", "INSEE_COM", "insee") if c in communes.columns)
    communes = communes[[code, "geometry"]].rename(columns={code: "code_insee"}).to_crs(2154)
    communes = communes[~communes["code_insee"].str.startswith("97")]          # métropole seulement
    print(f"  {len(communes):,} communes métropolitaines")

    print(f"Tirage de {POINTS_PAR_COMMUNE} points par commune...")
    points = communes.sample_points(POINTS_PAR_COMMUNE, rng=np.random.default_rng(42))
    points = (gpd.GeoDataFrame({"code_insee": communes["code_insee"].values}, geometry=points.values, crs=2154)
              .explode(index_parts=False).reset_index(drop=True))
    print(f"  {len(points):,} points ; croisement avec l'aléa...")
    joint = gpd.sjoin(points, alea, how="left", predicate="within")
    joint = joint.groupby(level=0)["niveau"].max()                         # zones qui se chevauchent
    points["niveau"] = joint.reindex(points.index).fillna(0).astype(int)

    parts = (pd.crosstab(points["code_insee"], points["niveau"], normalize="index")
               .reindex(columns=[0, 1, 2, 3], fill_value=0))
    sortie = pd.DataFrame({
        "code_insee": parts.index,
        "part_argile_faible": parts[1].round(3).values,
        "part_argile_moyen": parts[2].round(3).values,
        "part_argile_fort": parts[3].round(3).values,
    })
    sortie["indice_argile"] = (sortie["part_argile_faible"] + 2 * sortie["part_argile_moyen"]
                               + 3 * sortie["part_argile_fort"]).round(3)
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    sortie.to_csv(SORTIE, index=False)
    print(f"\n{len(sortie):,} communes -> {SORTIE} ({time.time() - t0:.0f} s)")
    print(sortie.describe().round(3).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())

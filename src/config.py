"""Configuration centrale : sources de données, chemins et règles métier."""

from pathlib import Path

# --- Chemins -----------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
REPORTS_DIR = ROOT_DIR / "reports"

# --- Sources (open data, Licence Ouverte) --------------------------------------
SOURCES = {
    "gaspar": {
        "description": "Base GASPAR (ministère de la Transition écologique) : "
                       "arrêtés de catastrophe naturelle par commune",
        # URL "latest" : pointe toujours vers la dernière version publiée.
        # Selon les versions, le fichier est un CSV ou une archive ZIP contenant
        # plusieurs tables (catnat, PPRN, AZI…) : l'ingestion gère les deux cas.
        "url": "https://www.data.gouv.fr/api/1/datasets/r/d6fb9e18-b66b-499c-8284-46a3595579cc",
        "page": "https://www.data.gouv.fr/datasets/base-nationale-de-gestion-assistee-des-procedures-administratives-relatives-aux-risques-gaspar",
    },
    "communes": {
        "description": "Référentiel des communes (API Découpage administratif)",
        "url": "https://geo.api.gouv.fr/communes"
               "?fields=nom,code,codeDepartement,codeRegion,population,surface,centre,departement,region"
               "&format=json",
        "page": "https://geo.api.gouv.fr/decoupage-administratif",
    },
}

# --- Règles métier -------------------------------------------------------------
# Familles de périls : le libellé GASPAR est très détaillé (« Inondations et
# coulées de boue », « Mouvements de terrain différentiels consécutifs à la
# sécheresse et à la réhydratation des sols »…). On le ramène à 6 familles,
# par mots-clés, dans l'ordre : la première famille reconnue l'emporte.
FAMILLES_PERILS = [
    ("secheresse",        ["secheresse", "rehydratation", "retrait", "gonflement"]),
    ("inondation",        ["inondation", "coulee", "crue", "remontee de nappe", "submersion", "lave torrentielle"]),
    ("mouvement_terrain", ["mouvement", "glissement", "eboulement", "effondrement", "affaissement", "chute de bloc"]),
    ("vent_tempete",      ["vent", "tempete", "cyclon", "ouragan", "tornade", "houle"]),
    ("seisme",            ["seisme", "sisme"]),
    ("autre",             []),  # tout le reste (avalanche, grêle, poids de la neige…)
]

# Arrondissements municipaux -> commune, pour harmoniser les jointures
ARRONDISSEMENTS = {
    **{f"751{i:02d}": "75056" for i in range(1, 21)},   # Paris
    **{f"6938{i}": "69123" for i in range(1, 10)},      # Lyon
    **{f"132{i:02d}": "13055" for i in range(1, 17)},   # Marseille
}

# Période d'analyse : le régime CatNat existe depuis la loi du 13 juillet 1982
ANNEE_DEBUT = 1982

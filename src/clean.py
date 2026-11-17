"""Étape 1 — Nettoyage : transforme data/raw/ en tables propres dans data/processed/.

Produit :
    data/processed/catnat.parquet               1 ligne = 1 reconnaissance CatNat
                                                (arrêté x commune x péril)
    data/processed/catnat_commune_annee.parquet 1 ligne = 1 commune x 1 année x 1 famille
                                                de péril (nombre de reconnaissances)
    data/processed/communes.parquet             référentiel des communes
    reports/qualite_donnees.md                  rapport de qualité chiffré

Usage :
    python src/clean.py
"""

import json
import re
import sys
import unicodedata

import pandas as pd

from config import ANNEE_DEBUT, ARRONDISSEMENTS, FAMILLES_PERILS, PROCESSED_DIR, RAW_DIR, REPORTS_DIR

QUALITE: list[tuple[str, str, str]] = []


def log(table: str, controle: str, resultat) -> None:
    QUALITE.append((table, controle, str(resultat)))
    print(f"  [{table}] {controle} : {resultat}")


# --- Fonctions utilitaires (testées dans tests/test_clean.py) ------------------------
def sans_accents(texte: str) -> str:
    """Minuscules, sans accents ni espaces superflus : base de comparaison."""
    texte = unicodedata.normalize("NFKD", str(texte))
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texte).strip().lower()


def corriger_encodage(texte):
    """Répare les accents mal encodés signalés sur GASPAR (« SÃ©cheresse » -> « Sécheresse »)."""
    if not isinstance(texte, str) or "Ã" not in texte and "Â" not in texte:
        return texte
    try:
        return texte.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return texte


def famille_peril(libelle) -> str:
    """Ramène un libellé de péril GASPAR à une des familles de config.FAMILLES_PERILS."""
    if not isinstance(libelle, str) or not libelle.strip():
        return "inconnu"
    texte = sans_accents(libelle)
    for famille, mots in FAMILLES_PERILS:
        if any(mot in texte for mot in mots):
            return famille
    return "autre"


def normaliser_code_insee(serie: pd.Series) -> pd.Series:
    """Code INSEE sur 5 caractères (Corse 2A/2B comprise), arrondissements
    de Paris/Lyon/Marseille ramenés à la commune. Valeur invalide -> vide."""
    codes = serie.astype("string").str.strip().str.upper().str.zfill(5)
    codes = codes.where(codes.str.fullmatch(r"\d{5}|2[AB]\d{3}", na=False))
    return codes.replace(ARRONDISSEMENTS)


def lire_dates(serie: pd.Series) -> pd.Series:
    """Les dates GASPAR changent de format selon les versions
    (AAAA-MM-JJ, JJ/MM/AAAA, parfois avec l'heure) : on garde le format
    qui en lit le plus."""
    texte = serie.astype("string").str.strip().str.slice(0, 10)
    essais = [pd.to_datetime(texte, format=f, errors="coerce") for f in ("%Y-%m-%d", "%d/%m/%Y")]
    return max(essais, key=lambda s: s.notna().sum())


# Colonnes attendues -> noms possibles selon les versions du fichier
SYNONYMES = {
    "id_reconnaissance": ["cod_nat_catnat", "code_national_catnat", "code_catnat", "id_catnat"],
    "code_insee":        ["cod_commune", "code_commune", "code_insee", "insee", "codgeo"],
    "nom_commune":       ["lib_commune", "nom_commune", "libelle_commune"],
    "libelle_peril":     ["lib_risque_jo", "libelle_risque_jo", "lib_risque", "libelle_risque", "risque"],
    "date_debut":        ["dat_deb", "date_deb", "date_debut", "dat_debut", "date_debut_evt"],
    "date_fin":          ["dat_fin", "date_fin", "date_fin_evt"],
    "date_arrete":       ["dat_pub_arrete", "date_pub_arrete", "dat_arrete", "date_arrete"],
    "date_jo":           ["dat_pub_jo", "date_pub_jo", "dat_jo", "date_jo"],
}
OBLIGATOIRES = ["code_insee", "libelle_peril", "date_debut"]


def harmoniser_colonnes(df: pd.DataFrame) -> pd.DataFrame:
    """Renomme les colonnes vers des noms stables, quelle que soit la version."""
    normalises = {c: re.sub(r"[^a-z0-9]+", "_", sans_accents(c)).strip("_") for c in df.columns}
    inverse = {nom_norm: c for c, nom_norm in normalises.items()}
    renommage = {}
    for cible, possibles in SYNONYMES.items():
        trouve = next((inverse[p] for p in possibles if p in inverse), None)
        if trouve is not None:
            renommage[trouve] = cible
    manquantes = [c for c in OBLIGATOIRES if c not in renommage.values()]
    if manquantes:
        raise SystemExit(
            f"Colonnes introuvables dans le fichier CatNat : {manquantes}.\n"
            f"Colonnes présentes : {list(df.columns)}\n"
            "Envoyez ce message pour adapter config/SYNONYMES.")
    return df.rename(columns=renommage)[list(dict.fromkeys(renommage.values()))]


def lire_csv_robuste(chemin) -> tuple[pd.DataFrame, str]:
    """Séparateur détecté automatiquement, encodage UTF-8 puis Windows-1252."""
    for encodage in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            df = pd.read_csv(chemin, sep=None, engine="python", dtype=str,
                             encoding=encodage, keep_default_na=False, na_values=[""])
            return df, encodage
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"Impossible de lire {chemin}")


# --- Communes --------------------------------------------------------------------------
def nettoyer_communes() -> pd.DataFrame:
    print("\n== Communes")
    data = json.loads((RAW_DIR / "communes.json").read_text(encoding="utf-8"))
    df = pd.DataFrame(data)
    df["nom_departement"] = df["departement"].map(lambda d: d.get("nom") if isinstance(d, dict) else None)
    df["nom_region"] = df["region"].map(lambda d: d.get("nom") if isinstance(d, dict) else None)
    coords = df["centre"].map(lambda c: c["coordinates"] if isinstance(c, dict) else [None, None])
    df["longitude"] = coords.str[0].astype(float)
    df["latitude"] = coords.str[1].astype(float)
    df = df.rename(columns={"code": "code_insee", "nom": "nom_commune",
                            "codeDepartement": "code_departement", "codeRegion": "code_region",
                            "surface": "surface_ha"})
    df["population"] = df["population"].astype("Int64")
    log("communes", "lignes", f"{len(df):,}")
    log("communes", "population manquante", int(df["population"].isna().sum()))
    return df[["code_insee", "nom_commune", "code_departement", "nom_departement",
               "code_region", "nom_region", "population", "surface_ha", "longitude", "latitude"]]


# --- Arrêtés CatNat ---------------------------------------------------------------------
def nettoyer_catnat(codes_valides: set[str]) -> pd.DataFrame:
    print("\n== Arrêtés de catastrophe naturelle (GASPAR)")
    brut, encodage = lire_csv_robuste(RAW_DIR / "catnat_gaspar.csv")
    log("catnat", "encodage détecté", encodage)
    log("catnat", "lignes brutes", f"{len(brut):,}")
    df = harmoniser_colonnes(brut)

    # 1. Doublons (signalés sur data.gouv.fr : lignes répétées 2 ou 3 fois)
    avant = len(df)
    df = df.drop_duplicates()
    log("catnat", "lignes strictement identiques supprimées", f"{avant - len(df):,}")
    cle = [c for c in ("id_reconnaissance", "code_insee", "libelle_peril") if c in df.columns]
    if "id_reconnaissance" in cle:
        avant = len(df)
        df = df.drop_duplicates(subset=cle, keep="first")
        log("catnat", f"doublons sur ({', '.join(cle)}) supprimés", f"{avant - len(df):,}")

    # 2. Accents mal encodés
    for col in ("libelle_peril", "nom_commune"):
        if col in df.columns:
            abimes = df[col].str.contains("Ã|Â", na=False)
            df[col] = df[col].map(corriger_encodage)
            log("catnat", f"accents réparés ({col})", f"{int(abimes.sum()):,}")

    # 3. Familles de périls
    df["famille_peril"] = df["libelle_peril"].map(famille_peril)
    for famille, n in df["famille_peril"].value_counts().items():
        log("catnat", f"famille de péril — {famille}", f"{n:,} ({n / len(df):.1%})")

    # 4. Dates
    for col in ("date_debut", "date_fin", "date_arrete", "date_jo"):
        if col in df.columns:
            df[col] = lire_dates(df[col])
            log("catnat", f"{col} manquante ou illisible", f"{int(df[col].isna().sum()):,}")
    if "date_fin" in df.columns:
        inversees = df["date_fin"] < df["date_debut"]
        log("catnat", "date de fin avant date de début (fin mise à vide)", int(inversees.sum()))
        df.loc[inversees, "date_fin"] = pd.NaT
        duree = (df["date_fin"] - df["date_debut"]).dt.days
        longues = (duree > 365) & (df["famille_peril"] != "secheresse")
        df["duree_suspecte"] = longues
        log("catnat", "événements de plus d'un an hors sécheresse (signalés, conservés)", int(longues.sum()))
    if "date_arrete" in df.columns:
        incoherent = df["date_arrete"] < df["date_debut"]
        log("catnat", "arrêté publié avant le début de l'événement", int(incoherent.sum()))
    hors_periode = df["date_debut"].dt.year < ANNEE_DEBUT
    log("catnat", f"événements antérieurs à {ANNEE_DEBUT} (exclus)", int(hors_periode.sum()))
    df = df[~hors_periode & df["date_debut"].notna()]
    df["annee"] = df["date_debut"].dt.year.astype("Int64")
    log("catnat", "années couvertes", f"{df['annee'].min()} → {df['annee'].max()}")

    # 5. Communes : GASPAR conserve les codes des communes fusionnées depuis
    df["code_insee"] = normaliser_code_insee(df["code_insee"])
    df["commune_actuelle"] = df["code_insee"].isin(codes_valides)
    n_old = int((~df["commune_actuelle"]).sum())
    log("catnat", "codes absents du référentiel actuel (communes fusionnées ?)",
        f"{n_old:,} ({n_old / len(df):.1%}) — rattachement prévu à l'étape 2")
    log("catnat", "reconnaissances retenues", f"{len(df):,}")
    return df


def agreger(df: pd.DataFrame) -> pd.DataFrame:
    """Nombre de reconnaissances par commune, année et famille de péril."""
    return (df.groupby(["code_insee", "annee", "famille_peril"], as_index=False)
              .size().rename(columns={"size": "nb_reconnaissances"}))


# --- Export et rapport -------------------------------------------------------------------
def preparer_export(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.date          # DATE dans BigQuery (pas TIMESTAMP)
    return df


def ecrire_rapport() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    lignes = ["# Rapport de qualité des données", "",
              f"_Généré automatiquement par `src/clean.py` le {pd.Timestamp.today():%d/%m/%Y}._", "",
              "| Table | Contrôle | Résultat |", "|---|---|---|",
              *[f"| {t} | {c} | {r} |" for t, c, r in QUALITE], ""]
    (REPORTS_DIR / "qualite_donnees.md").write_text("\n".join(lignes), encoding="utf-8")


def main() -> int:
    manquants = [f for f in ("catnat_gaspar.csv", "communes.json") if not (RAW_DIR / f).exists()]
    if manquants:
        print(f"Fichiers manquants dans data/raw/ : {manquants}. Lancez d'abord src/ingest.py",
              file=sys.stderr)
        return 1
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    communes = nettoyer_communes()
    catnat = nettoyer_catnat(set(communes["code_insee"]))
    panel = agreger(catnat)
    log("agrégat", "lignes commune x année x famille", f"{len(panel):,}")

    preparer_export(communes).to_parquet(PROCESSED_DIR / "communes.parquet", index=False)
    preparer_export(catnat).to_parquet(PROCESSED_DIR / "catnat.parquet", index=False)
    panel.to_parquet(PROCESSED_DIR / "catnat_commune_annee.parquet", index=False)
    ecrire_rapport()
    print(f"\nTerminé : tables dans {PROCESSED_DIR}, rapport dans reports/qualite_donnees.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())

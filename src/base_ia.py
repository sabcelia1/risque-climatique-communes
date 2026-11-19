"""Base de données isolée, utilisée par l'IA générative (étape 4).

Les tables utiles sont copiées en mémoire, puis la base est verrouillée :
  - aucun accès aux fichiers ni au réseau (enable_external_access = false) ;
  - configuration figée (lock_configuration = true), impossible à rouvrir par une requête.
Même une requête SQL malveillante ne peut donc lire que ces trois tables.
"""

import duckdb

from config import PROCESSED_DIR

# Tables exposées, avec leur description (sert aussi de documentation au modèle de langage)
TABLES = {
    "communes": {
        "description": "Une ligne par commune actuelle : identité, taille, historique CatNat depuis 1982, "
                       "exposition des sols aux argiles (zonage BRGM 2019).",
        "colonnes": {
            "code_insee": "code INSEE de la commune (texte, ex. '06088')",
            "nom_commune": "nom de la commune", "code_departement": "code du département (texte)",
            "nom_departement": "nom du département", "nom_region": "nom de la région",
            "population": "population", "surface_km2": "superficie en km²", "densite_hab_km2": "habitants par km²",
            "nb_evenements_total": "nombre de reconnaissances CatNat distinctes depuis 1982, tous périls",
            "nb_secheresses": "dont sécheresse", "nb_inondations": "dont inondation",
            "derniere_annee_touchee": "dernière année avec une reconnaissance",
            "part_argile_faible": "part du territoire en exposition faible aux argiles (0 à 1)",
            "part_argile_moyen": "part en exposition moyenne (0 à 1)",
            "part_argile_fort": "part en exposition forte (0 à 1)",
            "latitude": "latitude du centre de la commune", "longitude": "longitude du centre de la commune",
        },
        "sql": """select c.code_insee, c.nom_commune, c.code_departement, c.nom_departement, c.nom_region,
                         c.population, round(c.surface_km2, 2) as surface_km2,
                         round(c.densite_hab_km2, 1) as densite_hab_km2, c.nb_evenements_total,
                         c.nb_secheresses, c.nb_inondations, c.derniere_annee_touchee,
                         a.part_argile_faible, a.part_argile_moyen, a.part_argile_fort,
                         round(c.latitude, 4) as latitude, round(c.longitude, 4) as longitude
                  from src.dim_commune c left join src.exposition_argiles a using (code_insee)""",
    },
    "evenements": {
        "description": "Une ligne par reconnaissance CatNat distincte (commune x péril x dates), de 1982 à 2024.",
        "colonnes": {
            "code_insee": "code INSEE", "nom_commune": "nom de la commune", "code_departement": "code du département",
            "nom_departement": "nom du département", "nom_region": "nom de la région",
            "famille_peril": "'inondation', 'secheresse', 'mouvement_terrain', 'vent_tempete', 'seisme' ou 'autre'",
            "libelle_peril": "libellé officiel du péril", "annee": "année de début de l'événement",
            "date_debut": "date de début", "date_fin": "date de fin", "date_arrete": "date de signature de l'arrêté",
            "delai_reconnaissance_jours": "jours entre le début de l'événement et l'arrêté",
        },
        "sql": """select code_insee, nom_commune, code_departement, nom_departement, nom_region, famille_peril,
                         libelle_peril, annee, date_debut, date_fin, date_arrete, delai_reconnaissance_jours
                  from src.fct_evenements""",
    },
    "predictions": {
        "description": "Risque prédit par le modèle (étape 3) pour chaque commune, péril (inondation, sécheresse) "
                       "et horizon (1, 3 ou 5 ans à partir de l'année indiquée). La probabilité est indicative ; "
                       "le percentile national (0 à 1, 1 = plus exposée) est le résultat fiable.",
        "colonnes": {
            "code_insee": "code INSEE", "nom_commune": "nom de la commune", "nom_departement": "nom du département",
            "annee": "année de départ de la prédiction",
            "famille_peril": "'inondation' ou 'secheresse'", "horizon_ans": "1, 3 ou 5",
            "probabilite": "probabilité indicative d'au moins une reconnaissance sur l'horizon (0 à 1)",
            "percentile_national": "rang de la commune parmi toutes les communes (0 à 1)",
            "facteur_1": "variable qui pèse le plus dans la prédiction",
        },
        "sql": """select p.code_insee, c.nom_commune, c.nom_departement, p.annee, p.famille_peril, p.horizon_ans,
                         p.probabilite, p.percentile_national, p.facteur_1
                  from read_parquet('{predictions}') p left join src.dim_commune c using (code_insee)""",
    },
}


def base_isolee(export=None, avec_facteurs: bool = False) -> duckdb.DuckDBPyConnection:
    """Connexion en mémoire contenant uniquement les tables de TABLES, puis verrouillée.

    export : chemin d'un export pour l'application (src/exporter_app.py) ; à défaut, les
    tables sont construites à partir des sorties du pipeline (dbt et modèle).
    avec_facteurs : ajoute la table predictions_facteurs (détail des prédictions, pour les fiches).
    """
    if export is not None:
        con = duckdb.connect(":memory:")
        con.execute(f"attach '{str(export).replace(chr(92), '/')}' as src (read_only)")
        for nom in list(TABLES) + (["predictions_facteurs"] if avec_facteurs else []):
            con.execute(f"create table {nom} as select * from src.{nom}")
        con.execute("detach src")
        return _verrouiller(con)
    source = PROCESSED_DIR / "risque.duckdb"
    predictions = PROCESSED_DIR / "predictions.parquet"
    for chemin, etape in ((source, "src/lancer_dbt.py local"), (predictions, "src/modele.py")):
        if not chemin.exists():
            raise SystemExit(f"{chemin.name} introuvable : lancez d'abord {etape}")
    con = duckdb.connect(":memory:")
    con.execute(f"attach '{source.as_posix()}' as src (read_only)")
    for nom, table in TABLES.items():
        con.execute(f"create table {nom} as " + table["sql"].format(predictions=predictions.as_posix()))
    if avec_facteurs:
        con.execute(f"create table predictions_facteurs as select * from read_parquet('{predictions.as_posix()}')")
    con.execute("detach src")
    return _verrouiller(con)


def _verrouiller(con: duckdb.DuckDBPyConnection) -> duckdb.DuckDBPyConnection:
    con.execute("set enable_external_access = false")
    con.execute("set lock_configuration = true")
    return con


def schema_texte() -> str:
    """Description des tables, pour le modèle de langage."""
    lignes = []
    for nom, t in TABLES.items():
        lignes.append(f"Table {nom} : {t['description']}")
        lignes += [f"  - {c} : {d}" for c, d in t["colonnes"].items()]
    return "\n".join(lignes)

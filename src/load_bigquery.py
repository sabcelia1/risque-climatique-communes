"""Étape 2 — Chargement des tables nettoyées dans BigQuery (jeu de données risque_raw).

Chaque exécution remplace les tables (WRITE_TRUNCATE) : le chargement est
idempotent, et compatible avec le bac à sable BigQuery gratuit (pas de DML).

Usage :
    python src/load_bigquery.py
"""

import sys

from config import PROCESSED_DIR
from gcp import DATASET_RAW, LOCALISATION, configurer

TABLES = ["communes", "catnat"]


def main() -> int:
    projet = configurer()
    if projet is None:
        print("Clé Google Cloud introuvable (secrets/cle-gcp.json) : voir docs/guide_gcp.md",
              file=sys.stderr)
        return 1
    manquants = [t for t in TABLES if not (PROCESSED_DIR / f"{t}.parquet").exists()]
    if manquants:
        print(f"Tables manquantes {manquants} : lancez d'abord src/clean.py", file=sys.stderr)
        return 1

    from google.cloud import bigquery

    client = bigquery.Client(project=projet, location=LOCALISATION)
    dataset = bigquery.Dataset(f"{projet}.{DATASET_RAW}")
    dataset.location = LOCALISATION
    client.create_dataset(dataset, exists_ok=True)

    config = bigquery.LoadJobConfig(source_format=bigquery.SourceFormat.PARQUET,
                                    write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE)
    for table in TABLES:
        cible = f"{projet}.{DATASET_RAW}.{table}"
        with open(PROCESSED_DIR / f"{table}.parquet", "rb") as f:
            client.load_table_from_file(f, cible, job_config=config).result()
        print(f"  {cible} : {client.get_table(cible).num_rows:,} lignes")
    print("Chargement BigQuery terminé.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

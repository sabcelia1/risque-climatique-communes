"""Étape 2 — Construit et teste les modèles dbt.

Usage :
    python src/lancer_dbt.py            # en local (DuckDB), sans compte cloud
    python src/lancer_dbt.py bigquery   # dans BigQuery (identifiants requis, voir docs/guide_gcp.md)

Équivaut à `dbt build` (modèles + tests) lancé depuis la racine du projet.
"""

import os
import sys

from config import ROOT_DIR
from gcp import configurer


def main() -> int:
    cible = sys.argv[1] if len(sys.argv) > 1 else "local"
    if cible not in ("local", "bigquery"):
        print("Cible inconnue : utilisez « local » ou « bigquery »", file=sys.stderr)
        return 1
    if cible == "bigquery" and configurer() is None:
        print("Identifiants Google Cloud introuvables : voir docs/guide_gcp.md", file=sys.stderr)
        return 1

    from dbt.cli.main import dbtRunner

    os.chdir(ROOT_DIR)                       # chemins relatifs des profils et sources
    dbt_dir = str(ROOT_DIR / "dbt")
    resultat = dbtRunner().invoke(["build", "--project-dir", dbt_dir, "--profiles-dir", dbt_dir,
                                   "--target", cible])
    return 0 if resultat.success else 1


if __name__ == "__main__":
    sys.exit(main())

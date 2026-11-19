"""Étape 5 — Export compact des données pour l'application Streamlit.

Rassemble dans un seul fichier DuckDB (app/donnees/app.duckdb, quelques Mo) les tables
utiles à l'application : communes, événements, prédictions et leur détail. L'application
n'a ainsi rien à recalculer ; GitHub Actions publie ce fichier chaque semaine en
« Release » du dépôt, d'où l'application le télécharge.

Usage :
    python src/exporter_app.py
"""

import json
import shutil
import sys

import duckdb

from base_ia import TABLES, base_isolee
from config import REPORTS_DIR, ROOT_DIR

DOSSIER = ROOT_DIR / "app" / "donnees"


def main() -> int:
    DOSSIER.mkdir(parents=True, exist_ok=True)
    cible = DOSSIER / "app.duckdb"
    cible.unlink(missing_ok=True)
    source = base_isolee(avec_facteurs=True)
    sortie = duckdb.connect(str(cible))
    for nom in [*TABLES, "predictions_facteurs"]:
        df = source.execute(f"select * from {nom}").df()
        sortie.register("t", df)
        sortie.execute(f"create table {nom} as select * from t")
        sortie.unregister("t")
        print(f"  {nom} : {len(df):,} lignes")
    sortie.execute("checkpoint")
    sortie.close()
    metriques = REPORTS_DIR / "metriques_modele.json"
    if metriques.exists():
        shutil.copy(metriques, DOSSIER / "metriques_modele.json")
    exemples = ROOT_DIR / "docs" / "fiches_exemples.json"
    if exemples.exists():
        fiches = json.loads(exemples.read_text(encoding="utf-8"))
        valides = {f["faits"]["commune"]: f for f in fiches if f.get("valide")}
        (DOSSIER / "fiches_exemples.json").write_text(json.dumps(valides, ensure_ascii=False), encoding="utf-8")
    print(f"Export : {cible} ({cible.stat().st_size / 1e6:.1f} Mo)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

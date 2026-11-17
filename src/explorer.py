"""Étape 1 bis — Exploration : chiffres clés pour tester les hypothèses du journal.

Lit data/processed/ et écrit reports/exploration.md.

Usage :
    python src/explorer.py
"""

import sys

import pandas as pd

from config import PROCESSED_DIR, REPORTS_DIR


def tableau(df: pd.DataFrame) -> str:
    entete = "| " + " | ".join(map(str, df.columns)) + " |"
    sep = "|" + "|".join("---" for _ in df.columns) + "|"
    lignes = ["| " + " | ".join(map(str, r)) + " |" for r in df.itertuples(index=False)]
    return "\n".join([entete, sep, *lignes])


def main() -> int:
    chemin = PROCESSED_DIR / "catnat.parquet"
    if not chemin.exists():
        print("Lancez d'abord src/clean.py", file=sys.stderr)
        return 1
    cat = pd.read_parquet(chemin)
    if "evenement_repete" in cat.columns:          # un événement = une ligne
        cat = cat[~cat["evenement_repete"]]
    communes = pd.read_parquet(PROCESSED_DIR / "communes.parquet")
    md = ["# Exploration des données CatNat", "",
          f"_Généré par `src/explorer.py` le {pd.Timestamp.today():%d/%m/%Y} "
          f"sur {len(cat):,} événements reconnus (distincts)._", ""]

    # Reconnaissances par année d'événement (les années récentes sont-elles complètes ?)
    par_an = cat.groupby("annee").size()
    recent = par_an.loc[par_an.index >= par_an.index.max() - 9].reset_index()
    recent.columns = ["Année de l'événement", "Reconnaissances"]
    md += ["## Reconnaissances par année d'événement (10 dernières années)", "", tableau(recent), ""]
    if "date_arrete" in cat.columns:
        delai = (pd.to_datetime(cat["date_arrete"]) - pd.to_datetime(cat["date_debut"])).dt.days
        md += [f"Délai médian entre le début de l'événement et l'arrêté : **{delai.median():.0f} jours** "
               f"(90 % des arrêtés en moins de {delai.quantile(0.9):.0f} jours).", ""]

    # H1 — part de la sécheresse par période
    periodes = pd.cut(cat["annee"].astype(int), bins=[1981, 1999, 2014, 2100],
                      labels=["1982-1999", "2000-2014", "2015 et après"])
    part = (cat.assign(periode=periodes)
               .groupby("periode", observed=True)["famille_peril"]
               .value_counts(normalize=True).unstack(fill_value=0).mul(100).round(1))
    part = part.reset_index().rename(columns={"periode": "Période"})
    md += ["## H1 — Répartition des familles de périls par période (%)", "", tableau(part), ""]

    # H2 — concentration
    par_commune = cat.groupby("code_insee").size().sort_values(ascending=False)
    n_touchees = len(par_commune)
    top10 = par_commune.head(max(1, n_touchees // 10)).sum() / par_commune.sum()
    jamais = 1 - communes["code_insee"].isin(par_commune.index).mean()
    md += ["## H2 — Concentration des reconnaissances", "",
           f"- Communes ayant eu au moins une reconnaissance depuis 1982 : **{n_touchees:,}** "
           f"(**{1 - jamais:.1%}** des communes actuelles).",
           f"- Les 10 % de communes les plus touchées concentrent **{top10:.1%}** des reconnaissances.",
           f"- Nombre médian de reconnaissances par commune touchée : **{par_commune.median():.0f}** ; "
           f"maximum : **{par_commune.max()}**.", ""]
    top = (par_commune.head(10).rename("Reconnaissances").reset_index()
           .merge(communes[["code_insee", "nom_commune", "nom_departement"]], on="code_insee", how="left")
           [["nom_commune", "nom_departement", "Reconnaissances"]])
    md += ["Communes les plus touchées :", "", tableau(top), ""]

    # Libellés classés « autre » : la classification est-elle complète ?
    autres = cat.loc[cat["famille_peril"].isin(["autre", "inconnu"]), "libelle_peril"]
    autres = autres.value_counts().head(15).rename("Reconnaissances").reset_index()
    autres.columns = ["Libellé classé « autre »", "Reconnaissances"]
    md += ["## Contrôle de la classification : libellés classés « autre »", "", tableau(autres), ""]

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "exploration.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    sys.exit(main())

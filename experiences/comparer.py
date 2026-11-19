"""Essais de modélisation (branche « experiences », jamais fusionnée telle quelle).

Chaque configuration est évaluée sur la VALIDATION (seul critère de choix) et sur le TEST
(affiché pour mémoire). Variables « à date » : n'utilisent que les arrêtés déjà signés au
1er janvier de l'année prédite, comme en conditions réelles.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import modele as m  # noqa: E402
from config import PROCESSED_DIR  # noqa: E402

df = m.charger()
cat = pd.read_parquet(PROCESSED_DIR / "catnat.parquet")
cat = cat[~cat["evenement_repete"] & cat["commune_actuelle"]]
cat = cat[cat["famille_peril"].isin(["inondation", "secheresse"])]
cat["annee_arrete"] = pd.to_datetime(cat["date_arrete"]).dt.year
print("Part des événements de l'année t-1 déjà reconnus au 1er janvier de t :")
for f, g in cat.groupby("famille_peril"):
    print(f"  {f}: {(g['annee_arrete'] <= g['annee']).mean():.1%}")

# Variables à date : événements des années [t-k, t-1] dont l'arrêté est signé avant l'année t
def variables_a_date(df, cat):
    sortie = []
    for f in ("inondation", "secheresse"):
        e = cat[cat["famille_peril"] == f][["code_insee", "annee", "annee_arrete"]]
        g = df[df["famille_peril"] == f][["code_insee", "annee"]].drop_duplicates()
        j = g.merge(e, on="code_insee", how="left", suffixes=("", "_evt"))
        connu = (j["annee_evt"] < j["annee"]) & (j["annee_arrete"] < j["annee"])
        j = j[connu]
        age = j["annee"] - j["annee_evt"]
        agg = pd.DataFrame({
            "code_insee": j["code_insee"], "annee": j["annee"],
            "pit_1an": (age == 1).astype(int), "pit_5ans": (age <= 5).astype(int),
            "pit_10ans": (age <= 10).astype(int), "pit_total": 1, "pit_derniere": j["annee_evt"],
        }).groupby(["code_insee", "annee"]).agg(
            {"pit_1an": "sum", "pit_5ans": "sum", "pit_10ans": "sum", "pit_total": "sum", "pit_derniere": "max"})
        agg = g.merge(agg.reset_index(), on=["code_insee", "annee"], how="left")
        agg["famille_peril"] = f
        sortie.append(agg)
    pit = pd.concat(sortie)
    out = df.merge(pit, on=["code_insee", "annee", "famille_peril"], how="left")
    for c in ("pit_1an", "pit_5ans", "pit_10ans", "pit_total"):
        out[c] = out[c].fillna(0)
    out["nb_evt_1an"], out["nb_evt_5ans"], out["nb_evt_10ans"] = out["pit_1an"], out["pit_5ans"], out["pit_10ans"]
    out["taux_historique"] = out["pit_total"] / (out["annee"] - 1982)
    out["annees_depuis_derniere"] = out["annee"] - out["pit_derniere"]
    return out

pit = variables_a_date(df, cat)

PARAMS_BASE = dict(m.PARAMETRES)
PARAMS_REG = {**m.PARAMETRES, "num_leaves": 15, "min_child_samples": 1000, "learning_rate": 0.03,
              "lambda_l2": 10.0}

def evaluer_config(nom, data, famille, params, fenetre=None, variables=None):
    m.PARAMETRES = params
    vars_orig = m.VARIABLES
    if variables is not None:
        m.VARIABLES = {k: v for k, v in vars_orig.items() if k in variables}
    p = m.decouper(data, famille)
    train = p["entrainement"]
    if fenetre:
        train = train[train["annee"] > train["annee"].max() - fenetre]
    # validation : entraînement seul ; test : entraînement + validation, même nb d'arbres
    mod = m.entrainer_lgbm(train, p["validation"])
    v = m.evaluer(p["validation"]["cible"], mod.predict(p["validation"][list(m.VARIABLES)],
                  num_iteration=mod.best_iteration), p["validation"]["annee"])
    tv = pd.concat([train, p["validation"]])
    if fenetre:
        tv = tv[tv["annee"] > tv["annee"].max() - fenetre]
    final = m.entrainer_lgbm(tv, n_arbres=max(mod.best_iteration, 50))
    t = m.evaluer(p["test"]["cible"], final.predict(p["test"][list(m.VARIABLES)]), p["test"]["annee"])
    print(f"  {nom:<38} VALID auc {v['auc_moyen_par_annee']:.3f} top10 {v['top10_moyen_par_annee']:.1%}"
          f" | test auc {t['auc_moyen_par_annee']:.3f} top10 {t['top10_moyen_par_annee']:.1%} | arbres {mod.best_iteration}")
    m.PARAMETRES, m.VARIABLES = PARAMS_BASE, vars_orig
    return v, t

def references(nom, data, famille):
    p = m.decouper(data, famille)
    for jeu in ("validation", "test"):
        d = p[jeu]
        h = m.evaluer(d["cible"], m.reference_historique(d), d["annee"])
        tr = p["entrainement"] if jeu == "validation" else pd.concat([p["entrainement"], p["validation"]])
        lg = m.regression_logistique(tr)
        l = m.evaluer(d["cible"], lg.predict_proba(d[list(m.VARIABLES)])[:, 1], d["annee"])
        print(f"  [{nom}] {jeu:<10} historique auc {h['auc_moyen_par_annee']:.3f} top10 {h['top10_moyen_par_annee']:.1%}"
              f" | logistique auc {l['auc_moyen_par_annee']:.3f} top10 {l['top10_moyen_par_annee']:.1%}")

SANS_GEO = [v for v in m.VARIABLES if v not in ("latitude", "longitude")]
for famille in ("inondation", "secheresse"):
    print(f"\n===== {famille} (validation {m.DECOUPAGE[famille]['validation']}, test {m.DECOUPAGE[famille]['test']})")
    references("actuel", df, famille)
    references("à date", pit, famille)
    evaluer_config("A actuel", df, famille, PARAMS_BASE)
    evaluer_config("B régularisé", df, famille, PARAMS_REG)
    evaluer_config("C fenêtre 12 ans", df, famille, PARAMS_BASE, fenetre=12)
    evaluer_config("D régularisé + fenêtre 12 ans", df, famille, PARAMS_REG, fenetre=12)
    evaluer_config("E à date", pit, famille, PARAMS_BASE)
    evaluer_config("F à date + régularisé", pit, famille, PARAMS_REG)
    evaluer_config("G à date + régularisé + fenêtre 12", pit, famille, PARAMS_REG, fenetre=12)
    evaluer_config("H à date + régularisé, sans lat/long", pit, famille, PARAMS_REG, variables=SANS_GEO)

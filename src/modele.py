"""Étape 3 — Prédire la probabilité d'une reconnaissance CatNat par commune.

Un modèle par famille de péril (inondation, sécheresse) :
  1. découpage TEMPOREL : entraînement sur le passé, validation, puis test sur
     les années les plus récentes jamais vues par le modèle ;
  2. comparaison à deux références (historique de la commune, régression logistique) ;
  3. explications SHAP de chaque prédiction (TreeSHAP intégré à LightGBM) ;
  4. modèle final réentraîné sur toutes les années évaluables, puis prédiction de
     l'année suivante (annee_a_predire) pour chaque commune.

Lit la table mart_features_risque construite par dbt (data/processed/risque.duckdb).
Écrit reports/modele.md, reports/metriques_modele.json, reports/figures/*.png,
models/*.txt et data/processed/predictions.parquet.

Usage :
    python src/modele.py
"""

import json
import sys

import numpy as np
import pandas as pd

from config import PROCESSED_DIR, REPORTS_DIR, ROOT_DIR

ANNEE_DEBUT = 1982
FIGURES_DIR = REPORTS_DIR / "figures"
MODELS_DIR = ROOT_DIR / "models"

# Variables explicatives : calculées « à date », avec les seuls arrêtés signés avant le
# 1er janvier de l'année prédite (test dbt anti-fuite)
VARIABLES = {
    "nb_evt_1an": "Reconnaissances l'année précédente",
    "nb_evt_5ans": "Reconnaissances sur 5 ans",
    "nb_evt_10ans": "Reconnaissances sur 10 ans",
    "taux_historique": "Fréquence depuis 1982 (par an)",
    "annees_depuis_derniere": "Années depuis la dernière reconnaissance",
    "nb_evt_autres_perils_10ans": "Autres périls sur 10 ans",
    "taux_dept_5ans": "Fréquence dans le département (5 ans)",
    "population": "Population",
    "surface_km2": "Superficie (km²)",
    "densite_hab_km2": "Densité (hab./km²)",
    "latitude": "Latitude",
    "longitude": "Longitude",
}

# Découpage temporel. Les années de test respectent les fenêtres évaluables
# décidées à l'étape 1 (sécheresse : reconnaissances complètes jusqu'en 2021).
DECOUPAGE = {
    "inondation": {"entrainement": (1992, 2018), "validation": (2019, 2020), "test": (2021, 2024)},
    "secheresse": {"entrainement": (1992, 2014), "validation": (2015, 2016), "test": (2017, 2021)},
}

NOMS = {"inondation": "Inondation", "secheresse": "Sécheresse"}

PARAMETRES = {
    "objective": "binary", "learning_rate": 0.05, "num_leaves": 31, "min_child_samples": 200,
    "feature_fraction": 0.8, "bagging_fraction": 0.8, "bagging_freq": 1, "lambda_l2": 1.0,
    "verbose": -1, "seed": 42, "deterministic": True, "force_row_wise": True,
}


# --- Données ---------------------------------------------------------------------------
def charger() -> pd.DataFrame:
    import duckdb

    chemin = PROCESSED_DIR / "risque.duckdb"
    if not chemin.exists():
        sys.exit("Base dbt introuvable : lancez d'abord src/lancer_dbt.py local")
    with duckdb.connect(str(chemin), read_only=True) as con:
        df = con.sql("select * from mart_features_risque where historique_complet").df()
    manquantes = [v for v in VARIABLES if v != "taux_historique" and v not in df.columns]
    if manquantes:
        sys.exit(f"Colonnes absentes de la base dbt ({manquantes}) : relancez src/lancer_dbt.py local")
    return preparer(df)


def preparer(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Le total depuis 1982 grandit mécaniquement avec les années : on le ramène à une fréquence
    df["taux_historique"] = df["nb_evt_depuis_debut"] / (df["annee"] - ANNEE_DEBUT)
    for col in VARIABLES:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    df["cible"] = df["cible"].astype(int)
    return df


def decouper(df: pd.DataFrame, famille: str) -> dict[str, pd.DataFrame]:
    """Sépare les années sans recouvrement ; n'utilise que les années évaluables."""
    sous = df[(df["famille_peril"] == famille) & df["annee_evaluable"]]
    parts = {nom: sous[sous["annee"].between(debut, fin)]
             for nom, (debut, fin) in DECOUPAGE[famille].items()}
    annees = [set(p["annee"]) for p in parts.values()]
    assert not (annees[0] & annees[1] or annees[0] & annees[2] or annees[1] & annees[2])
    assert max(annees[0]) < min(annees[1]) and max(annees[1]) < min(annees[2]), "ordre temporel"
    return parts


# --- Évaluation ------------------------------------------------------------------------
def part_captee(y: np.ndarray, score: np.ndarray, part: float = 0.10) -> float:
    """Part des communes touchées qui figurent dans les `part` % de scores les plus élevés."""
    y, score = np.asarray(y), np.asarray(score)
    if y.sum() == 0:
        return float("nan")
    n = max(1, int(round(len(y) * part)))
    meilleurs = np.argsort(-score, kind="stable")[:n]
    return float(y[meilleurs].sum() / y.sum())


def evaluer(y, score, annees) -> dict:
    from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

    y, score, annees = np.asarray(y), np.asarray(score), np.asarray(annees)
    par_annee = {}
    for a in np.unique(annees):
        m = annees == a
        if 0 < y[m].sum() < m.sum():
            par_annee[int(a)] = {"auc": float(roc_auc_score(y[m], score[m])),
                                 "top10": part_captee(y[m], score[m]),
                                 "taux_reel": float(y[m].mean())}
    return {
        "auc": float(roc_auc_score(y, score)),
        "precision_moyenne": float(average_precision_score(y, score)),
        "brier": float(brier_score_loss(y, np.clip(score, 0, 1))),
        "auc_moyen_par_annee": float(np.mean([v["auc"] for v in par_annee.values()])),
        "top10_moyen_par_annee": float(np.mean([v["top10"] for v in par_annee.values()])),
        "taux_reel": float(y.mean()),
        "par_annee": par_annee,
    }


# --- Modèles ---------------------------------------------------------------------------
def reference_historique(df: pd.DataFrame) -> np.ndarray:
    """Référence naïve : une commune souvent touchée par le passé le sera encore."""
    return df["taux_historique"].fillna(0).to_numpy()


def regression_logistique(train: pd.DataFrame):
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import FunctionTransformer, StandardScaler

    signe_log = FunctionTransformer(lambda x: np.sign(x) * np.log1p(np.abs(x)))
    modele = make_pipeline(SimpleImputer(strategy="median", add_indicator=True), signe_log,
                           StandardScaler(), LogisticRegression(max_iter=2000))
    return modele.fit(train[list(VARIABLES)], train["cible"])


def entrainer_lgbm(train: pd.DataFrame, validation: pd.DataFrame | None = None, n_arbres: int = 2000):
    import lightgbm as lgb

    dtrain = lgb.Dataset(train[list(VARIABLES)], train["cible"], free_raw_data=False)
    if validation is None:
        return lgb.train(PARAMETRES, dtrain, num_boost_round=n_arbres)
    dval = lgb.Dataset(validation[list(VARIABLES)], validation["cible"], reference=dtrain)
    return lgb.train(PARAMETRES, dtrain, num_boost_round=n_arbres, valid_sets=[dval],
                     callbacks=[lgb.early_stopping(50, verbose=False)])


def contributions_shap(modele, X: pd.DataFrame) -> pd.DataFrame:
    """Valeurs SHAP exactes (TreeSHAP) en log-odds ; la dernière colonne est la valeur de base."""
    valeurs = modele.predict(X[list(VARIABLES)], pred_contrib=True)
    return pd.DataFrame(valeurs, columns=[*VARIABLES, "valeur_de_base"], index=X.index)


def principaux_facteurs(shap: pd.DataFrame, X: pd.DataFrame, n: int = 3) -> pd.DataFrame:
    """Les n variables qui pèsent le plus (en valeur absolue) dans chaque prédiction."""
    contrib = shap[list(VARIABLES)]
    ordre = np.argsort(-contrib.abs().to_numpy(), axis=1)[:, :n]
    noms = np.array(list(VARIABLES))
    sortie = {}
    for k in range(n):
        cols = noms[ordre[:, k]]
        sortie[f"facteur_{k + 1}"] = cols
        sortie[f"contribution_{k + 1}"] = contrib.to_numpy()[np.arange(len(contrib)), ordre[:, k]]
        sortie[f"valeur_{k + 1}"] = X[list(VARIABLES)].to_numpy()[np.arange(len(X)), ordre[:, k]]
    return pd.DataFrame(sortie, index=X.index)


# --- Rapport ---------------------------------------------------------------------------
def figures(resultats: dict, importances: dict, calibrations: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    couleurs = {"LightGBM": "#2a6f97", "Régression logistique": "#e09f3e", "Historique de la commune": "#9e9e9e"}
    familles = list(resultats)

    fig, axes = plt.subplots(1, len(familles), figsize=(11, 4), sharey=True)
    for ax, famille in zip(np.atleast_1d(axes), familles):
        for nom, res in resultats[famille].items():
            annees = sorted(res["par_annee"])
            ax.plot(annees, [res["par_annee"][a]["auc"] for a in annees], marker="o",
                    label=nom, color=couleurs[nom])
        ax.set_title(f"{NOMS[famille]} : AUC par année de test")
        ax.set_xticks(sorted(next(iter(resultats[famille].values()))["par_annee"]))
        ax.set_xlabel("Année")
        ax.grid(alpha=0.3)
    np.atleast_1d(axes)[0].set_ylabel("AUC (0,5 = hasard)")
    np.atleast_1d(axes)[0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "auc_par_annee.png", dpi=150)
    plt.close(fig)

    fig, axes = plt.subplots(1, len(familles), figsize=(12, 4.5))
    for ax, famille in zip(np.atleast_1d(axes), familles):
        imp = importances[famille].sort_values()
        ax.barh([VARIABLES[v] for v in imp.index], imp.to_numpy(), color="#2a6f97")
        ax.set_title(f"{NOMS[famille]} : importance des variables")
        ax.set_xlabel("|SHAP| moyen (log-odds)")
        ax.tick_params(axis="y", labelsize=8)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "importance_shap.png", dpi=150)
    plt.close(fig)

    fig, axes = plt.subplots(1, len(familles), figsize=(9, 4))
    for ax, famille in zip(np.atleast_1d(axes), familles):
        predit, observe = calibrations[famille]
        limite = max(predit.max(), observe.max()) * 1.1
        ax.plot([0, limite], [0, limite], "--", color="#bbb", label="Calibration parfaite")
        ax.plot(predit, observe, marker="o", color="#2a6f97", label="LightGBM")
        ax.set_xlim(0, limite)
        ax.set_ylim(0, limite)
        ax.set_title(f"{NOMS[famille]} : calibration (test)")
        ax.set_xlabel("Probabilité prédite")
        ax.set_ylabel("Fréquence observée")
        ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "calibration.png", dpi=150)
    plt.close(fig)


def rapport(resultats: dict, validations: dict, importances: dict, infos: dict) -> str:
    md = ["# Modèle de prédiction des reconnaissances CatNat", "",
          f"_Généré par `src/modele.py` le {pd.Timestamp.today():%d/%m/%Y}._", "",
          "Un modèle par famille de péril, évalué sur des années **jamais vues** à l'entraînement. "
          "Scores moyens par année (le niveau de risque global d'une année dépend de sa météo, "
          "que le modèle ne connaît pas : il s'agit de **classer** les communes au sein d'une année). "
          "L'AUC mesure la capacité à classer les communes (0,5 = hasard, 1 = parfait) ; "
          "« Top 10 % » est la part des communes réellement touchées que l'on trouve parmi "
          "les 10 % de communes jugées les plus à risque.", ""]
    for famille, res in resultats.items():
        i = infos[famille]
        md += [f"## {NOMS[famille]}", "",
               f"- Entraînement {i['entrainement']}, validation {i['validation']}, test {i['test']}.",
               f"- {i['n_train']:,} lignes d'entraînement, {i['n_test']:,} lignes de test ; "
               f"{i['arbres']} arbres retenus (arrêt anticipé sur la validation).", "",
               "| Modèle | AUC validation | AUC test | Top 10 % validation | Top 10 % test | Brier test |",
               "|---|---:|---:|---:|---:|---:|"]
        for nom, r in res.items():
            v = validations[famille][nom]
            md.append(f"| {nom} | {v['auc_moyen_par_annee']:.3f} | {r['auc_moyen_par_annee']:.3f} | "
                      f"{v['top10_moyen_par_annee']:.1%} | {r['top10_moyen_par_annee']:.1%} | {r['brier']:.4f} |")
        md += ["", "_Le choix du modèle se fait sur la validation ; le test, jamais utilisé pour "
               "décider, mesure la performance attendue sur des années nouvelles._"]
        lgbm = res["LightGBM"]["par_annee"]
        md += ["", "| Année de test | Communes touchées | AUC | Top 10 % |", "|---|---:|---:|---:|"]
        md += [f"| {a} | {v['taux_reel']:.1%} | {v['auc']:.3f} | {v['top10']:.1%} |" for a, v in lgbm.items()]
        imp = importances[famille].sort_values(ascending=False).head(5)
        md += ["", "Variables les plus influentes (SHAP) : "
               + ", ".join(f"{VARIABLES[v]} ({x:.2f})" for v, x in imp.items()) + ".", ""]
    md += ["![AUC par année](figures/auc_par_annee.png)", "",
           "![Importance SHAP](figures/importance_shap.png)", "",
           "![Calibration](figures/calibration.png)", ""]
    return "\n".join(md)


# --- Programme principal ---------------------------------------------------------------
def main() -> int:
    from sklearn.calibration import calibration_curve

    df = charger()
    resultats, validations, importances, calibrations, infos, predictions = {}, {}, {}, {}, {}, []
    MODELS_DIR.mkdir(exist_ok=True)

    for famille in DECOUPAGE:
        print(f"\n== {famille}")
        parts = decouper(df, famille)
        train, val, test = parts["entrainement"], parts["validation"], parts["test"]
        y, annees = test["cible"].to_numpy(), test["annee"].to_numpy()

        # 1. Validation (SEUL critère de choix) : modèles entraînés sur l'entraînement seul
        lgbm = entrainer_lgbm(train, val)
        logit_val = regression_logistique(train)
        scores_val = {
            "LightGBM": lgbm.predict(val[list(VARIABLES)], num_iteration=lgbm.best_iteration),
            "Régression logistique": logit_val.predict_proba(val[list(VARIABLES)])[:, 1],
            "Historique de la commune": reference_historique(val),
        }
        validations[famille] = {nom: evaluer(val["cible"], s, val["annee"]) for nom, s in scores_val.items()}

        # 2. Test : modèles réentraînés sur entraînement + validation, évalués une seule fois
        anterieur = pd.concat([train, val])
        lgbm_test = entrainer_lgbm(anterieur, n_arbres=max(lgbm.best_iteration, 50))
        logit = regression_logistique(anterieur)
        scores = {
            "LightGBM": lgbm_test.predict(test[list(VARIABLES)]),
            "Régression logistique": logit.predict_proba(test[list(VARIABLES)])[:, 1],
            "Historique de la commune": reference_historique(test),
        }
        resultats[famille] = {nom: evaluer(y, s, annees) for nom, s in scores.items()}
        for nom, r in resultats[famille].items():
            v = validations[famille][nom]
            print(f"  {nom:<26} validation AUC/an {v['auc_moyen_par_annee']:.3f} top10 {v['top10_moyen_par_annee']:.1%}"
                  f" | test AUC/an {r['auc_moyen_par_annee']:.3f} top10 {r['top10_moyen_par_annee']:.1%}")

        shap = contributions_shap(lgbm_test, test)
        importances[famille] = shap[list(VARIABLES)].abs().mean()
        calibrations[famille] = calibration_curve(y, scores["LightGBM"], n_bins=10, strategy="quantile")[::-1]
        infos[famille] = {**{k: f"{a}-{b}" for k, (a, b) in DECOUPAGE[famille].items()},
                          "n_train": len(train), "n_test": len(test), "arbres": lgbm.best_iteration}

        # Modèle final : toutes les années évaluables, même nombre d'arbres
        complet = df[(df["famille_peril"] == famille) & df["annee_evaluable"]]
        final = entrainer_lgbm(complet, n_arbres=max(lgbm.best_iteration, 50))
        final.save_model(str(MODELS_DIR / f"lgbm_{famille}.txt"))
        a_predire = df[(df["famille_peril"] == famille) & df["annee_a_predire"]]
        sortie = a_predire[["code_insee", "code_departement", "annee", "famille_peril"]].copy()
        sortie["probabilite"] = final.predict(a_predire[list(VARIABLES)])
        sortie["percentile_national"] = sortie["probabilite"].rank(pct=True)
        shap_pred = contributions_shap(final, a_predire)
        sortie = sortie.join(principaux_facteurs(shap_pred, a_predire))
        predictions.append(sortie)
        print(f"  prédictions {int(sortie['annee'].iloc[0]) if len(sortie) else '-'} : {len(sortie):,} communes")

    pd.concat(predictions).to_parquet(PROCESSED_DIR / "predictions.parquet", index=False)
    figures(resultats, importances, calibrations)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "metriques_modele.json").write_text(json.dumps(
        {"resultats": resultats, "validations": validations, "infos": infos,
         "importances": {f: imp.round(4).to_dict() for f, imp in importances.items()},
         "calibrations": {f: {"predit": list(map(float, p)), "observe": list(map(float, o))}
                          for f, (p, o) in calibrations.items()}},
        indent=2, ensure_ascii=False), encoding="utf-8")
    (REPORTS_DIR / "modele.md").write_text(rapport(resultats, validations, importances, infos), encoding="utf-8")
    print("\nTerminé : reports/modele.md, reports/figures/, data/processed/predictions.parquet")
    return 0


if __name__ == "__main__":
    sys.exit(main())

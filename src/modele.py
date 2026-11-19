"""Étape 3 — Prédire le risque de reconnaissance CatNat par commune, à 1, 3 et 5 ans.

Pour chaque famille de péril (inondation, sécheresse) et chaque horizon h, la cible est
« au moins une reconnaissance entre l'année t et l'année t + h - 1 », prédite avec ce
qui était connu au 1er janvier de l'année t.

  1. Découpage TEMPOREL sans chevauchement des fenêtres de cible : entraînement,
     validation (seul critère de choix), test sur des années jamais vues.
  2. Comparaison à deux références : historique de la commune, régression logistique.
  3. Calibration : le modèle apprend sur des années anciennes, alors que le risque
     évolue (la sécheresse progresse). Ses probabilités sont donc recalées (méthode de
     Platt) sur les années les plus récentes ; le classement des communes ne change pas.
  4. Explications SHAP exactes (TreeSHAP intégré à LightGBM).
  5. Production : même schéma décalé sur les dernières années disponibles, puis
     prédiction pour l'année suivante (annee_a_predire).

Lit mart_features_risque (dbt, data/processed/risque.duckdb). Écrit reports/modele.md,
reports/metriques_modele.json, reports/figures/*.png, models/*.txt et
data/processed/predictions.parquet.

Usage :
    python src/modele.py
"""

import json
import sys

import numpy as np
import pandas as pd

from config import PROCESSED_DIR, REPORTS_DIR, ROOT_DIR

ANNEE_DEBUT = 1982
DEBUT_ENTRAINEMENT = 1992          # 10 ans d'historique disponibles
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
# Exposition physique (zonage argiles BRGM) : utilisée si dbt la fournit
VARIABLES_EXPOSITION = {
    "part_argile_fort": "Part de la commune en exposition argile forte",
    "part_argile_moyen": "Part de la commune en exposition argile moyenne",
    "part_argile_faible": "Part de la commune en exposition argile faible",
}

HORIZONS = (1, 3, 5)
NOMS = {"inondation": "Inondation", "secheresse": "Sécheresse"}
# Dernière année dont les reconnaissances sont complètes (étape 1)
DERNIERE_ANNEE_EVALUABLE = {"inondation": 2024, "secheresse": 2021}
# Horizon 1 an : découpage historique (étape 3, version 1), conservé tel quel
DECOUPAGE_1AN = {
    "inondation": {"entrainement": (DEBUT_ENTRAINEMENT, 2018), "validation": (2019, 2020), "test": (2021, 2024)},
    "secheresse": {"entrainement": (DEBUT_ENTRAINEMENT, 2014), "validation": (2015, 2016), "test": (2017, 2021)},
}
ANNEES_TEST, ANNEES_VALIDATION = 3, 2     # horizons 3 et 5 ans

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
    attendues = [v for v in VARIABLES if v != "taux_historique"] + ["cible_3ans", "cible_5ans"]
    manquantes = [v for v in attendues if v not in df.columns]
    if manquantes:
        sys.exit(f"Colonnes absentes de la base dbt ({manquantes}) : relancez src/lancer_dbt.py local")
    return preparer(df)


def variables(df: pd.DataFrame) -> dict[str, str]:
    """Variables du modèle : l'exposition physique n'est ajoutée que si elle existe."""
    return {**VARIABLES, **{k: v for k, v in VARIABLES_EXPOSITION.items() if k in df.columns}}


def preparer(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Le total depuis 1982 grandit mécaniquement avec les années : on le ramène à une fréquence
    df["taux_historique"] = df["nb_evt_depuis_debut"] / (df["annee"] - ANNEE_DEBUT)
    for col in variables(df):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    for h, (cible, _) in colonnes_horizon().items():
        if cible in df.columns:
            df[cible] = df[cible].astype(int)
    return df


def colonnes_horizon() -> dict[int, tuple[str, str]]:
    return {1: ("cible", "annee_evaluable"), 3: ("cible_3ans", "annee_evaluable_3ans"),
            5: ("cible_5ans", "annee_evaluable_5ans")}


def periodes(famille: str, horizon: int) -> dict[str, tuple[int, int]]:
    """Années de DÉBUT de fenêtre pour chaque partie. Une fenêtre de h ans démarrant en t
    couvre t..t+h-1 : les fenêtres d'entraînement se terminent avant la validation, celles
    de validation avant le test, pour qu'aucune année de cible ne soit partagée."""
    if horizon == 1:
        return DECOUPAGE_1AN[famille]
    fin_test = DERNIERE_ANNEE_EVALUABLE[famille] - horizon + 1
    debut_test = fin_test - ANNEES_TEST + 1
    fin_val = debut_test - horizon
    debut_val = fin_val - ANNEES_VALIDATION + 1
    return {"entrainement": (DEBUT_ENTRAINEMENT, debut_val - horizon),
            "validation": (debut_val, fin_val), "test": (debut_test, fin_test)}


def periodes_production(famille: str, horizon: int) -> dict[str, tuple[int, int]]:
    """Même schéma, décalé sur les années les plus récentes : la calibration se fait sur les
    deux dernières fenêtres complètes, le modèle apprend sur tout ce qui précède."""
    fin_cal = DERNIERE_ANNEE_EVALUABLE[famille] - horizon + 1
    debut_cal = fin_cal - ANNEES_VALIDATION + 1
    return {"entrainement": (DEBUT_ENTRAINEMENT, debut_cal - horizon), "validation": (debut_cal, fin_cal)}


def decouper(df: pd.DataFrame, famille: str, horizon: int = 1, production: bool = False) -> dict[str, pd.DataFrame]:
    """Sépare les lignes par années de début de fenêtre ; colonne « y » = cible de l'horizon."""
    cible, evaluable = colonnes_horizon()[horizon]
    sous = df[(df["famille_peril"] == famille) & df[evaluable]].assign(y=lambda d: d[cible])
    bornes = periodes_production(famille, horizon) if production else periodes(famille, horizon)
    parts = {nom: sous[sous["annee"].between(a, b)] for nom, (a, b) in bornes.items()}
    noms = list(bornes)
    for avant, apres in zip(noms, noms[1:]):
        fin_fenetre = bornes[avant][1] + horizon - 1
        assert fin_fenetre < bornes[apres][0], f"chevauchement {avant}/{apres} (h={horizon})"
        assert len(parts[avant]) and len(parts[apres]), f"partie vide (h={horizon})"
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
                                 "taux_reel": float(y[m].mean()), "taux_predit": float(score[m].mean())}
    return {
        "auc": float(roc_auc_score(y, score)),
        "precision_moyenne": float(average_precision_score(y, score)),
        "brier": float(brier_score_loss(y, np.clip(score, 0, 1))),
        "auc_moyen_par_annee": float(np.mean([v["auc"] for v in par_annee.values()])),
        "top10_moyen_par_annee": float(np.mean([v["top10"] for v in par_annee.values()])),
        "taux_reel": float(y.mean()), "taux_predit": float(np.mean(score)),
        "par_annee": par_annee,
    }


# --- Modèles ---------------------------------------------------------------------------
def reference_historique(df: pd.DataFrame) -> np.ndarray:
    """Référence naïve : une commune souvent touchée par le passé le sera encore."""
    return df["taux_historique"].fillna(0).to_numpy()


def regression_logistique(train: pd.DataFrame, noms: list[str]):
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import FunctionTransformer, StandardScaler

    signe_log = FunctionTransformer(lambda x: np.sign(x) * np.log1p(np.abs(x)))
    modele = make_pipeline(SimpleImputer(strategy="median", add_indicator=True), signe_log,
                           StandardScaler(), LogisticRegression(max_iter=2000))
    return modele.fit(train[noms], train["y"])


def entrainer_lgbm(train: pd.DataFrame, validation: pd.DataFrame | None, noms: list[str], n_arbres: int = 2000):
    import lightgbm as lgb

    dtrain = lgb.Dataset(train[noms], train["y"], free_raw_data=False)
    if validation is None:
        return lgb.train(PARAMETRES, dtrain, num_boost_round=n_arbres)
    dval = lgb.Dataset(validation[noms], validation["y"], reference=dtrain)
    return lgb.train(PARAMETRES, dtrain, num_boost_round=n_arbres, valid_sets=[dval],
                     callbacks=[lgb.early_stopping(50, verbose=False)])


class Calibrateur:
    """Recalage de Platt : logit(p) = a + b * score brut (log-odds). Ne change pas le
    classement ; ajuste le niveau (a) et l'étalement (b) des probabilités."""

    def __init__(self, score_brut: np.ndarray, y: np.ndarray):
        from sklearn.linear_model import LogisticRegression

        reg = LogisticRegression(C=1e6, max_iter=1000).fit(np.asarray(score_brut).reshape(-1, 1), y)
        self.a, self.b = float(reg.intercept_[0]), float(reg.coef_[0, 0])

    def __call__(self, score_brut: np.ndarray) -> np.ndarray:
        return 1 / (1 + np.exp(-(self.a + self.b * np.asarray(score_brut))))


def contributions_shap(modele, X: pd.DataFrame, noms: list[str]) -> pd.DataFrame:
    """Valeurs SHAP exactes (TreeSHAP) en log-odds ; la dernière colonne est la valeur de base."""
    valeurs = modele.predict(X[noms], pred_contrib=True)
    return pd.DataFrame(valeurs, columns=[*noms, "valeur_de_base"], index=X.index)


def principaux_facteurs(shap: pd.DataFrame, X: pd.DataFrame, noms: list[str], n: int = 3) -> pd.DataFrame:
    """Les n variables qui pèsent le plus (en valeur absolue) dans chaque prédiction."""
    contrib = shap[noms].to_numpy()
    ordre = np.argsort(-np.abs(contrib), axis=1)[:, :n]
    lignes = np.arange(len(contrib))[:, None]
    sortie = {}
    for k in range(n):
        sortie[f"facteur_{k + 1}"] = np.array(noms)[ordre[:, k]]
        sortie[f"contribution_{k + 1}"] = contrib[lignes[:, 0], ordre[:, k]]
        sortie[f"valeur_{k + 1}"] = X[noms].to_numpy()[lignes[:, 0], ordre[:, k]]
    return pd.DataFrame(sortie, index=X.index)


# --- Une famille, un horizon -----------------------------------------------------------
def evaluer_famille_horizon(df: pd.DataFrame, famille: str, h: int, noms: list[str]) -> dict:
    from sklearn.calibration import calibration_curve

    p = decouper(df, famille, h)
    train, val, test = p["entrainement"], p["validation"], p["test"]

    lgbm = entrainer_lgbm(train, val, noms)
    logit = regression_logistique(train, noms)
    brut = {nom: lgbm.predict(d[noms], num_iteration=lgbm.best_iteration, raw_score=True)
            for nom, d in (("val", val), ("test", test))}
    calib = Calibrateur(brut["val"], val["y"])
    proba_brute = {k: 1 / (1 + np.exp(-v)) for k, v in brut.items()}

    resultats = {}
    for jeu, d in (("validation", val), ("test", test)):
        k = "val" if jeu == "validation" else "test"
        scores = {"LightGBM": proba_brute[k],
                  "Régression logistique": logit.predict_proba(d[noms])[:, 1],
                  "Historique de la commune": reference_historique(d)}
        resultats[jeu] = {nom: evaluer(d["y"], s, d["annee"]) for nom, s in scores.items()}
    resultats["test_calibre"] = evaluer(test["y"], calib(brut["test"]), test["annee"])

    # Apport de l'exposition physique : même modèle, sans ces variables (décision sur la validation)
    sans = [n for n in noms if n not in VARIABLES_EXPOSITION]
    if len(sans) < len(noms):
        lgbm_sans = entrainer_lgbm(train, val, sans)
        resultats["sans_exposition"] = {
            jeu: evaluer(d["y"], lgbm_sans.predict(d[sans], num_iteration=lgbm_sans.best_iteration), d["annee"])
            for jeu, d in (("validation", val), ("test", test))}

    shap = contributions_shap(lgbm, test, noms)
    courbes = {}
    for nom, s in (("brut", proba_brute["test"]), ("calibre", calib(brut["test"]))):
        obs, pred = calibration_curve(test["y"], s, n_bins=10, strategy="quantile")
        courbes[nom] = {"predit": pred.tolist(), "observe": obs.tolist()}
    return {
        "periodes": {k: f"{a}-{b}" for k, (a, b) in periodes(famille, h).items()},
        "n_train": len(train), "n_test": len(test), "arbres": lgbm.best_iteration,
        "calibrateur": {"a": calib.a, "b": calib.b},
        "resultats": resultats,
        "importances": shap[noms].abs().mean().round(4).to_dict(),
        "calibration": courbes,
    }


def produire(df: pd.DataFrame, famille: str, h: int, noms: list[str]) -> pd.DataFrame:
    """Modèle de production : appris sur les années anciennes, recalé sur les plus récentes."""
    p = decouper(df, famille, h, production=True)
    modele = entrainer_lgbm(p["entrainement"], p["validation"], noms)
    calib = Calibrateur(modele.predict(p["validation"][noms], num_iteration=modele.best_iteration,
                                       raw_score=True), p["validation"]["y"])
    modele.save_model(str(MODELS_DIR / f"lgbm_{famille}_{h}an{'s' if h > 1 else ''}.txt"),
                      num_iteration=modele.best_iteration)
    a_predire = df[(df["famille_peril"] == famille) & df["annee_a_predire"]]
    brut = modele.predict(a_predire[noms], num_iteration=modele.best_iteration, raw_score=True)
    sortie = a_predire[["code_insee", "code_departement", "annee", "famille_peril"]].copy()
    sortie["horizon_ans"] = h
    sortie["probabilite"] = calib(brut)
    sortie["percentile_national"] = sortie["probabilite"].rank(pct=True)
    shap = contributions_shap(modele, a_predire, noms) * calib.b      # log-odds recalés
    return sortie.join(principaux_facteurs(shap, a_predire, noms))


# --- Rapport ---------------------------------------------------------------------------
def figures(metriques: dict, libelles: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    couleurs = {"LightGBM": "#2a6f97", "Régression logistique": "#e09f3e", "Historique de la commune": "#9e9e9e"}
    familles = list(metriques)

    # 1. AUC de test par horizon
    fig, axes = plt.subplots(1, len(familles), figsize=(11, 4), sharey=True)
    largeur = 0.26
    for ax, famille in zip(np.atleast_1d(axes), familles):
        hs = sorted(metriques[famille], key=int)
        for i, nom in enumerate(couleurs):
            vals = [metriques[famille][h]["resultats"]["test"][nom]["auc_moyen_par_annee"] for h in hs]
            ax.bar(np.arange(len(hs)) + (i - 1) * largeur, vals, largeur, label=nom, color=couleurs[nom])
        ax.set_xticks(range(len(hs)), [f"{h} an{'s' if int(h) > 1 else ''}" for h in hs])
        ax.set_ylim(0.5, 1)
        ax.set_title(f"{NOMS[famille]} : AUC de test par horizon")
        ax.grid(axis="y", alpha=0.3)
    np.atleast_1d(axes)[0].set_ylabel("AUC (0,5 = hasard)")
    np.atleast_1d(axes)[0].legend(fontsize=8, loc="upper left")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "auc_par_horizon.png", dpi=150)
    plt.close(fig)

    # 2. Importance des variables (horizon 1 an)
    fig, axes = plt.subplots(1, len(familles), figsize=(12, 5))
    for ax, famille in zip(np.atleast_1d(axes), familles):
        imp = pd.Series(metriques[famille][next(iter(metriques[famille]))]["importances"]).sort_values()
        ax.barh([libelles.get(v, v) for v in imp.index], imp.to_numpy(), color="#2a6f97")
        ax.set_title(f"{NOMS[famille]} (1 an) : importance des variables")
        ax.set_xlabel("|SHAP| moyen (log-odds)")
        ax.tick_params(axis="y", labelsize=8)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "importance_shap.png", dpi=150)
    plt.close(fig)

    # 3. Calibration avant / après recalage (horizon 1 an)
    fig, axes = plt.subplots(1, len(familles), figsize=(10, 4.2))
    for ax, famille in zip(np.atleast_1d(axes), familles):
        courbes = metriques[famille][next(iter(metriques[famille]))]["calibration"]
        limite = max(max(c["predit"] + c["observe"]) for c in courbes.values()) * 1.1
        ax.plot([0, limite], [0, limite], "--", color="#bbb", label="Calibration parfaite")
        for nom, couleur, label in (("brut", "#9e9e9e", "Avant recalage"), ("calibre", "#2a6f97", "Après recalage")):
            ax.plot(courbes[nom]["predit"], courbes[nom]["observe"], marker="o", color=couleur, label=label)
        ax.set_xlim(0, limite)
        ax.set_ylim(0, limite)
        ax.set_title(f"{NOMS[famille]} (1 an) : calibration en test")
        ax.set_xlabel("Probabilité prédite")
        ax.set_ylabel("Fréquence observée")
        ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "calibration.png", dpi=150)
    plt.close(fig)


def rapport(metriques: dict, libelles: dict) -> str:
    md = ["# Modèle de prédiction des reconnaissances CatNat", "",
          f"_Généré par `src/modele.py` le {pd.Timestamp.today():%d/%m/%Y}._", "",
          "Cible : au moins une reconnaissance CatNat dans les **1, 3 ou 5 ans** qui suivent le "
          "1er janvier. Scores moyens par année de départ : il s'agit de **classer** les communes. "
          "« Top 10 % » : part des communes touchées trouvées parmi les 10 % jugées les plus à risque "
          "(un tirage au hasard en trouve 10 %). Le choix se fait sur la validation ; le test n'est "
          "utilisé qu'une fois.", ""]
    for famille, par_h in metriques.items():
        md += [f"## {NOMS[famille]}", ""]
        for h, m in par_h.items():
            r, v, c = m["resultats"]["test"], m["resultats"]["validation"], m["resultats"]["test_calibre"]
            per = m["periodes"]
            md += [f"### Horizon {h} an{'s' if int(h) > 1 else ''}", "",
                   f"Entraînement {per['entrainement']}, validation {per['validation']}, test {per['test']} "
                   f"(années de départ) ; {m['n_train']:,} lignes d'entraînement, {m['arbres']} arbres. "
                   f"Communes touchées en test : {r['LightGBM']['taux_reel']:.1%}.", "",
                   "| Modèle | AUC validation | AUC test | Top 10 % test |", "|---|---:|---:|---:|"]
            md += [f"| {nom} | {v[nom]['auc_moyen_par_annee']:.3f} | {r[nom]['auc_moyen_par_annee']:.3f} | "
                   f"{r[nom]['top10_moyen_par_annee']:.1%} |" for nom in r]
            if "sans_exposition" in m["resultats"]:
                se = m["resultats"]["sans_exposition"]
                md.append(f"| _LightGBM sans exposition argiles_ | {se['validation']['auc_moyen_par_annee']:.3f} | "
                          f"{se['test']['auc_moyen_par_annee']:.3f} | {se['test']['top10_moyen_par_annee']:.1%} |")
            md += ["", f"Calibration (test) : probabilité moyenne prédite **{r['LightGBM']['taux_predit']:.1%}** "
                   f"avant recalage, **{c['taux_predit']:.1%}** après, pour **{c['taux_reel']:.1%}** observé ; "
                   f"score de Brier {r['LightGBM']['brier']:.4f} → {c['brier']:.4f}.", ""]
        imp = pd.Series(par_h[next(iter(par_h))]["importances"]).sort_values(ascending=False).head(5)
        md += ["Variables les plus influentes à 1 an (SHAP) : "
               + ", ".join(f"{libelles.get(k, k)} ({x:.2f})" for k, x in imp.items()) + ".", ""]
    md += ["![AUC par horizon](figures/auc_par_horizon.png)", "",
           "![Importance SHAP](figures/importance_shap.png)", "",
           "![Calibration](figures/calibration.png)", ""]
    return "\n".join(md)


# --- Programme principal ---------------------------------------------------------------
def main() -> int:
    df = charger()
    libelles = variables(df)
    noms = list(libelles)
    print(f"{len(noms)} variables : {', '.join(noms)}")
    MODELS_DIR.mkdir(exist_ok=True)
    metriques, predictions = {}, []

    for famille in NOMS:
        metriques[famille] = {}
        for h in HORIZONS:
            print(f"\n== {famille}, horizon {h} an{'s' if h > 1 else ''}")
            m = evaluer_famille_horizon(df, famille, h, noms)
            metriques[famille][h] = m
            for nom in m["resultats"]["test"]:
                v, t = m["resultats"]["validation"][nom], m["resultats"]["test"][nom]
                print(f"  {nom:<26} validation AUC/an {v['auc_moyen_par_annee']:.3f} | "
                      f"test AUC/an {t['auc_moyen_par_annee']:.3f} top10 {t['top10_moyen_par_annee']:.1%}")
            if "sans_exposition" in m["resultats"]:
                se = m["resultats"]["sans_exposition"]
                print(f"  {'LightGBM sans exposition':<26} validation AUC/an {se['validation']['auc_moyen_par_annee']:.3f} | "
                      f"test AUC/an {se['test']['auc_moyen_par_annee']:.3f} top10 {se['test']['top10_moyen_par_annee']:.1%}")
            c, t = m["resultats"]["test_calibre"], m["resultats"]["test"]["LightGBM"]
            print(f"  calibration test : prédit {t['taux_predit']:.1%} -> {c['taux_predit']:.1%}, "
                  f"observé {c['taux_reel']:.1%} ; Brier {t['brier']:.4f} -> {c['brier']:.4f}")
            sortie = produire(df, famille, h, noms)
            predictions.append(sortie)
            print(f"  prédictions {int(sortie['annee'].iloc[0])} : {len(sortie):,} communes")

    pd.concat(predictions).to_parquet(PROCESSED_DIR / "predictions.parquet", index=False)
    figures(metriques, libelles)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "metriques_modele.json").write_text(
        json.dumps({"variables": noms, "metriques": metriques}, indent=2, ensure_ascii=False), encoding="utf-8")
    (REPORTS_DIR / "modele.md").write_text(rapport(metriques, libelles), encoding="utf-8")
    print("\nTerminé : reports/modele.md, reports/figures/, data/processed/predictions.parquet")
    return 0


if __name__ == "__main__":
    sys.exit(main())

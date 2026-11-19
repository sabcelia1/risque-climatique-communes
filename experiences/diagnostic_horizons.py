"""Diagnostic : pourquoi l'inondation à 3 et 5 ans est-elle mal prédite ?"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import modele as m

df = m.charger()
noms = list(m.variables(df))
for famille in ("inondation", "secheresse"):
    for h in (1, 3, 5):
        cible, ev = m.colonnes_horizon()[h]
        d = df[(df.famille_peril == famille) & df[ev]]
        print(f"\n== {famille} h={h} : par année de départ, taux réel et AUC de l'historique / de la fréquence départementale")
        lignes = []
        for a, g in d.groupby("annee"):
            if 0 < g[cible].sum() < len(g):
                lignes.append((a, g[cible].mean(), roc_auc_score(g[cible], g["taux_historique"].fillna(0)),
                               roc_auc_score(g[cible], g["taux_dept_5ans"].fillna(0)),
                               roc_auc_score(g[cible], -g["annees_depuis_derniere"].fillna(99))))
        t = pd.DataFrame(lignes, columns=["annee", "taux", "auc_hist", "auc_dept", "auc_recence"]).round(3)
        print(t.to_string(index=False))
    # Modèle à 5 ans entraîné sur des périodes différentes
    if famille == "inondation":
        p = m.decouper(df, famille, 5)
        for debut in (1992, 1998, 2000, 2002):
            tr = p["entrainement"][p["entrainement"].annee >= debut]
            mod = m.entrainer_lgbm(tr, p["validation"], noms)
            for jeu in ("validation", "test"):
                dd = p[jeu]
                r = m.evaluer(dd["y"], mod.predict(dd[noms], num_iteration=mod.best_iteration), dd["annee"])
                print(f"  h=5 entraînement {debut}-{tr.annee.max()} : {jeu} AUC/an {r['auc_moyen_par_annee']:.3f} (arbres {mod.best_iteration})")

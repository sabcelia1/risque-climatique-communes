"""Étape 4 — Fiches de risque par commune, rédigées par Gemini et contrôlées.

1. Un DOSSIER FACTUEL est construit pour la commune, uniquement à partir des données du
   projet (historique, exposition aux argiles, prédictions, facteurs SHAP), avec des
   valeurs déjà formatées.
2. Gemini rédige la fiche à partir de ce dossier seulement (sortie JSON structurée).
3. CONTRÔLE : chaque nombre écrit doit figurer dans le dossier. Sinon, un second essai est
   demandé en signalant les nombres en cause ; en cas de nouvel échec, la fiche est rejetée.

Usage :
    python src/fiches.py 06088 32013          # communes choisies (codes INSEE)
    python src/fiches.py --exemples           # jeu d'exemples -> docs/fiches_exemples.md
"""

import argparse
import json
import math
import sys

import pandas as pd
from pydantic import BaseModel, Field

from base_ia import base_isolee
from config import ROOT_DIR
from controle_chiffres import verifier

LIBELLES_FACTEURS = {
    "nb_evt_1an": ("Reconnaissances connues l'année précédente", "nombre"),
    "nb_evt_5ans": ("Reconnaissances connues sur 5 ans", "nombre"),
    "nb_evt_10ans": ("Reconnaissances connues sur 10 ans", "nombre"),
    "taux_historique": ("Fréquence des reconnaissances depuis 1982", "par_an"),
    "annees_depuis_derniere": ("Années depuis la dernière reconnaissance", "annees"),
    "nb_evt_autres_perils_10ans": ("Reconnaissances pour d'autres périls sur 10 ans", "nombre"),
    "taux_dept_5ans": ("Fréquence récente dans le département", "par_an"),
    "population": ("Population", "nombre"), "surface_km2": ("Superficie", "km2"),
    "densite_hab_km2": ("Densité de population", "densite"), "latitude": ("Localisation géographique (nord-sud)", "aucune"),
    "longitude": ("Localisation géographique (est-ouest)", "aucune"),
    "part_argile_fort": ("Part du territoire en exposition forte aux argiles", "part"),
    "part_argile_moyen": ("Part du territoire en exposition moyenne aux argiles", "part"),
    "part_argile_faible": ("Part du territoire en exposition faible aux argiles", "part"),
}
EXEMPLES = ["32013", "06088", "31555", "13055", "37261", "29019", "75056", "59350"]


# --- Formatage français -----------------------------------------------------------------
def entier(x) -> str:
    return f"{int(round(x)):,}".replace(",", " ")


def decimal(x, n=1) -> str:
    return f"{x:.{n}f}".replace(".", ",")


def pourcent(x) -> str:
    return f"{int(round(100 * x))} %"


def valeur_facteur(nom, valeur) -> str | None:
    _, nature = LIBELLES_FACTEURS.get(nom, (nom, "aucune"))
    if valeur is None or (isinstance(valeur, float) and math.isnan(valeur)) or nature == "aucune":
        return None
    return {"nombre": lambda v: entier(v), "par_an": lambda v: f"{decimal(v, 2)} par an",
            "annees": lambda v: f"{entier(v)} ans", "km2": lambda v: f"{decimal(v)} km²",
            "densite": lambda v: f"{entier(v)} habitants par km²", "part": pourcent}[nature](valeur)


def rang_national(percentile: float) -> str:
    haut = max(1, math.ceil(round((1 - percentile) * 100, 6)))     # round : évite 1,0000001 -> 2
    return (f"parmi les {haut} % de communes les plus exposées de France" if haut <= 50
            else f"dans la moitié la moins exposée des communes de France")


# --- Dossier factuel --------------------------------------------------------------------
def dossier(con, code_insee: str) -> dict:
    c = con.execute("select * from communes where code_insee = ?", [code_insee]).df()
    if c.empty:
        raise SystemExit(f"Commune inconnue : {code_insee}")
    c = c.iloc[0]
    preds = con.execute("""select * from predictions_facteurs where code_insee = ?
                           order by famille_peril, horizon_ans""", [code_insee]).df()
    evts = con.execute("""select famille_peril, count(*) n, max(annee) derniere
                          from evenements where code_insee = ? group by 1""", [code_insee]).df()
    recents = con.execute("""select annee, libelle_peril from evenements where code_insee = ?
                             order by date_debut desc limit 5""", [code_insee]).df()

    faits = {
        "commune": c["nom_commune"],
        "departement": f"{c['nom_departement']} ({c['code_departement']})",
        "region": c["nom_region"],
        "population": f"{entier(c['population'])} habitants" if pd.notna(c["population"]) else "inconnue",
        "superficie": f"{decimal(c['surface_km2'])} km²",
        "exposition_argiles": ("non couverte par le zonage BRGM" if pd.isna(c["part_argile_fort"]) else {
            "forte": pourcent(c["part_argile_fort"]), "moyenne": pourcent(c["part_argile_moyen"]),
            "faible": pourcent(c["part_argile_faible"])}),
        "historique_depuis_1982": {
            "total_reconnaissances": entier(c["nb_evenements_total"]),
            "par_peril": {r.famille_peril: f"{entier(r.n)} reconnaissances, la dernière en {int(r.derniere)}"
                          for r in evts.itertuples()},
            "dernieres_reconnaissances": [f"{int(r.annee)} : {r.libelle_peril}" for r in recents.itertuples()],
        },
        "risque_predit": {},
        "reperes": {"periode_historique": "depuis 1982", "date_de_reference": "au 1er janvier "
                    + (str(int(preds["annee"].iloc[0])) if not preds.empty else "")},
    }
    for p in preds.itertuples():
        horizon = f"{p.horizon_ans} an{'s' if p.horizon_ans > 1 else ''}"
        entree = {"classement": rang_national(p.percentile_national),
                  "probabilite_indicative": pourcent(p.probabilite)}
        facteurs = []
        for k in (1, 2, 3):
            nom, contrib = getattr(p, f"facteur_{k}", None), getattr(p, f"contribution_{k}", None)
            if nom is None or (isinstance(nom, float) and math.isnan(nom)):
                continue
            libelle = LIBELLES_FACTEURS.get(nom, (nom,))[0]
            val = valeur_facteur(nom, getattr(p, f"valeur_{k}", None))
            sens = "augmente le risque" if (contrib or 0) > 0 else "diminue le risque"
            facteurs.append(f"{libelle}{' : ' + val if val else ''} ({sens})")
        if facteurs:
            entree["principaux_facteurs"] = facteurs
        faits["risque_predit"].setdefault(p.famille_peril, {})[horizon] = entree
    return faits


# --- Rédaction et contrôle --------------------------------------------------------------
class Fiche(BaseModel):
    titre: str = Field(description="Nom de la commune et de son département")
    synthese: str = Field(description="2 à 3 phrases : niveau de risque global, péril dominant")
    secheresse: str = Field(description="Risque sécheresse : classement, horizons, facteurs, argiles")
    inondation: str = Field(description="Risque inondation : classement, horizons, facteurs")
    historique: str = Field(description="Reconnaissances passées, les plus récentes")
    limites: str = Field(description="Une phrase : probabilités indicatives, classement fiable")


CONSIGNE = """Tu es analyste en risques naturels pour un assureur. Tu rédiges en français une fiche
de risque concise et factuelle sur une commune, à partir du DOSSIER fourni.

Règles impératives :
- N'utilise QUE les informations du dossier. N'ajoute aucun fait extérieur (cours d'eau,
  événements, géographie, chiffres) même si tu les connais.
- Tout nombre que tu écris doit apparaître tel quel dans le dossier (même valeur, même unité).
  N'effectue aucun calcul, aucune conversion, aucun arrondi. N'écris pas de nombres en lettres.
- Mets en avant le classement national, plus fiable que la probabilité, qui est indicative.
- Explique les facteurs avec des mots simples ; ne parle pas de « SHAP » ni de « modèle LightGBM ».
- Ton professionnel, phrases courtes, pas de listes à puces, pas de recommandations commerciales."""


def rediger(llm, faits: dict) -> dict:
    contenu = "DOSSIER (JSON) :\n" + json.dumps(faits, ensure_ascii=False, indent=1)
    texte, hors_dossier, essais = None, [], 0
    for essais in (1, 2):
        if hors_dossier:
            contenu += ("\n\nTa fiche précédente contenait des nombres absents du dossier : "
                        + ", ".join(decimal(n, 2).rstrip("0").rstrip(",") for n in hors_dossier)
                        + ". Réécris-la en n'utilisant que des nombres du dossier.")
        texte = llm.json(CONSIGNE, contenu, Fiche)
        hors_dossier = verifier(" ".join(str(v) for v in texte.values()), faits)
        if not hors_dossier:
            break
    return {"fiche": texte, "faits": faits, "valide": not hors_dossier, "essais": essais,
            "nombres_hors_dossier": hors_dossier, "modele": getattr(llm, "modele", None)}


def en_markdown(resultat: dict) -> str:
    f = resultat["fiche"]
    statut = ("✅ chiffres vérifiés" if resultat["valide"] else
              f"❌ rejetée : nombres absents des données {resultat['nombres_hors_dossier']}")
    return "\n".join([f"### {f['titre']}", "", f"_{statut} — {resultat['essais']} essai(s), "
                      f"modèle {resultat['modele']}_", "", f"**En bref.** {f['synthese']}", "",
                      f"**Sécheresse.** {f['secheresse']}", "", f"**Inondation.** {f['inondation']}", "",
                      f"**Historique.** {f['historique']}", "", f"**Limites.** {f['limites']}", ""])


def base_avec_facteurs():
    """Base isolée, complétée des prédictions détaillées (facteurs explicatifs compris)."""
    from config import PROCESSED_DIR

    con = base_isolee()
    preds = pd.read_parquet(PROCESSED_DIR / "predictions.parquet")
    con.register("facteurs_df", preds)
    con.execute("create table predictions_facteurs as select * from facteurs_df")
    con.unregister("facteurs_df")
    return con


def main() -> int:
    from llm import Gemini, LLMIndisponible

    parser = argparse.ArgumentParser()
    parser.add_argument("codes", nargs="*")
    parser.add_argument("--exemples", action="store_true")
    args = parser.parse_args()
    codes = EXEMPLES if args.exemples or not args.codes else args.codes
    con = base_avec_facteurs()
    try:
        llm = Gemini()
    except LLMIndisponible as e:
        print(e, file=sys.stderr)
        return 1
    resultats = []
    for code in codes:
        try:
            r = rediger(llm, dossier(con, code))
        except LLMIndisponible as e:
            print(f"{code} : Gemini indisponible ({e})", flush=True)
            continue
        resultats.append(r)
        print(f"{code} {r['faits']['commune']} : {'valide' if r['valide'] else 'REJETÉE'} "
              f"({r['essais']} essai(s)){' ' + str(r['nombres_hors_dossier']) if r['nombres_hors_dossier'] else ''}",
              flush=True)
    valides = sum(r["valide"] for r in resultats)
    entete = ["# Fiches de risque : exemples générés par Gemini", "",
              f"_Générées par `src/fiches.py` le {pd.Timestamp.today():%d/%m/%Y} avec {llm.modele}. "
              f"{valides}/{len(resultats)} fiches validées par le contrôle des chiffres._", "",
              "Chaque fiche est rédigée à partir d'un dossier factuel construit par le pipeline ; "
              "tout nombre absent du dossier entraîne un second essai, puis le rejet.", ""]
    md = "\n".join(entete + [en_markdown(r) for r in resultats])
    sortie = ROOT_DIR / ("docs/fiches_exemples.md" if args.exemples or not args.codes else "reports/fiches.md")
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(md, encoding="utf-8")
    (sortie.with_suffix(".json")).write_text(json.dumps(resultats, ensure_ascii=False, indent=1, default=str),
                                              encoding="utf-8")
    print(f"\n{valides}/{len(resultats)} fiches validées -> {sortie.relative_to(ROOT_DIR)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Tests de l'IA générative, sans appel à Gemini (faux modèle aux réponses préparées)."""

import sys
from pathlib import Path

import duckdb
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import assistant_sql  # noqa: E402
import base_ia  # noqa: E402
import evaluer_assistant  # noqa: E402
import fiches  # noqa: E402
from controle_chiffres import extraire_nombres, verifier  # noqa: E402
from garde_fous_sql import RequeteRefusee, executer, verifier_sql  # noqa: E402
from llm import FauxLLM  # noqa: E402


# --- Contrôle des chiffres --------------------------------------------------------------
def test_extraction_format_francais():
    assert extraire_nombres("12 345 habitants, 91 %, 0,70 par an, au 1er janvier 2025") == [12345, 91, 0.7, 1, 2025]
    assert extraire_nombres("Alpes-Maritimes (06), 52,5 km²") == [6, 52.5]


def test_verifier_signale_les_nombres_inventes():
    faits = {"exposition": {"forte": "91 %"}, "population": "23 245 habitants", "horizons": ["1 an", "5 ans"]}
    assert verifier("91 % du territoire, 23 245 habitants, à 5 ans.", faits) == []
    assert verifier("92 % du territoire et 3 crues en 1999.", faits) == [3, 92, 1999]


# --- Garde-fous SQL ---------------------------------------------------------------------
@pytest.mark.parametrize("sql", [
    "drop table communes", "delete from evenements", "insert into communes select * from communes",
    "create table x as select 1", "copy communes to 'x.csv'", "attach 'risque.duckdb' as x",
    "select * from read_csv('/etc/passwd')", "select * from read_parquet('data/processed/predictions.parquet')",
    "select getenv('HOME')", "select * from duckdb_settings()", "select * from query('select 1')",
    "select * from information_schema.tables", "select * from src.dim_commune", "select 1; drop table communes",
    "set enable_external_access = true", "pragma database_list", "select * from glob('*')", "",
    "select * from communes where", "update communes set population = 0",
])
def test_requetes_dangereuses_refusees(sql):
    with pytest.raises(RequeteRefusee):
        verifier_sql(sql)


@pytest.mark.parametrize("sql", [
    "select nom_commune from communes order by nb_evenements_total desc limit 5",
    "with s as (select * from evenements where famille_peril = 'secheresse') select count(*) from s",
    "select c.nom_commune, p.percentile_national from predictions p join communes c using (code_insee)",
    "select annee, count(*) from evenements group by annee union all select 0, 0",
])
def test_lectures_acceptees_et_plafonnees(sql):
    assert verifier_sql(sql).endswith("limit 200")


# --- Base isolée ------------------------------------------------------------------------
@pytest.fixture
def base(tmp_path, monkeypatch):
    con = duckdb.connect(str(tmp_path / "risque.duckdb"))
    con.execute("""create table dim_commune as select * from (values
        ('32013', 'Auch', '32', 'Gers', 'Occitanie', 22000, 72.5, 303.4, 40, 12, 20, 2022),
        ('29019', 'Brest', '29', 'Finistère', 'Bretagne', 140000, 49.5, 2828.3, 10, 0, 8, 2018))
        t(code_insee, nom_commune, code_departement, nom_departement, nom_region, population, surface_km2,
          densite_hab_km2, nb_evenements_total, nb_secheresses, nb_inondations, derniere_annee_touchee)""")
    con.execute("""create table exposition_argiles as select * from (values ('32013', 0.0, 0.05, 0.95),
        ('29019', 0.3, 0.0, 0.0)) t(code_insee, part_argile_faible, part_argile_moyen, part_argile_fort)""")
    con.execute("""create table fct_evenements as select * from (values
        ('32013', 'Auch', '32', 'Gers', 'Occitanie', 'secheresse', 'Sécheresse', 2022,
         date '2022-07-01', date '2022-09-30', date '2023-06-01', 335, false),
        ('29019', 'Brest', '29', 'Finistère', 'Bretagne', 'inondation', 'Inondations et coulées de boue', 2018,
         date '2018-01-03', date '2018-01-04', date '2018-02-10', 38, false))
        t(code_insee, nom_commune, code_departement, nom_departement, nom_region, famille_peril, libelle_peril,
          annee, date_debut, date_fin, date_arrete, delai_reconnaissance_jours, duree_suspecte)""")
    con.close()
    lignes = []
    for code, pct in (("32013", 0.99), ("29019", 0.2)):
        for famille in ("secheresse", "inondation"):
            for h in (1, 3, 5):
                lignes.append({"code_insee": code, "code_departement": code[:2], "annee": 2025,
                               "famille_peril": famille, "horizon_ans": h, "probabilite": 0.1 * h,
                               "percentile_national": pct, "facteur_1": "part_argile_fort",
                               "contribution_1": 0.8, "valeur_1": 0.95, "facteur_2": "population",
                               "contribution_2": -0.2, "valeur_2": 22000.0, "facteur_3": "latitude",
                               "contribution_3": 0.1, "valeur_3": 43.6})
    pd.DataFrame(lignes).to_parquet(tmp_path / "predictions.parquet")
    monkeypatch.setattr(base_ia, "PROCESSED_DIR", tmp_path)
    monkeypatch.setattr("config.PROCESSED_DIR", tmp_path)
    return tmp_path


def test_base_isolee_sans_acces_aux_fichiers(base):
    con = base_ia.base_isolee()
    assert {r[0] for r in con.execute("select table_name from information_schema.tables").fetchall()} == set(base_ia.TABLES)
    for attaque in (f"select * from read_parquet('{(base / 'predictions.parquet').as_posix()}')",
                    "set enable_external_access = true", f"attach '{(base / 'risque.duckdb').as_posix()}' as x"):
        with pytest.raises(duckdb.Error):
            con.execute(attaque)
    assert executer(con, "select nom_commune from communes where part_argile_fort > 0.5")["nom_commune"].tolist() == ["Auch"]


# --- Fiches -----------------------------------------------------------------------------
def _fiche(texte_secheresse):
    return {"titre": "Auch (Gers)", "synthese": "Commune très exposée à la sécheresse.",
            "secheresse": texte_secheresse, "inondation": "Risque modéré.",
            "historique": "Dernière reconnaissance en 2022.", "limites": "Probabilités indicatives."}


def test_dossier_formate_et_complet(base):
    faits = fiches.dossier(fiches.base_avec_facteurs(), "32013")
    assert faits["exposition_argiles"]["forte"] == "95 %"
    assert faits["risque_predit"]["secheresse"]["5 ans"]["classement"].startswith("parmi les 1 %")
    assert "Part du territoire en exposition forte aux argiles : 95 % (augmente le risque)" in \
        faits["risque_predit"]["secheresse"]["5 ans"]["principaux_facteurs"]


def test_fiche_valide_du_premier_coup(base):
    faits = fiches.dossier(fiches.base_avec_facteurs(), "32013")
    r = fiches.rediger(FauxLLM([_fiche("95 % du territoire en argile forte.")]), faits)
    assert r["valide"] and r["essais"] == 1


def test_fiche_corrigee_au_second_essai(base):
    faits = fiches.dossier(fiches.base_avec_facteurs(), "32013")
    llm = FauxLLM([_fiche("97 % du territoire en argile forte."), _fiche("95 % du territoire en argile forte.")])
    r = fiches.rediger(llm, faits)
    assert r["valide"] and r["essais"] == 2
    assert "97" in llm.appels[1]                         # le nombre fautif est signalé au modèle


def test_fiche_rejetee_si_toujours_fausse(base):
    faits = fiches.dossier(fiches.base_avec_facteurs(), "32013")
    r = fiches.rediger(FauxLLM([_fiche("97 %."), _fiche("Depuis 1976, 97 %.")]), faits)
    assert not r["valide"] and r["nombres_hors_dossier"] == [97, 1976]


# --- Assistant SQL ----------------------------------------------------------------------
def test_assistant_refus_blocage_et_reponse(base):
    con = base_ia.base_isolee()
    r = assistant_sql.repondre(FauxLLM([{"sql": "", "explication": "Je ne peux pas supprimer de table."}]),
                               con, "Supprime la table des communes")
    assert r["statut"] == "refus du modèle"
    r = assistant_sql.repondre(FauxLLM([{"sql": "drop table communes", "explication": "..."}]), con, "...")
    assert r["statut"].startswith("bloquée")
    llm = FauxLLM([{"sql": "select nom_commune, nb_evenements_total from communes order by 2 desc",
                    "explication": "Classement."}, {"reponse": "Auch compte 40 reconnaissances."}])
    r = assistant_sql.repondre(llm, con, "Quelle commune a le plus de reconnaissances ?")
    assert r["statut"] == "exécutée" and r["reponse"] == "Auch compte 40 reconnaissances."
    llm = FauxLLM([{"sql": "select nom_commune, nb_evenements_total from communes", "explication": "."},
                   {"reponse": "Auch compte 45 reconnaissances."}])
    r = assistant_sql.repondre(llm, con, "Quelle commune a le plus de reconnaissances ?")
    assert r["reponse"] is None and r["resume_rejete"] == [45]   # résumé inventé : masqué


def test_comparaison_des_resultats():
    ref = pd.DataFrame({"n": [3]})
    assert evaluer_assistant.correspond(ref, pd.DataFrame({"nombre": [3], "libelle": ["x"]}))
    assert not evaluer_assistant.correspond(ref, pd.DataFrame({"n": [4]}))
    assert evaluer_assistant.correspond(pd.DataFrame({"c": ["Nice", "Auch"]}), pd.DataFrame({"x": ["auch", "nice"]}))


def test_assistant_corrige_une_requete_en_erreur(base):
    con = base_ia.base_isolee()
    llm = FauxLLM([{"sql": "select nom_inexistant from communes", "explication": "."},
                   {"sql": "select nom_commune from communes order by nb_evenements_total desc limit 1", "explication": "."},
                   {"reponse": "Auch."}])
    r = assistant_sql.repondre(llm, con, "Quelle commune a le plus de reconnaissances ?")
    assert r["statut"] == "exécutée" and r.get("corrigee") and "nom_inexistant" in llm.appels[1]
    r = assistant_sql.repondre(FauxLLM([{"sql": "drop table communes", "explication": "."}]), con, "...")
    assert r["statut"].startswith("bloquée") and not r.get("corrigee")      # pas de second essai


def test_paris_non_couverte_par_le_zonage_argiles():
    import csv
    chemin = Path(__file__).resolve().parents[1] / "dbt" / "seeds" / "exposition_argiles.csv"
    paris = [l for l in csv.DictReader(open(chemin, encoding="utf-8")) if l["code_insee"] == "75056"]
    assert paris and paris[0]["part_argile_fort"] == ""

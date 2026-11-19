"""Garde-fous de l'assistant SQL : une requête n'est exécutée que si elle est sûre.

Vérifications (avant exécution) :
  1. une seule instruction, lisible par l'analyseur SQL ;
  2. lecture seule : uniquement SELECT (avec WITH, UNION…), aucune écriture ni commande ;
  3. uniquement les tables autorisées, aucune fonction d'accès aux fichiers ou au système ;
  4. nombre de lignes plafonné.
L'exécution se fait ensuite dans une base isolée et verrouillée (base_ia.py), avec un délai maximal.
"""

import threading

import sqlglot
from sqlglot import exp

from base_ia import TABLES

LIGNES_MAX = 200
DELAI_MAX_S = 10
INTERDITS = (exp.Insert, exp.Update, exp.Delete, exp.Merge, exp.Create, exp.Drop, exp.Alter,
             exp.Command, exp.Copy, exp.Set, exp.Pragma, exp.Transaction, exp.Use, exp.Attach,
             exp.Detach, exp.Install, exp.Into, exp.TruncateTable, exp.Describe, exp.Show)
PREFIXES_FONCTIONS_INTERDITES = ("read_", "glob", "getenv", "current_setting", "pragma", "duckdb_",
                                 "sniff_", "query", "parquet_", "iceberg", "delta_", "sqlite_",
                                 "postgres_", "mysql_", "http", "load", "install", "attach", "system")


class RequeteRefusee(Exception):
    pass


def verifier_sql(sql: str) -> str:
    """Renvoie la requête sûre (avec limite de lignes) ou lève RequeteRefusee."""
    if not sql or not sql.strip():
        raise RequeteRefusee("requête vide")
    try:
        instructions = [s for s in sqlglot.parse(sql, read="duckdb") if s is not None]
    except sqlglot.errors.ParseError as e:
        raise RequeteRefusee(f"SQL illisible : {str(e).splitlines()[0]}") from e
    if len(instructions) != 1:
        raise RequeteRefusee("une seule instruction est autorisée")
    requete = instructions[0]
    if not isinstance(requete, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        raise RequeteRefusee(f"seules les lectures (SELECT) sont autorisées, pas {type(requete).__name__}")
    for noeud in requete.walk():
        if isinstance(noeud, INTERDITS):
            raise RequeteRefusee(f"opération interdite : {type(noeud).__name__}")
    ctes = {c.alias_or_name.lower() for c in requete.find_all(exp.CTE)}
    for table in requete.find_all(exp.Table):
        nom = table.name.lower()
        if isinstance(table.this, exp.Func) or not nom:
            raise RequeteRefusee("les fonctions de table (lecture de fichiers, système) sont interdites")
        if table.db or table.catalog:
            raise RequeteRefusee(f"table non autorisée : {table.sql()}")
        if nom not in TABLES and nom not in ctes:
            raise RequeteRefusee(f"table non autorisée : {nom} (tables possibles : {', '.join(TABLES)})")
    for fonction in requete.find_all(exp.Func):
        nom = (fonction.name if isinstance(fonction, exp.Anonymous) else fonction.sql_name()).lower()
        if nom.startswith(PREFIXES_FONCTIONS_INTERDITES):
            raise RequeteRefusee(f"fonction interdite : {nom}")
    return f"select * from ({requete.sql(dialect='duckdb')}) as resultat limit {LIGNES_MAX}"


def executer(con, sql: str):
    """Vérifie puis exécute la requête dans la base isolée ; renvoie un DataFrame."""
    sur = verifier_sql(sql)
    minuterie = threading.Timer(DELAI_MAX_S, con.interrupt)
    minuterie.start()
    try:
        return con.execute(sur).df()
    except Exception as e:                       # erreur SQL ou délai dépassé
        raise RequeteRefusee(f"exécution impossible : {str(e).splitlines()[0]}") from e
    finally:
        minuterie.cancel()

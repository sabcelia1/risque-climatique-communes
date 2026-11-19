"""Contenu des fichiers SDES (argiles par commune) et recherche d'un équivalent inondation."""
import io
import pandas as pd
import requests

S = requests.Session()
for nom, rid in [("maisons", "1d6ff531-fe68-4102-9591-8da9ffdf8300"), ("surfaces", "1a9ad5c2-0929-4687-8455-78aac6530a76")]:
    url = f"https://data.statistiques.developpement-durable.gouv.fr/dido/api/v1/datafiles/{rid}/csv"
    r = S.get(url, timeout=180, params={"withColumnName": "true", "withColumnDescription": "true"})
    print(f"\n######## {nom} : {r.status_code} {len(r.content)/1e6:.1f} Mo")
    texte = r.content.decode("utf-8", "replace")
    print("\n".join(texte.splitlines()[:6])[:3000])
    try:
        df = pd.read_csv(io.StringIO(texte), sep=None, engine="python", skiprows=0)
        print("lignes", len(df), "colonnes", list(df.columns)[:40])
    except Exception as e:
        print("lecture", e)

def api(q):
    r = S.get("https://www.data.gouv.fr/api/1/datasets/", params={"q": q, "page_size": 6}, timeout=60)
    print(f"\n######## recherche : {q}")
    for d in r.json()["data"]:
        org = (d.get("organization") or {}).get("name")
        print(f"\n* {d['title']} | {org} | maj {d.get('last_modified','')[:10]} | {d['page']}")
        for res in d["resources"][:6]:
            print(f"    - {res['title'][:70]} | {res.get('format')} | {res['url']}")
for q in ["population exposée inondation commune", "exposition inondation communes SDES",
          "EAIP France métropolitaine", "zones inondables par commune indicateur"]:
    try: api(q)
    except Exception as e: print("ERREUR", q, e)

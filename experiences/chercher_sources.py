"""Inventaire des sources d'exposition physique (argiles, zones inondables, contours)."""
import requests

S = requests.Session()
def api(q):
    r = S.get("https://www.data.gouv.fr/api/1/datasets/", params={"q": q, "page_size": 8}, timeout=60)
    print(f"\n######## recherche : {q}")
    for d in r.json()["data"]:
        org = (d.get("organization") or {}).get("name")
        print(f"\n* {d['title']} | {org} | maj {d.get('last_modified','')[:10]} | {d['page']}")
        for res in d["resources"][:8]:
            print(f"    - {res['title'][:70]} | {res.get('format')} | {res.get('filesize')} | {res['url']}")

for q in ["exposition retrait-gonflement des argiles", "aléa retrait gonflement argiles France",
          "enveloppe approchée des inondations potentielles", "EAIP inondation",
          "zones inondables france entière", "contours administratifs communes"]:
    try: api(q)
    except Exception as e: print("ERREUR", q, e)

print("\n######## URL candidates")
for u in ["https://files.georisques.fr/argiles/AleaRG_Fxx_L93.zip",
          "https://files.georisques.fr/argiles/ExpoArgile_Fxx_L93.zip",
          "https://files.georisques.fr/argiles/",
          "https://files.georisques.fr/di/",
          "https://files.georisques.fr/",
          "https://georisques.gouv.fr/api/v1/rga?latlon=2.29,48.85",
          "https://etalab-datasets.geo.data.gouv.fr/contours-administratifs/2025/geojson/communes-100m.geojson.gz",
          "https://etalab-datasets.geo.data.gouv.fr/contours-administratifs/2024/geojson/communes-100m.geojson.gz"]:
    try:
        r = S.get(u, timeout=60, stream=True)
        debut = next(r.iter_content(600), b"")
        print(f"\n{u}\n  -> {r.status_code} {r.headers.get('content-type')} {r.headers.get('content-length')}")
        if b"<" in debut[:5] or b"{" in debut[:5]:
            print("  ", debut.decode("utf-8", "replace")[:600].replace("\n", " "))
    except Exception as e:
        print(u, "ERREUR", e)

"""Étape 1 — Ingestion : télécharge les sources brutes dans data/raw/.

Usage :
    python src/ingest.py            # télécharge ce qui manque
    python src/ingest.py --force    # retélécharge tout
"""

import argparse
import io
import json
import sys
import zipfile
from datetime import datetime, timezone

import requests

from config import RAW_DIR, SOURCES

TIMEOUT = 120
FICHIERS = {"gaspar": "catnat_gaspar.csv", "communes": "communes.json"}
CHUNK = 1024 * 1024


def telecharger(url: str) -> bytes:
    with requests.get(url, stream=True, timeout=TIMEOUT) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        buf, fait = io.BytesIO(), 0
        for morceau in resp.iter_content(CHUNK):
            buf.write(morceau)
            fait += len(morceau)
            if total:
                print(f"\r  {fait / 1e6:6.1f} / {total / 1e6:.1f} Mo", end="")
        print()
        return buf.getvalue()


def extraire_catnat(contenu: bytes) -> bytes:
    """GASPAR est publié tantôt en CSV, tantôt en ZIP de plusieurs tables
    (noms variables : catnat_gaspar.csv, catnat_gaspar.csv.csv, 2026_catnat…).
    On renvoie le contenu de la table des arrêtés CatNat."""
    if not zipfile.is_zipfile(io.BytesIO(contenu)):
        return contenu
    with zipfile.ZipFile(io.BytesIO(contenu)) as z:
        noms = z.namelist()
        candidats = [n for n in noms if "catnat" in n.lower() and not n.endswith("/")]
        if not candidats:
            raise RuntimeError(f"Aucune table CatNat dans l'archive GASPAR. Fichiers : {noms}")
        nom = max(candidats, key=lambda n: z.getinfo(n).file_size)
        print(f"  archive ZIP : table retenue « {nom} » parmi {len(noms)} fichiers")
        return z.read(nom)


def ingerer(nom: str, source: dict, force: bool) -> None:
    cible = RAW_DIR / FICHIERS[nom]
    if cible.exists() and not force:
        print(f"[{nom}] déjà présent ({cible.stat().st_size / 1e6:.1f} Mo) — ignoré")
        return
    print(f"[{nom}] téléchargement : {source['description']}")
    contenu = telecharger(source["url"])
    if nom == "gaspar":
        contenu = extraire_catnat(contenu)
    tmp = cible.with_suffix(cible.suffix + ".part")
    tmp.write_bytes(contenu)
    tmp.replace(cible)
    print(f"[{nom}] OK -> {cible.name} ({len(contenu) / 1e6:.1f} Mo)")


def ecrire_manifeste() -> None:
    """Trace la provenance et la date de chaque fichier (gouvernance)."""
    fichiers = FICHIERS
    manifeste = {
        nom: {"fichier": f, "source": SOURCES[nom]["page"],
              "telecharge_le": datetime.fromtimestamp((RAW_DIR / f).stat().st_mtime,
                                                      tz=timezone.utc).isoformat(timespec="seconds")}
        for nom, f in fichiers.items() if (RAW_DIR / f).exists()
    }
    (RAW_DIR / "manifest.json").write_text(json.dumps(manifeste, indent=2, ensure_ascii=False),
                                           encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    erreurs = 0
    for nom, source in SOURCES.items():
        try:
            ingerer(nom, source, args.force)
        except (requests.RequestException, RuntimeError) as exc:
            erreurs += 1
            print(f"[{nom}] ÉCHEC : {exc}", file=sys.stderr)
    ecrire_manifeste()
    return 1 if erreurs else 0


if __name__ == "__main__":
    sys.exit(main())

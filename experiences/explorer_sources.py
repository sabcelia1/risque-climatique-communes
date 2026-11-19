"""Inventaire des tables de l'archive GASPAR (colonnes, taille, premières lignes)."""
import io, sys, zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from config import SOURCES
from ingest import telecharger

contenu = telecharger(SOURCES["gaspar"]["url"])
print("ZIP :", zipfile.is_zipfile(io.BytesIO(contenu)), f"{len(contenu)/1e6:.1f} Mo")
with zipfile.ZipFile(io.BytesIO(contenu)) as z:
    for info in z.infolist():
        print(f"\n--- {info.filename} ({info.file_size/1e6:.1f} Mo)")
        with z.open(info) as f:
            for _ in range(3):
                print("   ", f.readline().decode("utf-8", "replace").strip()[:400])

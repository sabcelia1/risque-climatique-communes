"""Diagnostic des erreurs 503 de Gemini : quelle requête passe ?"""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from google import genai
from google.genai import types, errors
from pydantic import BaseModel
from llm import cle_api

class Ping(BaseModel):
    reponse: str

client = genai.Client(api_key=cle_api(), http_options=types.HttpOptions(timeout=40_000))
variantes = {
    "texte simple": types.GenerateContentConfig(),
    "consigne systeme": types.GenerateContentConfig(system_instruction="Réponds brièvement."),
    "json sans schema": types.GenerateContentConfig(response_mime_type="application/json"),
    "json + schema": types.GenerateContentConfig(response_mime_type="application/json", response_schema=Ping),
}
for modele in ["gemini-flash-latest", "gemini-3.1-flash-lite", "gemini-2.5-flash", "gemini-3.8-flash", "gemini-2.5-flash-lite"]:
    for nom, cfg in variantes.items():
        t = time.time()
        try:
            r = client.models.generate_content(model=modele, contents="Dis bonjour en un mot.", config=cfg)
            print(f"OK   {modele:<24} {nom:<18} {time.time()-t:5.1f}s : {r.text.strip()[:60]!r}", flush=True)
        except Exception as e:
            code = getattr(e, "code", "")
            print(f"ERR  {modele:<24} {nom:<18} {time.time()-t:5.1f}s : {type(e).__name__} {code} {str(e)[:220]}", flush=True)

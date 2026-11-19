"""Accès au modèle de langage Gemini (API Google AI Studio).

La clé API est lue dans la variable d'environnement GEMINI_API_KEY, ou dans le fichier
secrets/gemini.env (ligne GEMINI_API_KEY=...), exclu de Git. Elle n'est jamais écrite
dans le code ni dans les journaux.

Le modèle est choisi par GEMINI_MODEL ; à défaut, le premier modèle disponible de
MODELES_PAR_DEFAUT (gratuits, famille Flash) est utilisé.
"""

import json
import os
import time

from config import ROOT_DIR

MODELES_PAR_DEFAUT = ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]
FICHIER_CLE = ROOT_DIR / "secrets" / "gemini.env"
PAUSE_ENTRE_APPELS_S = 4          # respecte les quotas du niveau gratuit


class LLMIndisponible(Exception):
    pass


def cle_api() -> str | None:
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]
    if FICHIER_CLE.exists():
        for ligne in FICHIER_CLE.read_text(encoding="utf-8").splitlines():
            if ligne.strip().startswith("GEMINI_API_KEY="):
                return ligne.split("=", 1)[1].strip().strip('"')
    return None


class Gemini:
    """Génère une réponse JSON conforme à un schéma (pydantic), avec nouvelles tentatives."""

    def __init__(self, modele: str | None = None):
        from google import genai

        cle = cle_api()
        if not cle:
            raise LLMIndisponible("clé Gemini introuvable : voir docs/guide_gemini.md")
        self.client = genai.Client(api_key=cle)
        self.candidats = [modele or os.environ.get("GEMINI_MODEL")] if (modele or os.environ.get("GEMINI_MODEL")) \
            else list(MODELES_PAR_DEFAUT)
        self.modele = None
        self._dernier_appel = 0.0

    def json(self, consigne: str, contenu: str, schema, temperature: float = 0.2) -> dict:
        from google.genai import errors, types

        config = types.GenerateContentConfig(system_instruction=consigne, temperature=temperature,
                                             response_mime_type="application/json", response_schema=schema)
        for essai in range(5):
            attente = PAUSE_ENTRE_APPELS_S - (time.time() - self._dernier_appel)
            if attente > 0:
                time.sleep(attente)
            modele = self.modele or self.candidats[0]
            try:
                self._dernier_appel = time.time()
                reponse = self.client.models.generate_content(model=modele, contents=contenu, config=config)
                self.modele = modele
                return json.loads(reponse.text)
            except errors.ClientError as e:
                if e.code == 404 and not self.modele and len(self.candidats) > 1:
                    print(f"  modèle {modele} indisponible, essai du suivant")
                    self.candidats.pop(0)
                    continue
                if e.code == 429:                                  # quota : on patiente
                    time.sleep(20 * (essai + 1))
                    continue
                raise LLMIndisponible(f"erreur Gemini {e.code} : {str(e)[:200]}") from e
            except errors.ServerError:
                time.sleep(10 * (essai + 1))
            except json.JSONDecodeError:
                continue
        raise LLMIndisponible("Gemini n'a pas répondu après plusieurs tentatives")


class FauxLLM:
    """Remplaçant de Gemini pour les tests : renvoie des réponses préparées, dans l'ordre."""

    modele = "faux-llm"

    def __init__(self, reponses: list[dict]):
        self.reponses = list(reponses)
        self.appels = []

    def json(self, consigne, contenu, schema, temperature=0.2):
        self.appels.append(contenu)
        return self.reponses.pop(0)

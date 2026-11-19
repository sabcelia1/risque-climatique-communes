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

MODELES_PAR_DEFAUT = ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite",
                      "gemini-3-flash-preview", "gemini-2.5-flash"]
FICHIER_CLE = ROOT_DIR / "secrets" / "gemini.env"
PAUSE_ENTRE_APPELS_S = 4          # respecte les quotas du niveau gratuit
DELAI_APPEL_MS = 90_000            # un appel bloqué est abandonné au bout de 90 s


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
        from google.genai import types

        cle = cle_api()
        if not cle:
            raise LLMIndisponible("clé Gemini introuvable : voir docs/guide_gemini.md")
        self.client = genai.Client(api_key=cle, http_options=types.HttpOptions(timeout=DELAI_APPEL_MS))
        self.candidats = [modele or os.environ.get("GEMINI_MODEL")] if (modele or os.environ.get("GEMINI_MODEL")) \
            else list(MODELES_PAR_DEFAUT)
        self.modele = None
        self._dernier_appel = 0.0

    def json(self, consigne: str, contenu: str, schema, temperature: float = 0.2) -> dict:
        from google.genai import errors, types

        config = types.GenerateContentConfig(system_instruction=consigne, temperature=temperature,
                                             response_mime_type="application/json", response_schema=schema)
        echecs_serveur = 0
        for essai in range(8):
            attente = PAUSE_ENTRE_APPELS_S - (time.time() - self._dernier_appel)
            if attente > 0:
                time.sleep(attente)
            modele = self.candidats[0]
            debut = time.time()
            try:
                self._dernier_appel = time.time()
                reponse = self.client.models.generate_content(model=modele, contents=contenu, config=config)
                self.modele = modele
                return json.loads(reponse.text)
            except errors.ClientError as e:
                print(f"  [gemini] {modele} : erreur {e.code} après {time.time() - debut:.0f} s", flush=True)
                if e.code == 404 and len(self.candidats) > 1:
                    self._suivant()
                    continue
                if e.code == 429:                                  # quota : on patiente
                    time.sleep(20 * (essai + 1))
                    continue
                raise LLMIndisponible(f"erreur Gemini {e.code} : {str(e)[:300]}") from e
            except errors.ServerError as e:
                print(f"  [gemini] {modele} : erreur serveur {e.code}", flush=True)
                echecs_serveur += 1
                if echecs_serveur >= 2 and len(self.candidats) > 1:     # modèle surchargé : on change
                    self._suivant()
                    echecs_serveur = 0
                    continue
                time.sleep(10)
            except (json.JSONDecodeError, TypeError):
                print(f"  [gemini] {modele} : réponse non JSON", flush=True)
                continue
            except Exception as e:                                # délai dépassé, réseau
                print(f"  [gemini] {modele} : {type(e).__name__} après {time.time() - debut:.0f} s", flush=True)
                time.sleep(5)
        raise LLMIndisponible("Gemini n'a pas répondu après plusieurs tentatives")

    def _suivant(self):
        ancien = self.candidats.pop(0)
        self.modele = None
        print(f"  [gemini] {ancien} écarté, essai de {self.candidats[0]}", flush=True)


class FauxLLM:
    """Remplaçant de Gemini pour les tests : renvoie des réponses préparées, dans l'ordre."""

    modele = "faux-llm"

    def __init__(self, reponses: list[dict]):
        self.reponses = list(reponses)
        self.appels = []

    def json(self, consigne, contenu, schema, temperature=0.2):
        self.appels.append(contenu)
        return self.reponses.pop(0)


if __name__ == "__main__":
    # Test de connexion : modèles accessibles avec la clé, puis un appel minimal
    from pydantic import BaseModel

    class Ping(BaseModel):
        reponse: str

    llm = Gemini()
    noms = [m.name.removeprefix("models/") for m in llm.client.models.list()]
    flash = sorted(n for n in noms if "flash" in n and not any(k in n for k in ("image", "audio", "tts", "live")))
    print(f"{len(noms)} modèles accessibles, dont Flash (texte) : {', '.join(flash)}")
    if not os.environ.get("GEMINI_MODEL"):
        llm.candidats = [m for m in MODELES_PAR_DEFAUT if m in noms] or flash[:1]
    t = time.time()
    print("Réponse :", llm.json("Réponds en JSON.", "Dis bonjour en un mot.", Ping), f"({llm.modele}, {time.time() - t:.1f} s)")

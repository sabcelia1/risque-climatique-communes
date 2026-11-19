"""Contrôle d'ancrage : tout nombre écrit par le modèle de langage doit figurer dans les faits.

Les nombres sont extraits au format français (« 12 345 », « 12,5 % », « 1er »), puis
comparés aux nombres présents dans le dossier factuel transmis au modèle.
"""

import re

# 12 345 / 12 345,6 / 12,5 / 2018 / 1er : séparateur de milliers = espace (fine ou insécable)
_NOMBRE = re.compile(r"(?<![\w,.])(\d{1,3}(?:[   ]\d{3})+|\d+)(?:,(\d+))?(?![\d])")


def extraire_nombres(texte: str) -> list[float]:
    nombres = []
    for entier, decimales in _NOMBRE.findall(texte or ""):
        entier = re.sub(r"[   ]", "", entier)
        nombres.append(float(f"{entier}.{decimales}" if decimales else entier))
    return nombres


def nombres_autorises(faits) -> set[float]:
    """Tous les nombres présents dans les faits (dictionnaires, listes et textes imbriqués)."""
    autorises: set[float] = set()

    def parcourir(x):
        if isinstance(x, dict):
            for k, v in x.items():
                parcourir(k)
                parcourir(v)
        elif isinstance(x, (list, tuple)):
            for v in x:
                parcourir(v)
        elif isinstance(x, (int, float)) and not isinstance(x, bool):
            autorises.add(float(x))
        elif isinstance(x, str):
            autorises.update(extraire_nombres(x))

    parcourir(faits)
    return autorises


def verifier(texte: str, faits) -> list[float]:
    """Renvoie les nombres du texte absents des faits (liste vide = texte ancré)."""
    autorises = nombres_autorises(faits)
    return sorted({n for n in extraire_nombres(texte) if n not in autorises})

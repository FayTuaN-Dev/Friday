"""Réflexion à la demande : qwen3 sans réflexion répond en ~2 s mais se trompe sur les calculs
en plusieurs étapes (3/6 justes sur un banc, contre 6/6 en réfléchissant, en ~11 s).
On ne réfléchit donc que si l'utilisateur le demande, ou pour un calcul."""

import re

from friday.voice.wake import normalize

# « réfléchis », « analyse », « prends ton temps »… (début de mots, sans accents)
ASK_TO_THINK = (
    "reflechi", "analyse", "prends ton temps", "prends le temps", "verifie bien", "raisonne",
    "pas a pas", "etape par etape", "en detail", "creuse",
)  # fmt: skip
# Mots d'une question de calcul (avec au moins deux nombres)
CALCULATION = (
    "combien", "calcul", "moyenne", "pourcent", "total", "somme", "difference", "jours entre",
    "quelle heure", "interet", "partag", "divis", "multipli", "rembours", "vitesse", "reste t il",
    "ca fait", "au centime",
)  # fmt: skip
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


AUTOMATIC = "(Message automatique"  # briefing, fin de tâche : pas une question de l'utilisateur


def own_words(text: str) -> str:
    """Ce que l'utilisateur a dit lui-même, sans les pièces jointes ajoutées par Friday
    (« [Fichier joint : …] », « [Texte copié par l'utilisateur : … ] » : leurs nombres ne
    font pas de sa demande un calcul) ni les messages automatiques."""
    if text.startswith(AUTOMATIC):
        return ""
    if "\n]\n" in text:  # bloc du texte copié : la demande vient après
        text = text.rsplit("\n]\n", 1)[1]
    lines = [line for line in text.splitlines()
             if not (line.startswith("[") and line.rstrip().endswith("]"))]  # fmt: skip
    return "\n".join(lines)


def needs_thinking(text: str) -> bool:
    text = own_words(text)
    words = f" {normalize(text)} "
    if any(f" {key}" in words for key in ASK_TO_THINK):
        return True
    numbers = len(_NUMBER.findall(text))
    is_calculation = "%" in text or any(f" {key}" in words for key in CALCULATION)
    return numbers >= 2 and is_calculation

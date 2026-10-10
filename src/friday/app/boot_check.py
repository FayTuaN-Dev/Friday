"""L'auto-test du démarrage (J4) : quand Friday est prête, ce dont elle dépend défile sur la
sphère (Ollama, modèles, carte graphique, voix, micro, Google, sauvegarde), puis « EN
LIGNE ». Mêmes vérifications que Réglages → Diagnostic (app/diagnostic.py), sans celles qui
ne peuvent pas encore être bonnes au démarrage (vitesse pas mesurée, modèle pas chargé…)."""

import subprocess
from collections.abc import Callable
from pathlib import Path

from friday.app.diagnostic import BAD, OK, WARN, Line, collect

SKIPPED = {"Vitesse", "Chargement", "Limites Claude"}  # jamais « bonnes » au démarrage
SHORT = {"Modèle de conversation": "Modèle", "Modèle de la mémoire": "Mémoire",
         "Micro et écoute": "Micro"}  # fmt: skip


def google_line(google) -> list[Line]:
    if google is None:
        return []
    try:
        connected = bool(google.connected)
    except Exception:
        connected = False
    if connected:
        return [("Google", OK, "agenda et mails connectés")]
    return [("Google", WARN, "connexion expirée : reconnectez-la dans Réglages → Comptes")]


def boot_lines(components, settings, data_dir: Path,
               run: Callable = subprocess.run) -> list[Line]:  # fmt: skip
    lines = [(SHORT.get(topic, topic), state, detail)
             for topic, state, detail in collect(components, settings, data_dir, run)
             if topic not in SKIPPED]  # fmt: skip
    return lines + google_line(getattr(components, "google", None))


def problems(lines: list[Line]) -> list[Line]:
    return [line for line in lines if line[1] in (WARN, BAD)]


def summary(lines: list[Line]) -> str:
    """La phrase affichée sous la sphère quand quelque chose ne va pas (rien si tout va bien)."""
    wrong = problems(lines)
    if not wrong:
        return ""
    return "Au démarrage : " + " ; ".join(f"{topic} : {detail}" for topic, _, detail in wrong)

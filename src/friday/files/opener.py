"""Ouvrir un fichier avec son application habituelle, ou le montrer dans l'explorateur."""

import os
import subprocess
from datetime import datetime
from pathlib import Path

from friday.brain.prompts import MOIS

# Ces fichiers lancent des programmes : on ne les ouvre pas (open_app sert à ça).
RISKY = {".exe", ".msi", ".bat", ".cmd", ".ps1", ".vbs", ".js", ".lnk", ".scr", ".com", ".reg"}


class CannotOpen(Exception):
    pass


def open_file(path: Path) -> None:
    if not path.exists():
        raise CannotOpen(f"« {path} » est introuvable.")
    if path.suffix.lower() in RISKY:
        raise CannotOpen(f"« {path.name} » est un programme : je ne l'ouvre pas par sécurité.")
    os.startfile(path)  # noqa: S606 (application associée au type de fichier)


def reveal_file(path: Path) -> None:
    """Ouvre le dossier dans l'explorateur, le fichier sélectionné."""
    if not path.exists():
        raise CannotOpen(f"« {path} » est introuvable.")
    subprocess.Popen(["explorer", "/select,", str(path)])  # noqa: S603, S607


def human_size(size: int) -> str:
    for unit in ("octets", "Ko", "Mo", "Go"):
        if size < 1024 or unit == "Go":
            if unit == "octets":
                return f"{size:.0f} {unit}"
            return f"{size:.1f} {unit}".replace(".", ",")
        size /= 1024
    return ""


def short_date(moment: datetime) -> str:
    """« 12 mars 2026 »"""
    return f"{moment.day} {MOIS[moment.month - 1]} {moment.year}"

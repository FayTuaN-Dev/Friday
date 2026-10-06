"""Lecture et écriture du fichier .env : il reste LA référence des réglages (modifiable à la
main), l'écran de réglages ne fait que changer des valeurs en gardant les commentaires."""

from pathlib import Path

from dotenv import dotenv_values, set_key

from friday.core.config import ROOT_DIR

ENV_PATH = ROOT_DIR / ".env"


def read_env(path: Path | None = None) -> dict[str, str]:
    path = path or ENV_PATH
    if not path.is_file():
        return {}
    return {key: value or "" for key, value in dotenv_values(path).items()}


def update_env(values: dict[str, str], path: Path | None = None) -> None:
    """Change (ou ajoute à la fin) les clés données ; le reste du fichier est conservé."""
    path = path or ENV_PATH
    path.touch(exist_ok=True)
    for key, value in values.items():
        set_key(str(path), key, str(value), quote_mode="never")

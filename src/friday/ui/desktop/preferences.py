"""Préférences d'interface choisies dans l'application (couleur…), gardées entre deux lancements.

Rangées dans data/interface.json (non versionné). Elles priment sur le .env (FRIDAY_COLOR),
qui ne sert que de valeur de départ.
"""

import json
import logging
from pathlib import Path

from friday.core.config import DATA_DIR

log = logging.getLogger(__name__)
PATH = DATA_DIR / "interface.json"


def load(path: Path = PATH) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as error:
        log.warning("Préférences d'interface illisibles (%s) : valeurs par défaut", error)
        return {}


def save(values: dict, path: Path = PATH) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({**load(path), **values}, indent=2), encoding="utf-8")
    except OSError as error:
        log.warning("Impossible d'enregistrer les préférences d'interface : %s", error)

"""Démarrage avec Windows (S1) : une entrée « Friday » dans la clé Run de l'utilisateur
(HKCU, sans droits administrateur). Friday s'y lance discrètement (`--tray` : seulement
l'icône près de l'horloge), avec pythonw (pas de console noire)."""

import logging
import sys
from pathlib import Path

log = logging.getLogger(__name__)

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
NAME = "Friday"


def command(executable: str = sys.executable) -> str:
    """La commande lancée à l'ouverture de session : `pythonw -m friday --tray`."""
    python = Path(executable)
    windowless = python.with_name("pythonw.exe")
    return f'"{windowless if windowless.exists() else python}" -m friday --tray'


def current() -> str | None:
    """La commande enregistrée (None : Friday ne démarre pas avec Windows)."""
    if sys.platform != "win32":
        return None
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            return winreg.QueryValueEx(key, NAME)[0]
    except OSError:
        return None


def sync(enabled: bool, wanted: str | None = None) -> bool:
    """Met la clé Run d'accord avec le réglage. Renvoie True si quelque chose a changé."""
    if sys.platform != "win32":
        return False
    import winreg

    wanted = wanted or command()
    existing = current()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled and existing != wanted:
                winreg.SetValueEx(key, NAME, 0, winreg.REG_SZ, wanted)
                log.info("Démarrage avec Windows activé : %s", wanted)
                return True
            if not enabled and existing is not None:
                winreg.DeleteValue(key, NAME)
                log.info("Démarrage avec Windows désactivé")
                return True
    except OSError as error:
        log.warning("Démarrage avec Windows : clé Run inaccessible (%s)", error)
    return False

"""Dossiers où Friday a le droit de chercher : Documents, Bureau, Téléchargements, Images,
Musique (avec tous leurs sous-dossiers).

Leur vrai emplacement est demandé à Windows (dossiers connus) : il suit une éventuelle
redirection vers OneDrive ou un autre disque.
"""

import ctypes
import logging
import sys
import uuid
from ctypes import wintypes
from pathlib import Path

log = logging.getLogger(__name__)

# Nom affiché → (identifiant Windows du dossier connu, nom de repli dans le dossier perso)
KNOWN_FOLDERS = {
    "Documents": ("FDD39AD0-238F-46AF-ADB4-6C85480369C7", "Documents"),
    "Bureau": ("B4BFCC3A-DB2C-424C-B029-7FE99A87C641", "Desktop"),
    "Téléchargements": ("374DE290-123F-4565-9164-39C4925E467B", "Downloads"),
    "Images": ("33E28130-4E1E-4676-835A-98395C3BC3BB", "Pictures"),
    "Musique": ("4BD8D571-6D19-48D3-BE97-422220080E43", "Music"),
}


class _GUID(ctypes.Structure):
    _fields_ = [
        ("data1", wintypes.DWORD),
        ("data2", wintypes.WORD),
        ("data3", wintypes.WORD),
        ("data4", ctypes.c_ubyte * 8),
    ]


def _known_folder(guid_text: str) -> Path | None:
    if sys.platform != "win32":
        return None
    u = uuid.UUID(guid_text)
    guid = _GUID(u.fields[0], u.fields[1], u.fields[2], (ctypes.c_ubyte * 8)(*u.bytes[8:]))
    pointer = ctypes.c_wchar_p()
    try:
        if ctypes.windll.shell32.SHGetKnownFolderPath(
            ctypes.byref(guid), 0, None, ctypes.byref(pointer)
        ):
            return None
        return Path(pointer.value)
    except OSError as error:
        log.debug("Dossier connu %s introuvable : %s", guid_text, error)
        return None
    finally:
        if pointer:
            ctypes.windll.ole32.CoTaskMemFree(pointer)


def search_folders() -> dict[str, Path]:
    """Nom → chemin des dossiers autorisés qui existent."""
    folders = {}
    for name, (guid, fallback) in KNOWN_FOLDERS.items():
        path = _known_folder(guid) or Path.home() / fallback
        if path.is_dir():
            folders[name] = path
    return folders

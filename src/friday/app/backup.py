"""Sauvegarde automatique de data/ : une fois par jour (au démarrage, puis toutes les 24 h), une
archive datée dans data/sauvegardes, et une copie dans un dossier choisi (BACKUP_DIR : clé
USB, OneDrive…) s'il est réglé. Les 7 dernières sont gardées.

Ce qui compte et ne se retrouve pas ailleurs : journal de trading, plans et stratégies,
mémoire, agenda et notes, réglages. Pas les caches, ni les modèles, ni la bibliothèque (ses
PDF sont tes originaux, ailleurs sur le PC). Les bases SQLite sont copiées par l'outil de
sauvegarde de SQLite : une copie cohérente, même si Friday écrit au même moment.
"""

import logging
import shutil
import sqlite3
import tempfile
import threading
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger(__name__)

# mcp_comptes : jetons des connecteurs MCP, jamais copiés (comme ceux de Google)
SKIP = {"cache", "bibliotheque", "models", "voices", "trading_claude", "sauvegardes", "mcp_comptes"}
SKIP_FILES = {
    "library.db",  # se reconstruit depuis la bibliothèque
    # Clés de connexion (Google, Spotify) : jamais copiées (la copie peut aller sur
    # OneDrive) ; perdues, il suffit de reconnecter le compte une fois
    "google_token.json", "google_credentials.json", "spotify_token.json", ".gitkeep",
    "mcp.json",  # connecteurs : leurs « env » peuvent porter des clés
}  # fmt: skip
KEEP = 7
EVERY = timedelta(hours=24)


def files_to_save(data_dir: Path) -> list[Path]:
    found = []
    for path in sorted(data_dir.rglob("*")):
        relative = path.relative_to(data_dir)
        if path.is_file() and relative.parts[0] not in SKIP and path.name not in SKIP_FILES \
                and not path.name.endswith(("-wal", "-shm", "-journal")):  # fmt: skip
            found.append(path)
    return found


def backup(data_dir: Path, folder: Path | None = None, copy_to: Path | None = None,
           now: datetime | None = None) -> Path:  # fmt: skip
    """Crée l'archive ; renvoie son chemin."""
    folder = folder or data_dir / "sauvegardes"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"friday-{(now or datetime.now()):%Y-%m-%d-%H%M}.zip"
    with tempfile.TemporaryDirectory() as scratch, zipfile.ZipFile(
            target, "w", zipfile.ZIP_DEFLATED) as archive:  # fmt: skip
        for path in files_to_save(data_dir):
            name = path.relative_to(data_dir).as_posix()
            if path.suffix == ".db":
                copy = Path(scratch) / path.name
                source, dest = sqlite3.connect(path), sqlite3.connect(copy)
                try:
                    source.backup(dest)
                finally:  # (le « with » de sqlite3 ne ferme pas : fichier bloqué sous Windows)
                    source.close()
                    dest.close()
                archive.write(copy, name)
            else:
                archive.write(path, name)
    for old in sorted(folder.glob("friday-*.zip"))[:-KEEP]:
        old.unlink()
    if copy_to is not None:
        try:
            copy_to.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, copy_to / target.name)
            for old in sorted(copy_to.glob("friday-*.zip"))[:-KEEP]:
                old.unlink()
        except OSError as error:  # clé USB absente… : la sauvegarde locale reste
            log.warning("Copie de la sauvegarde vers %s impossible : %s", copy_to, error)
    log.info("Sauvegarde : %s (%d Ko)", target.name, target.stat().st_size // 1024)
    return target


def last_backup(data_dir: Path) -> Path | None:
    found = sorted((data_dir / "sauvegardes").glob("friday-*.zip"))
    return found[-1] if found else None


class DailyBackup:
    """Au démarrage si la dernière a plus de 24 h, puis toutes les 24 h."""

    def __init__(self, data_dir: Path, copy_to: Path | None = None) -> None:
        self.data_dir, self.copy_to = data_dir, copy_to
        self._stop = threading.Event()

    def due(self, now: datetime | None = None) -> bool:
        last = last_backup(self.data_dir)
        if last is None:
            return True
        return (now or datetime.now()) - datetime.fromtimestamp(last.stat().st_mtime) >= EVERY

    def run_now(self) -> Path | None:
        try:
            return backup(self.data_dir, copy_to=self.copy_to)
        except Exception:
            log.exception("Sauvegarde impossible")
            return None

    def start(self) -> None:
        def loop() -> None:
            while not self._stop.is_set():
                if self.due():
                    self.run_now()
                self._stop.wait(3600)

        threading.Thread(target=loop, daemon=True, name="backup").start()

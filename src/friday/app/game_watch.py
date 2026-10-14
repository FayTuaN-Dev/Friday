"""Mode jeu automatique (G2) : toutes les 5 s, Friday regarde quels programmes occupent la
carte graphique. Un jeu (rangé dans une bibliothèque Steam, Epic… ou gros consommateur de
mémoire graphique) se lance → elle passe d'elle-même en mode jeu.

Rappelée pendant la partie (« Friday, reviens »), elle ne se remet pas en pause pour ce même
jeu : il est « excusé » jusqu'à sa fermeture."""

import logging
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass

import psutil

log = logging.getLogger(__name__)

EVERY = 5.0  # secondes entre deux regards
GAME_MB = 1000  # au-delà, un programme qui n'est pas dans la liste blanche est un jeu
LIBRARY_MB = 150  # dans une bibliothèque de jeux : un peu de carte graphique suffit
LIBRARIES = ("\\steamapps\\common\\", "\\epic games\\", "\\gog galaxy\\games\\",
             "\\riot games\\", "\\xboxgames\\", "\\ubisoft game launcher\\games\\",
             "\\ea games\\")  # fmt: skip
# Gros consommateurs de carte graphique qui ne sont pas des jeux
NOT_GAMES = {
    "dwm", "explorer", "csrss", "chrome", "msedge", "firefox", "opera", "brave", "vivaldi",
    "steam", "steamwebhelper", "epicgameslauncher", "epicwebhelper", "discord", "spotify",
    "obs64", "ollama", "ollama app", "llama-server", "python", "pythonw", "friday",
    "qtwebengineprocess", "nzxt cam", "wallpaper32", "wallpaper64", "webwallpaper32",
    "lghub", "lghub_system_tray", "nvcontainer", "nvidia overlay", "medal", "outplayed",
}  # fmt: skip


@dataclass(frozen=True)
class Game:
    pid: int
    name: str  # « Counter-Strike 2 » (dossier de la bibliothèque) ou le programme


def stem(name: str) -> str:
    return name.lower().removesuffix(".exe")


def as_game(pid: int, exe: str, used_mb: float, ignored: set[str]) -> Game | None:
    """Ce programme est-il un jeu ? (exe : chemin complet ou nom)."""
    name = stem(os.path.basename(exe))
    if name in NOT_GAMES or name in ignored:
        return None
    path = exe.lower()
    for library in LIBRARIES:
        if library in path and used_mb >= LIBRARY_MB:
            folder = exe[path.index(library) + len(library) :].split("\\")[0]
            return Game(pid, folder or name)
    return Game(pid, os.path.basename(exe).removesuffix(".exe")) if used_mb >= GAME_MB else None


def find_game(usage: dict[int, int], ignored: set[str], skip: set[int]) -> Game | None:
    """Le jeu qui tourne (le plus gourmand), parmi les programmes de `usage` {pid : octets}."""
    for pid, used in sorted(usage.items(), key=lambda item: -item[1]):
        if pid in skip:
            continue
        try:
            exe = psutil.Process(pid).exe()
        except (psutil.Error, OSError):
            continue
        if game := as_game(pid, exe, used / 2**20, ignored):
            return game
    return None


class GameWatch:
    def __init__(self, on_game: Callable[[Game], None], is_paused: Callable[[], bool],
                 ignored: tuple[str, ...] = (), usage=None) -> None:  # fmt: skip
        if usage is None:
            from friday.tools.pc.gpu_memory import GpuMemory

            usage = GpuMemory().by_pid
        self.on_game = on_game
        self.is_paused = is_paused
        self.ignored = {stem(n) for n in ignored}
        self.usage = usage
        self.excused: set[int] = set()  # jeux pendant lesquels l'utilisateur a rappelé Friday
        self._own = {os.getpid()}
        self._stop = threading.Event()

    def start(self) -> None:
        threading.Thread(target=self._loop, daemon=True, name="game-watch").start()

    def stop(self) -> None:
        self._stop.set()

    def excuse_running_games(self) -> None:
        """Friday rappelée pendant une partie : ce jeu-là ne la remet plus en pause."""
        usage = self.usage()
        while game := find_game(usage, self.ignored, self._own | self.excused):
            self.excused.add(game.pid)
            log.info("Mode jeu : %s excusé jusqu'à sa fermeture", game.name)

    def check(self) -> Game | None:
        usage = self.usage()
        self.excused &= set(usage)  # un jeu fermé n'est plus excusé
        if self.is_paused():
            return None
        game = find_game(usage, self.ignored, self._own | self.excused)
        if game is not None:
            self.excused.add(game.pid)  # une seule fois par partie
            log.info("Mode jeu automatique : %s (pid %d)", game.name, game.pid)
            self.on_game(game)
        return game

    def _loop(self) -> None:
        while not self._stop.wait(EVERY):
            try:
                self.check()
            except Exception:  # un regard raté ne doit jamais arrêter la surveillance
                log.exception("Mode jeu automatique : regard impossible")

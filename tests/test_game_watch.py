from types import SimpleNamespace

from friday.app import game_watch
from friday.app.game_watch import Game, GameWatch, as_game

MB = 2**20
STEAM = r"D:\SteamLibrary\steamapps\common\Counter-Strike Global Offensive\game\bin\cs2.exe"
EXES = {
    10: r"C:\Windows\System32\dwm.exe",
    11: r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    12: STEAM,
    13: r"C:\Games\Minecraft\javaw.exe",
    14: r"D:\SteamLibrary\steamapps\common\wallpaper_engine\wallpaper64.exe",
}


def test_what_counts_as_a_game():
    assert as_game(12, STEAM, 300, set()) == Game(12, "Counter-Strike Global Offensive")
    assert as_game(12, STEAM, 50, set()) is None  # pas encore sur la carte graphique
    assert as_game(13, EXES[13], 1500, set()) == Game(13, "javaw")  # gros consommateur
    assert as_game(13, EXES[13], 400, set()) is None
    assert as_game(11, EXES[11], 2000, set()) is None  # un navigateur n'est pas un jeu
    assert as_game(14, EXES[14], 600, set()) is None  # fond d'écran animé
    assert as_game(13, EXES[13], 1500, {"javaw"}) is None  # ignoré dans les réglages


def watcher(monkeypatch, usage, paused=False):
    monkeypatch.setattr(game_watch.psutil, "Process", lambda pid: SimpleNamespace(
        exe=lambda: EXES[pid]))  # fmt: skip
    found = []
    watch = GameWatch(found.append, lambda: paused, usage=lambda: dict(usage))
    return watch, found


def test_a_game_starting_triggers_the_game_mode_once(monkeypatch):
    usage = {10: 350 * MB, 11: 300 * MB}
    watch, found = watcher(monkeypatch, usage)
    assert watch.check() is None and found == []
    usage[12] = 900 * MB  # Counter-Strike se lance
    assert watch.check().name == "Counter-Strike Global Offensive"
    assert watch.check() is None  # une seule fois par partie
    assert len(found) == 1
    del usage[12]  # partie finie…
    watch.check()
    usage[12] = 900 * MB  # …et relancée plus tard : de nouveau détectée
    assert watch.check() is not None


def test_nothing_happens_while_already_paused(monkeypatch):
    watch, found = watcher(monkeypatch, {12: 900 * MB}, paused=True)
    assert watch.check() is None and found == []


def test_a_game_running_when_friday_is_called_back_is_excused(monkeypatch):
    usage = {13: 1500 * MB}
    watch, found = watcher(monkeypatch, usage)
    watch.excuse_running_games()  # « Friday, reviens » pendant la partie
    assert watch.check() is None and found == []


def test_game_mode_posts_the_game_to_the_assistant_thread():
    from friday.app.game_mode import GameMode

    posted, interrupted = [], []
    assistant = SimpleNamespace(post=lambda kind, payload: posted.append((kind, payload)),
                                interrupt=lambda: interrupted.append(True))  # fmt: skip
    GameMode(assistant)._detected(Game(12, "Counter-Strike 2"))
    assert interrupted == [True] and posted == [("game", "Counter-Strike 2")]

"""J4 : sphère de particules (nuage → sphère au démarrage), auto-test qui défile, carte
« En écoute », et choix du cœur (sphère / hologramme) changé à chaud et gardé."""

import json
from types import SimpleNamespace

import numpy as np
from fakes import SETTINGS
from test_desktop import app, make_window  # noqa: F401  (QApplication)

from friday.app.boot_check import boot_lines, google_line, summary
from friday.app.diagnostic import BAD, OK, WARN
from friday.app.events import AssistantState
from friday.tools.pc.now_playing import Track, app_name
from friday.ui.desktop.widgets.boot_log import BootLog, row
from friday.ui.desktop.widgets.now_playing import NowPlayingCard
from friday.ui.desktop.widgets.sphere import POINTS, ParticleSphere, converge, fibonacci_sphere


def test_the_sphere_gathers_when_friday_is_ready():
    points = fibonacci_sphere(POINTS)
    assert points.shape == (POINTS, 3) and np.allclose(np.linalg.norm(points, axis=1), 1)
    delays = np.linspace(0, 1, 50)
    assert converge(0.0, delays).max() == 0 and converge(1.0, delays).min() == 1
    sphere = ParticleSphere()
    assert not sphere.converging and sphere.progress == 0  # nuage pendant le chargement
    far = np.linalg.norm(sphere.positions(), axis=1)
    sphere.set_state(AssistantState.IDLE)
    assert sphere.converging
    sphere.progress = 1.0
    near = np.linalg.norm(sphere.positions(), axis=1)
    assert far.std() > 0.3 and abs(near.mean() - 1) < 0.05  # dispersé, puis une sphère
    sphere.level = 1.0  # la voix déforme la sphère
    assert np.linalg.norm(sphere.positions(), axis=1).std() > near.std()
    sphere.resize(300, 300)
    assert not sphere.grab().isNull()


def test_the_boot_check_skips_what_cannot_be_ready_yet(tmp_path):
    def nvidia(*args, **kwargs):
        return SimpleNamespace(stdout="RTX 3070, 1000, 8192, 45")

    lines = boot_lines(None, SETTINGS, tmp_path, run=nvidia)
    topics = [topic for topic, _, _ in lines]
    assert "Vitesse" not in topics and "Limites Claude" not in topics
    assert "Carte graphique" in topics and "Micro" in topics
    connected = SimpleNamespace(connected=True)
    assert google_line(connected) == [("Google", OK, "agenda et mails connectés")]
    assert google_line(SimpleNamespace(connected=False))[0][1] == WARN
    assert google_line(None) == []
    assert summary([("Ollama", OK, "ok")]) == ""
    assert summary([("Ollama", BAD, "injoignable"), ("Google", WARN, "expirée")]) == (
        "Au démarrage : Ollama : injoignable ; Google : expirée")  # fmt: skip


def test_the_boot_log_scrolls_line_by_line():
    assert row("Micro", OK)[:2] == ("MICRO", "OK")
    assert row("Google", WARN)[1] == "À VOIR" and row("Ollama", BAD)[1] == "ÉCHEC"
    log = BootLog()
    log.start([("Ollama", OK, ""), ("Micro", OK, "")])
    assert log.isVisible() and not log._trouble
    for _ in range(3):
        log._step()
    assert "FRIDAY EN LIGNE" in log.text() and "OLLAMA" in log.text()


def test_now_playing_card():
    assert app_name("Spotify.exe") == "Spotify" and app_name("MSEdge") == "Edge"
    assert app_name("308046B0AF4A39CB!Spotify") == "Spotify"
    card = NowPlayingCard()  # sans Windows derrière
    assert not card.has_track
    card.show_track(Track("Spotify", "Let's Get It Started", "Måneskin", True, 73.5, 147.0))
    assert card.has_track and card.head.text() == "EN ÉCOUTE · SPOTIFY"
    assert card.title.toolTip() == "Let's Get It Started" and card.artist.text() == "Måneskin"
    assert card.title.text().startswith("Let's Get")  # coupé « … » s'il est trop long
    assert 495 <= card.bar.value() <= 520  # la moitié du morceau
    card.show_track(None)
    assert not card.has_track


def test_the_core_style_is_changed_live_and_kept(tmp_path):
    window = make_window(tmp_path)
    assert window.orb_style == "sphere" and isinstance(window.orb, ParticleSphere)
    window.set_orb_style("holo")
    assert window.orb_style == "holo" and not isinstance(window.orb, ParticleSphere)
    saved = json.loads((tmp_path / "interface.json").read_text("utf-8"))
    assert saved["orb"] == "holo"
    again = make_window(tmp_path)  # gardé au prochain lancement
    assert again.orb_style == "holo"
    window.set_orb_style("n'importe quoi")
    assert window.orb_style == "holo"
    window._side_panels()
    assert not window.playing.isVisible()  # fenêtre normale : pas de panneaux latéraux

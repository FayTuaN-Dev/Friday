import os
import sys
from types import SimpleNamespace

# Les tests de l'interface tournent sans écran (CI)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    session.config.friday_status = int(exitstatus)


def pytest_unconfigure(config):
    """Résumé affiché : on sort tout de suite avec le bon code. Constaté (CI, M1) : tous les
    tests passaient, puis Python plantait en démontant Qt (des dizaines de fenêtres de test,
    leur moteur web, leurs fils) : violation d'accès, et la CI échouait. os._exit ne suffit pas
    (Windows décharge encore Qt, et c'est là que ça plante) : TerminateProcess, sans nettoyage."""
    status = getattr(config, "friday_status", None)
    if status is None:
        return
    sys.stdout.flush()
    sys.stderr.flush()
    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p  # sinon tronqué en 32 bits
        kernel32.TerminateProcess.argtypes = (ctypes.c_void_p, ctypes.c_uint)
        kernel32.TerminateProcess(kernel32.GetCurrentProcess(), status)
    os._exit(status)


@pytest.fixture(autouse=True)
def no_real_sonar(monkeypatch):
    """Jamais le vrai SteelSeries Sonar du PC : un test a déjà baissé son volume à 15 %."""
    from friday.tools.pc import sonar

    monkeypatch.setattr(sonar.Sonar, "find", classmethod(lambda cls, *a, **k: None))


@pytest.fixture(autouse=True)
def no_real_pc_stats(monkeypatch):
    """Jamais nvidia-smi ni les vrais disques : les cartes du PC lisent des valeurs fixes."""
    from friday.app import pc_stats

    monkeypatch.setattr(pc_stats, "read_gpu", lambda run=None: None)
    monkeypatch.setattr(pc_stats.PcStats, "__init__", fake_stats_init)


def fake_stats_init(self, gpu=None, disks=None, pinger=None):
    self._gpu = gpu or (lambda: None)
    self._disks = disks or (lambda: [])
    self._ping = pinger or (lambda: None)  # jamais de connexion vers Internet
    self._failures = self._reads = 0
    self._last_ping = None


@pytest.fixture(autouse=True)
def no_real_friday_status(monkeypatch):
    """Ni le vrai Ollama ni le vrai Pi pour les cartes Friday et Pi : rien de chargé, pas de Pi."""
    from friday.app import friday_status

    reader = SimpleNamespace(read=lambda: friday_status.Status([]))
    monkeypatch.setattr(friday_status, "from_settings", lambda settings: reader)


@pytest.fixture(autouse=True)
def drop_main_windows():
    """Après chaque test, ses fenêtres de Friday sont détruites : laissées en vie, chacune
    était re-stylée à chaque nouvelle fenêtre (thème appliqué à toute l'application), et les
    tests d'animation finissaient par manquer leurs délais."""
    yield
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return
    from friday.ui.desktop.main_window import MainWindow

    for window in app.topLevelWidgets():
        if isinstance(window, MainWindow):
            window.playing.close_poller()
            window.side.close()
            window.deleteLater()
    app.processEvents()


@pytest.fixture(autouse=True)
def no_real_trading_glance(monkeypatch):
    """La carte Trading des fenêtres de test ne lit ni Yahoo ni le calendrier en ligne."""
    from friday.app import trading_glance

    monkeypatch.setattr(trading_glance, "from_trading", lambda trading: None)

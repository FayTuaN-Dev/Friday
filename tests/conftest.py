import os
import sys

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


def fake_stats_init(self, gpu=None, disks=None):
    self._gpu = gpu or (lambda: None)
    self._disks = disks or (lambda: [])
    self._failures = 0

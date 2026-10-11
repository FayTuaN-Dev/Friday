import os

# Les tests de l'interface tournent sans écran (CI)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(autouse=True)
def no_real_sonar(monkeypatch):
    """Jamais le vrai SteelSeries Sonar du PC : un test a déjà baissé son volume à 15 %."""
    from friday.tools.pc import sonar

    monkeypatch.setattr(sonar.Sonar, "find", classmethod(lambda cls, *a, **k: None))

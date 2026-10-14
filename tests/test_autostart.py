import sys
import types

from PySide6.QtTest import QTest
from test_desktop import app, make_window

from friday.core import autostart
from friday.ui.desktop.single_instance import InstanceServer, wake_running


def test_windows_starts_friday_hidden_without_a_console(tmp_path):
    python = tmp_path / "python.exe"
    (tmp_path / "pythonw.exe").write_text("")
    assert autostart.command(str(python)) == f'"{tmp_path / "pythonw.exe"}" -m friday --tray'


class FakeRegistry:
    """Le registre de Windows, en mémoire : les tests ne touchent jamais la vraie clé Run."""

    HKEY_CURRENT_USER, KEY_SET_VALUE, REG_SZ = 1, 2, 1

    def __init__(self):
        self.values = {}

    def OpenKey(self, *args):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def QueryValueEx(self, key, name):
        if name not in self.values:
            raise OSError("absent")
        return self.values[name], 1

    def SetValueEx(self, key, name, _, kind, value):
        self.values[name] = value

    def DeleteValue(self, key, name):
        del self.values[name]


def test_the_setting_drives_the_run_key(monkeypatch):
    registry = FakeRegistry()
    monkeypatch.setitem(sys.modules, "winreg", registry)
    monkeypatch.setattr(autostart.sys, "platform", "win32")
    assert autostart.sync(True, "friday --tray") and registry.values == {"Friday": "friday --tray"}
    assert not autostart.sync(True, "friday --tray")  # déjà en place : rien à refaire
    assert autostart.sync(False) and registry.values == {}
    assert not autostart.sync(False)


def test_a_second_friday_wakes_the_first_instead_of_starting():
    import subprocess

    name = "friday-test-instance"
    assert not wake_running(name)  # personne : celle-ci démarre
    server = InstanceServer(name)
    shown = []
    server.show_requested.connect(lambda: shown.append(True))
    second = subprocess.Popen(  # une seconde Friday, dans son propre programme
        [sys.executable, "-c", "from PySide6.QtCore import QCoreApplication; "
         "app = QCoreApplication([]); "
         "from friday.ui.desktop.single_instance import wake_running; "
         f"print(wake_running({name!r}))"],
        stdout=subprocess.PIPE, text=True,
    )  # fmt: skip
    for _ in range(200):
        if shown and second.poll() is not None:
            break
        QTest.qWait(25)
    assert second.communicate(timeout=10)[0].strip() == "True"  # elle s'arrête…
    assert shown == [True]  # …et la première se montre
    server.server.close()


def test_the_cross_hides_friday_and_only_the_menu_quits():
    w = make_window()
    w.show()
    w.notifier.hidden_once = types.MethodType(lambda self: setattr(self, "told", True), w.notifier)
    w.close()  # la croix
    app.processEvents()
    assert w.isHidden() and getattr(w.notifier, "told", False)
    w._quitting = True  # « Quitter Friday » (sans arrêter l'application des tests)
    shut = []
    w.assistant.shutdown = lambda: shut.append(True)
    w.close()
    assert shut == [True]

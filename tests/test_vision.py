from types import SimpleNamespace

import ollama
import pytest

from friday.tools.screen import AskClaudeAboutScreenTool, LookAtScreenTool
from friday.vision.capture import pick_monitor
from friday.vision.reader import ScreenReader

MONITORS = [
    {"left": -1920, "top": 0, "width": 3840, "height": 1080},  # tous les écrans
    {"left": 0, "top": 0, "width": 1920, "height": 1080},  # principal
    {"left": -1920, "top": 0, "width": 1920, "height": 1080},  # à gauche
]


def test_picks_the_screen_under_the_mouse():
    assert pick_monitor(MONITORS, (-500, 300)) is MONITORS[2]
    assert pick_monitor(MONITORS, (100, 100)) is MONITORS[1]
    assert pick_monitor(MONITORS, None) is MONITORS[1]  # inconnue : écran principal


class FakeClient:
    def __init__(self, answer="Fenêtre d'erreur : « Erreur 0x80070070 »", error=None):
        self.answer, self.error, self.calls = answer, error, []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(message=SimpleNamespace(content=self.answer))


def test_reader_sends_image_and_frees_video_memory():
    client = FakeClient()
    text = ScreenReader(client, "vision").describe(b"png", "c'est quoi cette erreur ?")
    call = client.calls[0]
    assert "0x80070070" in text
    assert call["messages"][0]["images"] == [b"png"] and call["keep_alive"] == 0
    assert call["options"]["num_predict"] == 600  # constaté : 9 000 caractères en 35 s
    assert "c'est quoi cette erreur ?" in call["messages"][0]["content"]


def test_look_at_screen_tool():
    tool = LookAtScreenTool(ScreenReader(FakeClient(), "vision"), capture=lambda: b"png")
    result = tool.run("c'est quoi cette erreur ?")
    assert "0x80070070" in result.text and "calculs" in result.text
    assert result.display.kind == "screen" and result.display.data["image"] == b"png"
    missing = FakeClient(error=ollama.ResponseError("not found", 404))
    assert "ollama pull vision" in LookAtScreenTool(ScreenReader(missing, "vision"),
                                                    capture=lambda: b"png").run().text  # fmt: skip


def test_claude_fallback_captures_before_asking(tmp_path):
    shots = iter([b"avant la question", b"apres"])
    claude = SimpleNamespace(job=SimpleNamespace(workspace=tmp_path), tasks=[])
    claude.run = lambda task: claude.tasks.append(task) or SimpleNamespace(text="lancé")
    tool = AskClaudeAboutScreenTool(claude, capture=lambda: next(shots))
    assert tool.needs_confirmation and "en ligne" in tool.confirmation({"question": "?"})
    tool.run("que vois-tu ?")
    saved = list((tmp_path / "captures").glob("ecran-*.png"))
    assert saved[0].read_bytes() == b"avant la question"  # pas la carte « Je lance ? »
    assert str(saved[0]) in claude.tasks[0] and "que vois-tu ?" in claude.tasks[0]


def test_real_capture_is_a_png():
    from friday.vision.capture import capture_screen

    try:
        image = capture_screen(max_width=800)
    except Exception as error:  # machine sans écran (serveur)
        pytest.skip(f"capture impossible ici : {error}")
    assert image.startswith(b"\x89PNG")


def test_screen_popup_renders():
    from PySide6.QtCore import QBuffer, QIODevice
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtWidgets import QApplication

    from friday.tools.screen import screen_display
    from friday.ui.desktop.popups.screen import ScreenPopup

    QApplication.instance() or QApplication([])
    image = QImage(320, 180, QImage.Format_RGB32)
    image.fill(QColor("#336699"))
    buffer = QBuffer()
    buffer.open(QIODevice.WriteOnly)
    image.save(buffer, "PNG")
    popup = ScreenPopup(screen_display(bytes(buffer.data())))
    popup.show()
    popup.close()

"""Les images envoyées à Friday : collées dans la demande (file:///…, C:\\…), collées dans la
barre (Ctrl+V) ou glissées, puis décrites par le modèle de vision local. Sans réseau ni vrai
presse-papier : le modèle et le presse-papier sont simulés."""

from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote

from test_vision import FakeClient

from friday.app.attachments import Attachments, pasted_files
from friday.brain.safety import mentions_attachment
from friday.brain.thinking import own_words
from friday.vision.capture import load_image
from friday.vision.reader import ScreenReader


def png(path: Path, width: int = 40, height: int = 20) -> Path:
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (width, height), "white").save(path)
    return path


def test_pasted_files_are_taken_out_of_the_request(tmp_path):
    clip = png(tmp_path / "{6EC5}" / "capture écran.png")
    url = "file:///" + quote(clip.as_posix(), safe="/:")
    text, found = pasted_files(f"{url} regarde cette image et choisis 5 numéros")
    assert found == [clip] and text == "regarde cette image et choisis 5 numéros"
    photo = png(tmp_path / "mes photos" / "tirage.jpg")
    text, found = pasted_files(f"compare avec {photo} stp")
    assert found == [photo] and text == "compare avec stp"
    absent = "C:\\nulle\\part.png"
    assert pasted_files(f"et {absent} ?") == (f"et {absent} ?", [])  # pas un fichier : intact


def test_images_are_described_by_the_local_vision_model(tmp_path):
    seen = []

    def look(path, question):
        seen.append((path, question))
        return "Grille EuroMillions : derniers tirages 3, 17, 22, 41, 48 ; étoiles 2 et 9"

    clip = png(tmp_path / "grille.png")
    notes = tmp_path / "notes.txt"
    notes.write_text("x", "utf-8")
    attachments = Attachments(look=look)
    attachments.add(notes)
    wrapped = attachments.wrap(f"file:///{clip.as_posix()} choisis 5 numéros et 2 étoiles")
    assert seen == [(clip, "choisis 5 numéros et 2 étoiles")]  # la question, sans l'adresse
    assert f"[Fichier joint : {notes}]" in wrapped and "[Image jointe : grille.png" in wrapped
    assert "étoiles 2 et 9" in wrapped and wrapped.endswith("choisis 5 numéros et 2 étoiles")
    assert mentions_attachment(wrapped)  # contenu externe : actions confirmées ensuite
    assert own_words(wrapped) == "choisis 5 numéros et 2 étoiles"  # ses chiffres ne comptent pas

    def broken(path, question):
        raise RuntimeError("modèle absent")

    failed = Attachments(look=broken)
    failed.add(clip)
    assert "pas pu la regarder : modèle absent" in failed.wrap("et ça ?")
    plain = Attachments()  # sans vision : un simple fichier joint
    plain.add(clip)
    assert plain.wrap("et ça ?").startswith(f"[Fichier joint : {clip}]")


def test_reader_describes_an_image_not_the_screen(tmp_path):
    client = FakeClient("Une grille de loto")
    ScreenReader(client, "vision").describe(b"png", "choisis", screen=False)
    prompt = client.calls[0]["messages"][0]["content"]
    assert "image que l'utilisateur t'envoie" in prompt and "écran" not in prompt
    big = png(tmp_path / "grande.png", 3200, 1000)
    from io import BytesIO

    from PIL import Image

    assert Image.open(BytesIO(load_image(big))).size == (1600, 500)  # réduite comme l'écran


def test_ctrl_v_of_a_capture_attaches_it(tmp_path, monkeypatch):
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QImage, QKeyEvent, QKeySequence
    from PySide6.QtWidgets import QApplication

    from friday.ui.desktop.pasted_image import save_pasted
    from friday.ui.desktop.widgets import input_bar

    QApplication.instance() or QApplication([])
    image = QImage(30, 20, QImage.Format_RGB32)
    image.fill(Qt.white)
    mime = SimpleNamespace(hasImage=lambda: True, hasText=lambda: False)
    clipboard = SimpleNamespace(mimeData=lambda: mime, image=lambda: image)
    monkeypatch.setattr(input_bar.QApplication, "clipboard", lambda: clipboard)
    bar = input_bar.InputBar("F9")
    pasted = []
    bar.image_pasted.connect(pasted.append)
    paste = QKeyEvent(QEvent.KeyPress, Qt.Key_V, Qt.ControlModifier)
    assert paste.matches(QKeySequence.Paste)
    assert bar.eventFilter(bar.edit, paste) and pasted == [image]

    folder = tmp_path / "images"
    paths = [save_pasted(image, folder, keep=2) for _ in range(3)]
    assert all(paths) and sorted(folder.iterdir()) == paths[1:]  # les plus anciennes partent
    assert save_pasted(QImage(), folder) is None

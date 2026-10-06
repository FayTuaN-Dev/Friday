import os

import numpy as np

from friday.library.chunker import PASSAGE_CHARS, split
from friday.library.library import Library
from friday.library.store import LibraryStore
from friday.tools.library import ListLibraryTool, SearchLibraryTool, UpdateLibraryTool

TOPICS = ("pip", "levier", "cuisine")


class FakeEmbedder:
    """Sens = présence des mots-thèmes (assez pour tester la fusion)."""

    def _vector(self, text):
        v = np.array([1.0 if t in text.lower() else 0.0 for t in TOPICS] + [0.1])
        return v / np.linalg.norm(v)

    def documents(self, texts):
        return np.array([self._vector(t) for t in texts])

    def query(self, text):
        return self._vector(text)


def make_library(tmp_path):
    folder = tmp_path / "bibliotheque"
    folder.mkdir()
    (folder / "forex.md").write_text(
        "Un pip est la plus petite variation d'un cours, 0,0001 pour EUR/USD.\n\n"
        "L'effet de levier multiplie les gains comme les pertes.", "utf-8")  # fmt: skip
    (folder / "recettes.txt").write_text("La cuisine française aime le beurre.", "utf-8")
    return Library(folder, LibraryStore(tmp_path / "library.db"), FakeEmbedder())


def test_split_keeps_pages_and_size():
    text = "[Page 1]\n" + ("Phrase sur le Forex. " * 30) + "\n\n[Page 2]\n" + "Le pip. " * 80
    passages = split(text)
    assert passages[0].page == 1 and passages[-1].page == 2
    assert all(len(p.text) <= PASSAGE_CHARS + 50 for p in passages)
    assert not any("[Page" in p.text for p in passages)


def test_sync_indexes_new_changed_and_removed_files(tmp_path):
    library = make_library(tmp_path)
    assert sorted(library.sync()["added"]) == ["forex.md", "recettes.txt"]
    assert library.sync() == {"added": [], "removed": [], "failed": []}  # rien de neuf
    forex = library.folder / "forex.md"
    forex.write_text("Le pip et le spread.", "utf-8")
    os.utime(forex, (forex.stat().st_atime, forex.stat().st_mtime + 10))
    (library.folder / "recettes.txt").unlink()
    (library.folder / "vide.pdf").write_bytes(b"pas un pdf")
    report = library.sync()
    assert report["added"] == ["forex.md"] and report["removed"] == ["recettes.txt"]
    assert report["failed"] and "vide.pdf" in report["failed"][0]


def test_hybrid_search_finds_by_meaning_and_by_exact_word(tmp_path):
    library = make_library(tmp_path)
    library.sync()
    assert "pip" in library.search("c'est quoi un pip ?")[0].text
    assert "EUR/USD" in library.search("EUR USD")[0].text  # mot exact (FTS5)
    assert library.search("astronomie des galaxies") == []  # rien de pertinent


def test_retire_moves_the_file_instead_of_deleting_it(tmp_path):
    library = make_library(tmp_path)
    library.sync()
    target = library.retire(str(library.folder / "recettes.txt"))
    assert target.is_file() and target.parent.name == "_retires"
    assert [d.name for d in library.store.documents()] == ["forex.md"]
    assert library.sync()["added"] == []  # le dossier _retires n'est pas indexé


def test_add_files_copies_without_touching_originals(tmp_path):
    library = make_library(tmp_path)
    original = tmp_path / "cours.txt"
    original.write_text("Cours sur le levier.", "utf-8")
    copied = library.add_files([original, tmp_path / "image.png"])
    assert copied == [library.folder / "cours.txt"] and original.is_file()


def test_library_tools(tmp_path):
    library = make_library(tmp_path)
    search = SearchLibraryTool(library)
    assert "vide" in search.run("pip").text
    assert "forex.md" in UpdateLibraryTool(library).run().text
    result = search.run("effet de levier")
    assert "[forex.md]" in result.text and result.display.kind == "files"
    assert "2 document(s)" in ListLibraryTool(library).run().text


def test_settings_page_retires_after_two_clicks(tmp_path):
    from PySide6.QtWidgets import QApplication

    from friday.ui.desktop.settings.library_page import LibraryPage

    QApplication.instance() or QApplication([])
    library = make_library(tmp_path)
    library.sync()
    page = LibraryPage(library)
    assert "2 document(s)" in page.status.text()
    path = str(library.folder / "recettes.txt")
    page._remove(path)
    assert len(library.store.documents()) == 2  # premier clic : on demande confirmation
    page._remove(path)
    assert [d.name for d in library.store.documents()] == ["forex.md"]
    disabled = LibraryPage(None)
    texts = [label.text() for label in disabled.findChildren(type(page.status))]
    assert any("Bibliothèque désactivée" in t for t in texts)


def test_indexing_survives_a_closed_settings_page(tmp_path):
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication

    from friday.ui.desktop.settings.library_page import LibraryPage

    QApplication.instance() or QApplication([])
    library = make_library(tmp_path)
    page = LibraryPage(library)
    notify = page._notify
    page.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    report = library.sync(notify)  # la page n'existe plus : l'indexation va au bout
    assert sorted(report["added"]) == ["forex.md", "recettes.txt"]


def test_library_hint_only_when_it_knows_the_topic(tmp_path):
    library = make_library(tmp_path)
    assert library.hint("c'est quoi un pip ?") == ""  # vide : pas encore indexée
    library.sync()
    library._known = ("", [])  # oublie la réponse gardée pour la question
    hint = library.hint("c'est quoi un pip ?")
    assert "forex.md" in hint and "cite le document" in hint
    assert library.auto_search("c'est quoi un pip ?") == (
        "search_library",
        {"query": "c'est quoi un pip ?"},
    )
    assert library.hint("raconte-moi une blague") == ""
    assert library.auto_search("raconte-moi une blague") is None
    # le présent : internet, jamais un exemple du livre donné comme cours actuel
    assert library.auto_search("quel est le cours du pip aujourd'hui ?") is None
    assert library.hint("le pip en ce moment") == ""

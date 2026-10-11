import os
from datetime import datetime
from pathlib import Path

import pytest

from friday.files.content_search import search_contents
from friday.files.opener import CannotOpen, human_size, open_file
from friday.files.search import FileFinder, Query
from friday.tools.file_search import OpenFileTool, SearchFilesTool


def make(path: Path, text: str = "x", when: datetime | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if when:
        os.utime(path, (when.timestamp(), when.timestamp()))
    return path


@pytest.fixture
def folders(tmp_path):
    docs, downloads = tmp_path / "Docs", tmp_path / "DL"
    make(docs / "Factures" / "Facture_EDF_2026.pdf", when=datetime(2026, 2, 10))
    make(docs / "Devis cuisine.docx", when=datetime(2026, 3, 14))
    make(docs / "devis salle de bain.txt", "Total : 3 200 euros, carrelage inclus",
         when=datetime(2025, 11, 2))  # fmt: skip
    make(downloads / "Photo vacances Bretagne.jpg", when=datetime(2025, 8, 1))
    make(downloads / "notes.txt", "rendez-vous chez le garagiste mardi")
    make(docs / "projet" / "node_modules" / "devis.js")  # dossier ignoré
    make(docs / ".cache" / "devis.txt")  # dossier caché ignoré
    return {"Documents": docs, "Téléchargements": downloads}


def names(entries):
    return [e.path.name for e in entries]


def test_query_parsing_separates_dates():
    q = Query.parse("mon devis de Mars 2026")
    assert q.words == ["devis"] and q.month == 3 and q.year == 2026


def test_finds_by_name_ignoring_accents_case_and_skipped_folders(folders):
    finder = FileFinder(folders)
    assert names(finder.find("devis")) == ["Devis cuisine.docx", "devis salle de bain.txt"]
    assert names(finder.find("facture edf")) == ["Facture_EDF_2026.pdf"]
    assert names(finder.find("photo vacances")) == ["Photo vacances Bretagne.jpg"]


def test_tolerates_small_typos(folders):
    assert names(FileFinder(folders).find("facure"))[0] == "Facture_EDF_2026.pdf"


def test_month_and_year_match_modification_date(folders):
    finder = FileFinder(folders)
    assert names(finder.find("devis mars"))[0] == "Devis cuisine.docx"
    assert names(finder.find("devis 2025"))[0] == "devis salle de bain.txt"
    assert names(finder.find("aout")) == ["Photo vacances Bretagne.jpg"]  # date seule


def test_kind_filter_and_most_recent(folders):
    finder = FileFinder(folders)
    assert names(finder.find("", kind="image")) == ["Photo vacances Bretagne.jpg"]
    assert names(finder.find("", kind="PDF")) == ["Facture_EDF_2026.pdf"]
    assert names(finder.find("introuvable")) == []


def test_content_search(folders):
    entries = FileFinder(folders).entries()
    found, partial = search_contents(entries, "carrelage")
    assert names(found) == ["devis salle de bain.txt"] and not partial
    assert names(search_contents(entries, "garagiste mardi")[0]) == ["notes.txt"]
    _, interrupted = search_contents(entries, "carrelage", budget=-1)
    assert interrupted


def test_search_tool_output_and_display(folders):
    tool = SearchFilesTool(FileFinder(folders))
    result = tool.run("devis")
    assert "[1] Devis cuisine.docx — Documents — modifié le 14 mars 2026" in result.text
    assert result.display.kind == "files" and len(result.display.data["files"]) == 2
    assert "Factures" in tool.run("edf").display.data["files"][0]["where"]
    assert "Propose de chercher aussi dans le contenu" in tool.run("carrelage").text
    assert "devis salle de bain.txt" in tool.run("carrelage", in_content=True).text


def test_open_file_refuses_programs_and_missing_files(tmp_path):
    with pytest.raises(CannotOpen, match="programme"):
        open_file(make(tmp_path / "setup.exe"))
    assert "introuvable" in OpenFileTool().run(str(tmp_path / "absent.pdf")).text


def test_human_size():
    assert human_size(512) == "512 octets"
    assert human_size(340 * 1024) == "340,0 Ko"
    assert human_size(5 * 1024**3) == "5,0 Go"


def test_files_popup_renders(folders):
    from PySide6.QtWidgets import QApplication

    from friday.ui.desktop.popups.files import FilesPopup

    QApplication.instance() or QApplication([])
    popup = FilesPopup(SearchFilesTool(FileFinder(folders)).run("devis").display)
    popup.show()
    popup.close()


def test_wrong_kind_guess_falls_back_to_any_type(folders):
    result = SearchFilesTool(FileFinder(folders)).run("devis cuisine", kind="pdf")  # c'est un .docx
    assert "Devis cuisine.docx" in result.text


def test_type_words_become_a_filter(folders):
    from friday.files.search import split_kind

    assert split_kind("mes derniers PDF", None) == ("mes derniers", "pdf")
    assert split_kind("photo vacances", "image") == ("vacances", "image")
    tool = SearchFilesTool(FileFinder(folders))
    result = tool.run("PDF", kind="pdf", in_content=True)  # ne cherche pas « pdf » dans le texte
    assert [f["name"] for f in result.display.data["files"]] == ["Facture_EDF_2026.pdf"]


def test_an_invented_path_is_found_by_its_name(folders, monkeypatch):
    """Constaté : « lance panda.png dans le dossier Download » → « /Download/panda.png »
    inventé par qwen ; le fichier était dans Téléchargements."""
    import friday.files.opener as opener

    opened = []
    monkeypatch.setattr(opener.os, "startfile", opened.append, raising=False)
    tool = OpenFileTool(FileFinder(folders))
    said = tool.run("/Download/Photo vacances Bretagne.jpg").text
    assert opened == [folders["Téléchargements"] / "Photo vacances Bretagne.jpg"]
    assert "Fichier ouvert" in said
    make(folders["Documents"] / "Archives" / "notes.txt")  # deux fichiers du même nom
    said = OpenFileTool(FileFinder(folders, cache_seconds=0)).run("/Download/notes.txt").text
    assert "Plusieurs fichiers « notes.txt »" in said and len(opened) == 1
    assert "introuvable" in tool.run("/Download/absent.pdf").text


def test_music_is_one_of_the_searched_folders():
    from friday.files.folders import KNOWN_FOLDERS

    assert KNOWN_FOLDERS["Musique"][1] == "Music"

"""Bibliothèque de trading de départ (PR E) : uniquement des documents légaux, sources citées."""

from types import SimpleNamespace

import httpx

from friday.library import catalog
from friday.library.catalog import CATALOG, FOLDER, Source, download, fetch_catalog


def response(json=None, content=b"", text=""):
    return SimpleNamespace(raise_for_status=lambda: None, json=lambda: json, content=content,
                           text=text)  # fmt: skip


def fake_get(url, params=None, headers=None, timeout=None, follow_redirects=False):
    assert "Friday-assistant" in headers["User-Agent"]  # identifié, comme Wikipédia le demande
    if params:  # API de Wikipédia
        title = params["titles"]
        page = {"title": title, "extract": f"{title} : " + "texte " * 200}
        return response({"query": {"pages": {"1": page}}})
    if url.endswith(".pdf"):
        return response(content=b"%PDF-1.7 contenu")
    return response(text="<html>page</html>")


def test_every_source_is_free_and_says_its_license():
    assert len(CATALOG) >= 20
    for source in CATALOG:
        assert source.license and source.publisher, source.title
        if source.kind == "wikipedia":
            assert "CC BY-SA" in source.license
    assert "CC BY-SA" in catalog.__doc__ and "piratés" in catalog.__doc__


def test_wikipedia_article_is_saved_with_its_source_and_license():
    data = download(Source("Wikipédia - MACD", "wikipedia", "MACD", "Wikipédia",
                           catalog.WIKI_LICENSE), fake_get).decode("utf-8")  # fmt: skip
    assert data.startswith("# Wikipédia - MACD")
    assert "https://fr.wikipedia.org/wiki/MACD" in data and "CC BY-SA 4.0" in data
    assert "MACD : texte" in data


def test_a_pdf_must_really_be_a_pdf():
    import pytest

    source = Source("AMF", "pdf", "https://x/a.pdf", "AMF", "gratuit")
    assert download(source, fake_get).startswith(b"%PDF")
    html = lambda *a, **k: response(content=b"<html>erreur</html>")  # noqa: E731
    with pytest.raises(ValueError, match="pas un PDF"):
        download(source, html)


def test_fetch_skips_what_is_there_and_reports_failures(tmp_path, monkeypatch):
    monkeypatch.setattr("trafilatura.extract", lambda html: "Contenu de la page. " * 30)
    first = fetch_catalog(tmp_path, fake_get, pause=lambda s: None)
    assert len(first["added"]) == len(CATALOG) and not first["failed"]
    files = list((tmp_path / FOLDER).iterdir())
    assert len(files) == len(CATALOG) and all("'" not in f.name for f in files)
    again = fetch_catalog(tmp_path, fake_get, pause=lambda s: None)
    assert again["added"] == [] and len(again["present"]) == len(CATALOG)  # rien de retéléchargé

    def offline(*args, **kwargs):
        raise httpx.ConnectError("hors ligne")

    report = fetch_catalog(tmp_path / "autre", offline, pause=lambda s: None)
    assert len(report["failed"]) == len(CATALOG) and "hors ligne" in report["failed"][0]


def test_library_downloads_then_indexes(tmp_path, monkeypatch):
    import time

    from test_library import FakeEmbedder

    from friday.library.library import Library
    from friday.library.store import LibraryStore

    monkeypatch.setattr(catalog, "CATALOG", CATALOG[:2])
    library = Library(tmp_path / "bib", LibraryStore(tmp_path / "l.db"), FakeEmbedder())
    progress = []

    def fetch(folder, on_progress):
        def note(title):
            progress.append(title)
            on_progress(title)

        return fetch_catalog(folder, fake_get, pause=lambda s: None, on_progress=note)

    library.add_trading_catalog(fetch=fetch)
    for _ in range(100):
        if len(library.store.documents()) == 2:
            break
        time.sleep(0.05)
    assert sorted(d.name for d in library.store.documents()) == sorted(
        s.filename for s in CATALOG[:2])  # fmt: skip
    assert library.indexing is None and len(progress) == 2

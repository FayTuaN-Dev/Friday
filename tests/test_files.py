import sys
from pathlib import Path

import pytest

from friday.app.attachments import Attachments
from friday.files.readers import Document, UnreadableFile, clean_path, read_document
from friday.tools.files import PART_CHARS, ReadFileTool, document_part


def minimal_pdf(text: str) -> bytes:
    """Petit PDF valide d'une page contenant `text` (sans bibliothèque d'écriture)."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return bytes(out)


def test_reads_text_with_old_windows_encoding(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_bytes("Café crème à 2 €".encode("cp1252"))
    assert read_document(path).text == "Café crème à 2 €"


def test_reads_pdf_with_pages(tmp_path):
    path = tmp_path / "devis.pdf"
    path.write_bytes(minimal_pdf("Devis total 1250 euros"))
    document = read_document(path)
    assert document.pages == 1
    assert "Devis total 1250 euros" in document.text and "[Page 1]" in document.text


def test_reads_word_paragraphs_and_tables(tmp_path):
    import docx

    word = docx.Document()
    word.add_paragraph("Compte rendu de réunion")
    table = word.add_table(rows=1, cols=2)
    table.cell(0, 0).text, table.cell(0, 1).text = "Budget", "3000"
    path = tmp_path / "cr.docx"
    word.save(path)
    text = read_document(path).text
    assert "Compte rendu de réunion" in text and "Budget | 3000" in text


@pytest.mark.parametrize(
    ("name", "content", "message"),
    [
        ("absent.pdf", None, "introuvable"),
        ("photo.jpg", b"\xff\xd8", "ne sais pas lire"),
        ("vide.txt", b"   ", "pas de texte"),
        ("faux.docx", b"pas un zip", "pas un document Word"),
    ],
)
def test_unreadable_files_explain_why(tmp_path, name, content, message):
    path = tmp_path / name
    if content is not None:
        path.write_bytes(content)
    with pytest.raises(UnreadableFile, match=message):
        read_document(path)


def test_long_document_is_read_by_parts():
    document = Document(Path("long.txt"), "a" * PART_CHARS + "b" * 10)
    first, last = document_part(document, 1), document_part(document, 2)
    assert "partie 1/2" in first and "part=2" in first
    assert "partie 2/2" in last and "bbbbbbbbbb" in last and "Suite non lue" not in last
    assert "partie 2/2" in document_part(document, 9)  # partie trop grande : la dernière


def test_read_file_tool(tmp_path):
    path = tmp_path / "liste.md"
    path.write_text("# Courses\n- lait", encoding="utf-8")
    result = ReadFileTool().run(f'"{path}"')  # guillemets tolérés
    assert "lait" in result.text and result.display.data["path"] == str(path)
    assert ReadFileTool().run(str(path), part=2).display is None  # pop-up une seule fois
    assert "introuvable" in ReadFileTool().run(str(tmp_path / "x.txt")).text


def test_clean_path_handles_quotes_and_home():
    assert clean_path("  'C:/a b/c.pdf' ") == Path("C:/a b/c.pdf")
    assert clean_path("~/x.txt") == Path.home() / "x.txt"


def test_attachments_are_joined_once():
    attachments = Attachments()
    attachments.add(Path("C:/a.pdf"))
    attachments.add(Path("C:/a.pdf"))
    wrapped = attachments.wrap("résume-le")
    assert wrapped.count("[Fichier joint") == 1 and wrapped.endswith("résume-le")
    assert attachments.wrap("et ensuite ?") == "et ensuite ?"


def test_clipboard_is_joined_only_when_the_request_mentions_it():
    from friday.files.clipboard import ClipboardContent, ClipboardError

    attachments = Attachments(lambda: ClipboardContent(text="bonjour a tous"))
    assert attachments.wrap("Quelle heure est-il ?") == "Quelle heure est-il ?"
    wrapped = attachments.wrap("Corrige ce que j'ai copié")
    assert "[Texte copié par l'utilisateur :\nbonjour a tous" in wrapped
    assert "presse-papier" in Attachments(lambda: ClipboardContent()).wrap("lis le presse-papier")
    files = Attachments(lambda: ClipboardContent(files=["C:/devis.pdf"]))
    assert "[Fichier copié par l'utilisateur : C:/devis.pdf]" in files.wrap("résume le copié")

    def busy():
        raise ClipboardError("occupé")

    assert Attachments(busy).wrap("traduis ce que j'ai copié") == "traduis ce que j'ai copié"


@pytest.mark.skipif(sys.platform != "win32", reason="presse-papier Windows")
def test_clipboard_round_trip_restores_user_clipboard():
    from friday.files.clipboard import ClipboardError, read_clipboard, write_clipboard
    from friday.tools.files import ReadClipboardTool

    try:
        saved = read_clipboard().text
        write_clipboard("Bonjour, ceci est un tést 😊")
        assert read_clipboard().text == "Bonjour, ceci est un tést 😊"
        assert "ceci est un tést" in ReadClipboardTool().run().text
    except ClipboardError:
        pytest.skip("presse-papier indisponible sur cette machine")
    finally:
        try:
            write_clipboard(saved)  # on rend son presse-papier à l'utilisateur
        except (ClipboardError, NameError):
            pass

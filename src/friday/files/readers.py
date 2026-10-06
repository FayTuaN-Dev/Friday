"""Lecture du texte d'un document : PDF, Word (.docx), texte et code."""

from dataclasses import dataclass
from pathlib import Path

TEXT_EXTENSIONS = {
    ".txt", ".md", ".csv", ".tsv", ".json", ".log", ".xml", ".html", ".htm", ".yaml", ".yml",
    ".ini", ".cfg", ".toml", ".srt", ".py", ".js", ".ts", ".css", ".sql", ".bat", ".ps1",
    ".sh", ".java", ".c", ".cpp", ".h", ".cs", ".rs", ".go", ".php", ".rb",
}  # fmt: skip
SUPPORTED = TEXT_EXTENSIONS | {".pdf", ".docx"}
MAX_BYTES = 50 * 1024 * 1024


class UnreadableFile(Exception):
    """Le message est destiné à l'utilisateur (via le LLM)."""


@dataclass
class Document:
    path: Path
    text: str
    pages: int | None = None  # PDF seulement


def clean_path(raw: str) -> Path:
    """Chemin donné par le LLM ou collé : guillemets et « ~ » tolérés."""
    return Path(raw.strip().strip("\"'")).expanduser()


def read_document(path: Path) -> Document:
    if not path.is_file():
        raise UnreadableFile(f"Le fichier « {path} » est introuvable.")
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED:
        raise UnreadableFile(
            f"Je ne sais pas lire les fichiers « {suffix or 'sans extension'} » "
            "(je lis les PDF, les documents Word et les fichiers texte)."
        )
    if path.stat().st_size > MAX_BYTES:
        raise UnreadableFile(f"« {path.name} » est trop volumineux (plus de 50 Mo).")
    if suffix == ".pdf":
        document = _read_pdf(path)
    elif suffix == ".docx":
        document = Document(path, _read_docx(path))
    else:
        document = Document(path, _read_text(path))
    if not document.text.strip():
        hint = " (sans doute un scan : c'est une image, pas du texte)" if suffix == ".pdf" else ""
        raise UnreadableFile(f"« {path.name} » ne contient pas de texte lisible{hint}.")
    return document


def _read_text(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1252"):  # cp1252 : anciens fichiers Windows
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _read_pdf(path: Path) -> Document:
    import logging

    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    # Avertissements techniques sans conséquence (polices) : ils noieraient le journal.
    logging.getLogger("pypdf").setLevel(logging.ERROR)

    try:
        reader = PdfReader(path)
        if reader.is_encrypted and not reader.decrypt(""):
            raise UnreadableFile(f"« {path.name} » est protégé par un mot de passe.")
        pages = [page.extract_text() or "" for page in reader.pages]
    except PdfReadError as error:
        raise UnreadableFile(f"« {path.name} » est un PDF abîmé ({error}).") from error
    text = "\n\n".join(f"[Page {i}]\n{p.strip()}" for i, p in enumerate(pages, 1) if p.strip())
    return Document(path, text, pages=len(pages))


def _read_docx(path: Path) -> str:
    import docx

    try:
        document = docx.Document(str(path))
    except Exception as error:  # fichier abîmé ou faux .docx
        raise UnreadableFile(f"« {path.name} » n'est pas un document Word lisible.") from error
    parts = [p.text for p in document.paragraphs if p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text.strip() for cell in row.cells))
    return "\n".join(parts)

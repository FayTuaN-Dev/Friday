"""Découpe un document en passages d'environ PASSAGE_CHARS caractères, en suivant les
paragraphes, avec un léger chevauchement (une idée à cheval sur deux passages n'est pas
perdue). Chaque passage garde son numéro de page (marques « [Page N] » des PDF)."""

import re
from dataclasses import dataclass

PASSAGE_CHARS = 900
OVERLAP_CHARS = 150
_PAGE = re.compile(r"^\[Page (\d+)\]$")


@dataclass
class Passage:
    text: str
    page: int | None


def _paragraphs(text: str) -> list[tuple[str, int | None]]:
    """(paragraphe, page) ; les paragraphes trop longs sont coupés en phrases."""
    page: int | None = None
    pieces: list[tuple[str, int | None]] = []
    for block in re.split(r"\n\s*\n", text):
        lines = []
        for line in block.splitlines():
            marker = _PAGE.match(line.strip())
            if marker:
                page = int(marker.group(1))
            elif line.strip():
                lines.append(line.strip())
        paragraph = " ".join(lines)
        while len(paragraph) > PASSAGE_CHARS:
            cut = paragraph.rfind(". ", 0, PASSAGE_CHARS)
            cut = cut + 1 if cut > PASSAGE_CHARS // 3 else PASSAGE_CHARS
            pieces.append((paragraph[:cut].strip(), page))
            paragraph = paragraph[cut:].strip()
        if paragraph:
            pieces.append((paragraph, page))
    return pieces


def split(text: str) -> list[Passage]:
    passages: list[Passage] = []
    current, page = "", None
    for paragraph, paragraph_page in _paragraphs(text):
        if current and len(current) + len(paragraph) + 1 > PASSAGE_CHARS:
            passages.append(Passage(current, page))
            tail = current[-OVERLAP_CHARS:]
            current = tail[tail.find(" ") + 1 :] if " " in tail else tail
            page = paragraph_page
        if not current:
            page = paragraph_page
        current = f"{current} {paragraph}".strip()
    if current:
        passages.append(Passage(current, page))
    return passages

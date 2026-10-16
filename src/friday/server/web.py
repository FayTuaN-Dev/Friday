"""Les fichiers de l'application du téléphone (server/web/), et ses icônes, dessinées une
fois au premier appel (pas d'image à garder dans le dépôt)."""

import io
from functools import cache
from pathlib import Path

WEB = Path(__file__).with_name("web")
FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/sw.js": ("sw.js", "text/javascript; charset=utf-8"),
    "/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json"),
}
ICONS = {"/icone-192.png": 192, "/icone-512.png": 512}
BACKGROUND, ACCENT = (11, 13, 18), (240, 168, 60)


@cache
def icon(size: int) -> bytes:
    """Un anneau doré sur fond sombre, comme la sphère de Friday (marge pour les icônes
    « masquables » d'Android, rognées en rond)."""
    from PIL import Image, ImageDraw

    big = size * 4  # dessiné en grand puis réduit : bords lisses
    image = Image.new("RGB", (big, big), BACKGROUND)
    draw = ImageDraw.Draw(image)
    for ratio, width, color in ((0.30, 0.045, ACCENT), (0.19, 0.022, (120, 86, 34))):
        r, w = big * ratio, int(big * width)
        draw.ellipse((big / 2 - r, big / 2 - r, big / 2 + r, big / 2 + r), outline=color, width=w)
    dot = big * 0.06
    draw.ellipse((big / 2 - dot, big / 2 - dot, big / 2 + dot, big / 2 + dot), fill=ACCENT)
    out = io.BytesIO()
    image.resize((size, size), Image.LANCZOS).save(out, "PNG")
    return out.getvalue()


def web_file(path: str) -> tuple[str, bytes] | None:
    """(type, contenu) d'un fichier de l'application, ou None."""
    path = path.split("?")[0]
    if path in ICONS:
        return "image/png", icon(ICONS[path])
    if path in FILES:
        name, kind = FILES[path]
        return kind, (WEB / name).read_bytes()
    return None

"""Une image collée dans la barre de saisie (Ctrl+V après une capture) : gardée en PNG dans
data/cache/images pour être jointe à la prochaine demande, comme un fichier glissé. Seules
les dernières sont gardées."""

from datetime import datetime
from pathlib import Path

KEEP = 20


def save_pasted(image, folder: Path, keep: int = KEEP) -> Path | None:
    """`image` : QImage du presse-papier ; None si elle n'a pas pu être enregistrée."""
    folder.mkdir(parents=True, exist_ok=True)
    stamp = f"{datetime.now():%Y%m%d-%H%M%S-%f}"
    n = 0  # l'horloge de Windows peut rendre deux fois le même instant (constaté en test)
    while (path := folder / f"collage-{stamp}-{n:03d}.png").exists():
        n += 1
    if image.isNull() or not image.save(str(path), "PNG"):
        return None
    for old in sorted(folder.glob("collage-*.png"))[:-keep]:
        old.unlink(missing_ok=True)
    return path

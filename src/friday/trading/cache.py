"""Cache sur disque des sources publiques (data/cache) : on n'interroge pas sans cesse des
sites gratuits (ForexFactory bloque au-delà : « 429 Too Many Requests », constaté), et en cas
de panne on garde la dernière version connue, en disant son âge."""

import time
from collections.abc import Callable
from pathlib import Path

STALE_MAX = 7 * 24 * 3600  # au-delà, une vieille copie ne sert plus


def cached_text(
    path: Path | None, fresh_for: float, download: Callable[[], str]
) -> tuple[str, float | None]:
    """(texte, âge en secondes si c'est une vieille copie faute de mieux, sinon None).

    Le texte en cache est rendu s'il a moins de `fresh_for` secondes ; sinon on télécharge ;
    si le téléchargement échoue, la copie (même ancienne) sert de secours ; sinon l'erreur
    remonte."""
    age = time.time() - path.stat().st_mtime if path is not None and path.is_file() else None
    if age is not None and age < fresh_for:
        return path.read_text("utf-8"), None
    try:
        text = download()
    except Exception:
        if age is not None and age < STALE_MAX:
            return path.read_text("utf-8"), age
        raise
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, "utf-8")
    return text, None


def age_note(source: str, age: float | None) -> str:
    if age is None:
        return ""
    hours = age / 3600
    when = f"{hours:.0f} h" if hours >= 1 else f"{age / 60:.0f} min"
    return f"{source} : source injoignable, dernière version connue (il y a {when})."

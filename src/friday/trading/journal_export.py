"""Fichiers du journal : export CSV (point-virgule et BOM, pour Excel en français) et captures
d'entrée (gardées sur le PC, jamais envoyées)."""

import csv
from pathlib import Path

CSV_COLUMNS = ("n°", "ouvert le", "instrument", "sens", "entrée", "stop", "objectif", "lots",
               "raison", "sortie", "résultat (R)", "setup", "plan respecté",
               "état d'esprit")  # fmt: skip


def export_csv(trades: list, path: Path) -> int:
    with open(path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file, delimiter=";")
        writer.writerow(CSV_COLUMNS)
        for t in trades:
            writer.writerow([t.id, t.opened_at, t.pair, t.direction, t.entry, t.stop, t.target,
                             t.lots, t.reason, t.exit,
                             "" if t.result_r is None else round(t.result_r, 2), t.setup,
                             {True: "oui", False: "non"}.get(t.plan_ok, ""), t.mood])  # fmt: skip
    return len(trades)


def save_capture(folder: Path, trade_id: int, image: bytes) -> str:
    """La capture d'entrée, gardée sur le PC (data/journal_captures) ; jamais envoyée."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"trade-{trade_id}.png"
    path.write_bytes(image)
    return str(path)

"""Le bilan du carnet des setups (P3), pour l'outil vocal et l'onglet « Setups » de la page
Trading : ce que les setups FERMÉS auraient donné, tous ensemble, puis selon l'avis de Claude."""

from types import SimpleNamespace

from friday.trading.backtest.report import Report

GROUPS = (("Tous les setups", lambda avis: True),
          ("Claude a dit OUI", lambda avis: avis == "oui"),
          ("Claude a dit NON", lambda avis: avis == "non"),
          ("Sans avis", lambda avis: avis not in ("oui", "non")))  # fmt: skip


def review(entries: list[dict]) -> tuple[list[Report], int]:
    """(un bilan par groupe de GROUPS, nombre de setups encore en cours)."""
    done = [e for e in entries if e["result_r"] is not None]
    reports = [Report(label, [SimpleNamespace(result_r=e["result_r"]) for e in done
                              if keep(e.get("avis"))])
               for label, keep in GROUPS]  # fmt: skip
    return reports, len(entries) - len(done)

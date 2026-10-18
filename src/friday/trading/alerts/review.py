"""Le bilan du carnet des setups (P3), pour l'outil vocal et l'onglet « Setups » de la page
Trading : ce que les setups FERMÉS auraient donné, tous ensemble, puis selon l'avis de Claude ;
leurs courbes en R au fil des sorties, et leur total par marché ou par stratégie."""

from types import SimpleNamespace

from friday.trading.backtest.report import Report

GROUPS = (("Tous les setups", lambda avis: True),
          ("Claude a dit OUI", lambda avis: avis == "oui"),
          ("Claude a dit NON", lambda avis: avis == "non"),
          ("Sans avis", lambda avis: avis not in ("oui", "non")))  # fmt: skip
CURVES = GROUPS[:3]  # « sans avis » : pas de courbe (elle n'apprend rien sur Claude)


def closed(entries: list[dict]) -> list[dict]:
    """Les setups terminés, dans l'ordre de leur sortie."""
    done = [e for e in entries if e["result_r"] is not None]
    return sorted(done, key=lambda e: (e.get("closed") or e["seen"], e["id"]))


def review(entries: list[dict]) -> tuple[list[Report], int]:
    """(un bilan par groupe de GROUPS, nombre de setups encore en cours)."""
    done = closed(entries)
    reports = [Report(label, [SimpleNamespace(result_r=e["result_r"]) for e in done
                              if keep(e.get("avis"))])
               for label, keep in GROUPS]  # fmt: skip
    return reports, len(entries) - len(done)


def curves(entries: list[dict]) -> list[tuple[dict, list[float]]]:
    """Après chaque setup terminé (dans l'ordre des sorties) : le total en R de chaque groupe
    de CURVES. Un groupe ne bouge qu'avec ses setups : les courbes partagent le même axe."""
    totals, points = [0.0] * len(CURVES), []
    for entry in closed(entries):
        for k, (_, keep) in enumerate(CURVES):
            if keep(entry.get("avis")):
                totals[k] += entry["result_r"]
        points.append((entry, list(totals)))
    return points


def totals_by(entries: list[dict], key) -> list[tuple[str, int, float]]:
    """(nom, setups terminés, total en R) par `key(entry)`, du meilleur au pire."""
    found: dict[str, list[float]] = {}
    for entry in closed(entries):
        found.setdefault(key(entry), []).append(entry["result_r"])
    rows = [(name, len(results), sum(results)) for name, results in found.items()]
    return sorted(rows, key=lambda row: row[2], reverse=True)

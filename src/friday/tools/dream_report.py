"""« Qu'as-tu fait cette nuit ? » : le dernier rapport du rêve nocturne (app/night_dream.py),
dit par le CODE (les faits ont été mis au tutoiement pendant la nuit). Les points à vérifier
sont posés en questions : c'est l'utilisateur qui décide (« oublie que… », « retiens
que… ») ; Friday n'a rien changé."""

import json
from datetime import date
from pathlib import Path

from friday.memory.day_log import day_name
from friday.tools.base import Tool, ToolResult
from friday.voice.wake import normalize

ASKS = ("fait cette nuit", "fais cette nuit", "rapport de la nuit", "ton reve", "tu as reve",
        "as tu reve", "rapport de menage", "fait la nuit derniere")  # fmt: skip


def asks_dream(text: str) -> bool:
    padded = f" {normalize(text)} "
    return any(f" {words} " in padded for words in ASKS)


def of_day(name: str) -> str:
    """« d'hier », « d'aujourd'hui », « d'avant-hier », « du jeudi 9 octobre »."""
    return f"d'{name}" if name in ("aujourd'hui", "hier", "avant-hier") else f"du {name}"


def joined(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " et " + items[-1]


def sentence(data: dict, today: date) -> str:
    """La phrase du rapport, construite par le code."""
    you = data.get("you", {})
    say = lambda text: you.get(text) or text.rstrip(".")  # noqa: E731
    count = data["exchanges"]
    read = f"nos {count} échanges" if count > 1 else "notre échange"
    name = day_name(date.fromisoformat(data["day"]), today)
    parts = [f"Cette nuit, j'ai relu {read} {of_day(name)}"]
    added = data.get("added", [])[:4]
    parts[0] += (" et j'ai retenu que " + joined([say(t) for t in added]) + "."
                 if added else " : rien de nouveau à retenir.")  # fmt: skip
    for pair in data.get("pairs", [])[:3]:
        a, b = say(pair["a"][1]), say(pair["b"][1])
        if pair["kind"] == "doublon":
            parts.append(f"« {a} » et « {b} » disent la même chose : j'en oublie un ?")
        else:
            parts.append(f"Une contradiction : {a}, ou {b} ? Lequel est juste ?")
    for _, text in data.get("stale", [])[:2]:
        parts.append(f"Est-ce toujours vrai que {say(text)} ?")
    for text, times in data.get("errors", [])[:1]:
        parts.append(f"Et une erreur revient souvent dans mon journal ({times} fois) : "
                     f"{text.replace('#', '…').rstrip('.')}.")  # fmt: skip
    if len(parts) == 1:
        parts.append("Rien à vérifier.")
    return " ".join(parts)


class DreamReportTool(Tool):
    name = "dream_report"
    description = (
        "Le rapport du rêve nocturne : ce que Friday a retenu en relisant la journée et les "
        "souvenirs à vérifier (« qu'as-tu fait cette nuit ? »)."
    )
    parameters = {}

    def __init__(self, folder: Path, today=date.today) -> None:
        self.folder, self.today = folder, today

    def label(self, args: dict) -> str:
        return "🌙 Rapport de la nuit"

    def run(self) -> ToolResult:
        try:
            data = json.loads((self.folder / "dernier.json").read_text("utf-8"))
        except (OSError, ValueError):
            return ToolResult("Dis EXACTEMENT : « Je n'ai pas encore rêvé : je relis nos "
                              "échanges la nuit, ou quand tu me laisses tranquille une "
                              "demi-heure. »")  # fmt: skip
        return ToolResult(f"Dis EXACTEMENT : « {sentence(data, self.today())} »")

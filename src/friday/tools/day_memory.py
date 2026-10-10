"""« De quoi on a parlé hier ? » : relit les échanges d'un jour (memory/day_log.py). Le jour
est calculé par le code ; le modèle résume, sans rien ajouter."""

from datetime import date

from friday.memory.day_log import DayLog, day_name, past_day
from friday.tools.base import Tool, ToolResult

SHOWN = 40  # échanges relus au plus (les derniers du jour)
SAID, REPLY = 160, 120  # caractères relus de chaque côté


def _cut(text: str, size: int) -> str:
    return text if len(text) <= size else text[: size - 1].rsplit(" ", 1)[0] + "…"


class RecallDayTool(Tool):
    name = "recall_day"
    description = (
        "Relit nos échanges d'un jour passé (« de quoi on a parlé hier ? », « qu'est-ce que je "
        "t'ai demandé lundi ? », « résume notre journée »)."
    )
    parameters = {
        "day": {
            "type": "string",
            "description": "Le jour tel que l'utilisateur l'a dit (hier, lundi, le 4 "
            "octobre…) ; vide pour aujourd'hui",
        },  # fmt: skip
    }

    def __init__(self, log: DayLog, today=date.today) -> None:
        self.log, self.today = log, today

    def label(self, args: dict) -> str:
        return f"🗓️ Nos échanges : {args.get('day') or 'aujourd hui'}"

    def run(self, day: str = "") -> ToolResult:
        today = self.today()
        wanted = past_day(day, today)
        name = day_name(wanted, today)
        exchanges = self.log.day(wanted)
        if not exchanges:
            return ToolResult(f"Dis EXACTEMENT : « Je n'ai aucun échange gardé pour {name}. »")
        lines = [f"- {when:%H:%M} tu as dit « {_cut(said, SAID)} »"
                 + (f" ; j'ai répondu « {_cut(reply, REPLY)} »" if reply else "")
                 for when, said, reply in exchanges[-SHOWN:]]  # fmt: skip
        skipped = len(exchanges) - SHOWN
        more = f" (les {SHOWN} derniers sur {len(exchanges)})" if skipped > 0 else ""
        return ToolResult(
            f"Nos échanges ({name}){more}, de {exchanges[0][0]:%H:%M} à "
            f"{exchanges[-1][0]:%H:%M} :\n" + "\n".join(lines) + "\n"
            f"Résume-les en 3 à 6 phrases, regroupés par sujet, en commençant par "
            f"« {name.capitalize()}, on a parlé de ». Tutoie l'utilisateur. N'invente rien, "
            "ne cite pas les heures une à une, n'ajoute aucun conseil."
        )

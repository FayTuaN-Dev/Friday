"""Ce qu'affiche une notification Windows quand une tâche de fond se termine (analyse de
Claude, alerte, rappel, briefing trading, traduction d'un plan…) : un titre et une phrase
courte. La fenêtre ne la montre que si Friday n'est pas au premier plan."""

from friday.tools.base import Display, ToolResult

TITLES = {
    "rappel": "⏰ Rappel",
    "alerte": "🔔 Alerte de trading",
    "briefing trading": "🌅 Briefing trading",
    "traduction du plan": "📝 Plan traduit",
    "rêve de la nuit": "🌙 Rêve de la nuit",
    "routine": "🔁 Routine",
    "atelier": "🧪 Compétence",
}
QUIET = {"rêve de la nuit"}  # notification seulement : Friday ne parle pas (3 h du matin)
MAX_CHARS = 200


def notification(task: str, result: ToolResult) -> Display:
    """Display « notification » : titre selon la tâche, texte = la phrase à dire si elle est
    donnée (« Dis EXACTEMENT : « … » »), sinon un résumé."""
    title = TITLES.get(task)
    start, end = result.text.find("« "), result.text.rfind(" »")
    if title is None:  # une analyse ou une tâche de Claude : son nom est la question
        title = "💬 Réponse de Claude prête"
        text = f"« {task[:120]} »"
    elif 0 <= start < end:  # la phrase à dire, guillemets imbriqués compris
        text = result.text[start + 2 : end]
    else:
        text = result.text
    text = " ".join(text.split())
    if len(text) > MAX_CHARS:
        text = text[: MAX_CHARS - 1].rsplit(" ", 1)[0] + "…"
    return Display("notification", title, {"text": text})

"""La mémoire des analyses de Claude : ses dernières analyses sur un instrument, jointes à une
nouvelle question (décochables dans l'aperçu), avec ce que le cours a fait depuis. Il peut dire
ce qui s'est confirmé, et se corriger. Comparaison en % sur le cours Yahoo des deux côtés (le
cours du graphique, recalé pour l'or, fausserait l'écart)."""

from datetime import datetime

from friday.trading.sent_log import Analysis

ANSWER_CHARS = 700  # d'une analyse passée, pas plus (quota)
KEEP = 2  # analyses passées jointes


def moved(then: float | None, now: float | None) -> str:
    if not then or not now:
        return ""
    change = round((now - then) / then * 100, 2) + 0.0
    return f" ; depuis, le cours a fait {change:+.2f} %".replace(".", ",")


def past_text(analyses: list[Analysis], price_now: float | None) -> str | None:
    if not analyses:
        return None
    lines = []
    for a in analyses[:KEEP]:
        when = datetime.fromisoformat(a.sent_at)
        answer = a.answer if len(a.answer) <= ANSWER_CHARS else a.answer[:ANSWER_CHARS] + "…"
        lines.append(f"- Le {when:%d/%m à %H:%M}{moved(a.price, price_now)}. Question : "
                     f"« {a.question} ». Ta réponse d'alors : « {answer} »")  # fmt: skip
    return "\n".join(lines)

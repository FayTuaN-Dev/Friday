"""Quand une alerte de trading se déclenche : carillon, puis Friday l'annonce de lui-même."""

from collections.abc import Callable

from friday.tools.base import ToolResult
from friday.trading.alerts.watcher import AlertWatcher
from friday.voice.speaker import Speaker


def start_alerts(
    watcher: AlertWatcher,
    speaker: Callable[[], Speaker | None],
    on_background: Callable[[str, ToolResult], None],
) -> None:
    def on_alert(text: str) -> None:
        if (voice := speaker()) is not None:
            voice.chime()
        on_background("alerte", ToolResult(
            f"ALERTE DE TRADING (surveillance locale). Dis EXACTEMENT : « {text} » N'ajoute "
            "aucun conseil : ce n'est ni un signal ni un ordre."))  # fmt: skip

    watcher.on_alert = on_alert
    watcher.start()

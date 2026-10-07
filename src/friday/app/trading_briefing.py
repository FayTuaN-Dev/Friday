"""Le briefing trading automatique (début de la plage de trading, en semaine) : carillon, puis
Friday le lit, comme un rappel."""

from collections.abc import Callable

from friday.tools.base import ToolResult
from friday.tools.trading_briefing import briefing_result
from friday.trading.briefing_service import BriefingService
from friday.voice.speaker import Speaker


def start_trading_briefing(
    service: BriefingService,
    speaker: Callable[[], Speaker | None],
    on_background: Callable[[str, ToolResult], None],
) -> None:
    def on_ready(briefing) -> None:
        if (voice := speaker()) is not None:
            voice.chime()
        on_background("briefing trading", briefing_result(briefing, automatic=True))

    service.start(on_ready)

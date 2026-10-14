"""Mode jeu (G1) : le cœur s'arrête de s'animer, il ne prend plus rien au jeu."""

from PySide6.QtCore import QTimer

from friday.app.events import AssistantState


def freeze(timer: QTimer, state: AssistantState) -> None:
    if state is AssistantState.PAUSED:
        timer.stop()
    elif not timer.isActive():
        timer.start()

from friday.brain.ollama_wait import wait_for_ollama


class LateOllama:
    """Ollama qui ne répond qu'après quelques essais (le PC finit de démarrer)."""

    def __init__(self, refusals):
        self.refusals = refusals
        self.calls = 0

    def list(self):
        self.calls += 1
        if self.calls <= self.refusals:
            raise ConnectionError("connexion refusée")
        return {"models": []}


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def sleep(self, seconds):
        self.now += seconds

    def __call__(self):
        return self.now


def test_friday_waits_for_ollama_to_start():
    clock, ollama = FakeClock(), LateOllama(refusals=5)
    assert wait_for_ollama(ollama, sleep=clock.sleep, clock=clock)
    assert ollama.calls == 6 and clock.now == 10.0


def test_no_wait_when_ollama_is_already_there():
    clock, ollama = FakeClock(), LateOllama(refusals=0)
    assert wait_for_ollama(ollama, sleep=clock.sleep, clock=clock) and clock.now == 0


def test_friday_gives_up_and_starts_anyway():
    clock = FakeClock()
    assert not wait_for_ollama(LateOllama(refusals=10**6), patience=30,
                               sleep=clock.sleep, clock=clock)  # fmt: skip
    assert clock.now == 30.0


def test_the_tray_says_friday_is_starting():
    from test_desktop import make_window

    from friday.app.events import AssistantState

    w = make_window()
    if w.notifier.tray is None:
        return
    w.show_state(AssistantState.LOADING)
    assert w.notifier.tray.toolTip() == "Friday · démarrage…"
    w.notifier.set_game(True)  # le mode jeu passe avant
    assert "mode jeu" in w.notifier.tray.toolTip()
    w.notifier.set_game(False)
    w.show_state(AssistantState.IDLE)
    assert w.notifier.tray.toolTip() == "Friday"

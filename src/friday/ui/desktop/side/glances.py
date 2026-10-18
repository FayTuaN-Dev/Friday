"""Les cartes qui suivent Friday une fois chargée (SidePanels) : Trading (W3) et Aujourd'hui
(W4). Ce qui est local (carnet, journal, rappels) est relu toutes les 10 s sur place ; ce qui
passe par le réseau, dans un fil : cours et annonces toutes les minutes, agenda et mails
Google toutes les 5 minutes. Rien tant que la carte n'est pas affichée."""

from friday.ui.desktop.side.sampler import Sampler

LOCAL_EVERY, MARKETS_EVERY, GOOGLE_EVERY = 5, 30, 150  # en tours de 2 s


class GlanceMixin:
    trading = glance = None  # set_trading()
    agenda = day = None  # set_day()

    def set_trading(self, trading, glance: Sampler | None = None) -> None:
        """Friday chargée (ou rechargée) : la carte Trading suit ce trading-là (None : cachée)."""
        from friday.app.trading_glance import from_trading

        if self.glance is not None:
            self.glance.stop()
        self.trading, self.glance = trading, None
        reader = from_trading(trading) if trading is not None else None
        if reader is not None:
            self.glance = glance or Sampler(lambda: reader.read, "trading-glance")
            self.glance.read.connect(self.cards["trading"].show_glance)
        self.place(self.wide)

    def set_day(self, agenda, account, day: Sampler | None = None) -> None:
        """Les rappels (AgendaStore) et le compte Google de Friday chargée ; sans l'un ni
        l'autre, la carte Aujourd'hui reste cachée."""
        from friday.app.day_glance import DayGlance

        if self.day is not None:
            self.day.stop()
        self.agenda, self.day = agenda, None
        if account is not None and getattr(account, "configured", False):
            reader = DayGlance(account)
            self.day = day or Sampler(lambda: reader.read, "day-glance")
            self.day.read.connect(self.cards["day"].show_day)
        self._has_day = agenda is not None or self.day is not None
        self.place(self.wide)

    def _glance_tick(self, force: bool = False) -> None:
        local = force or self._ticks % LOCAL_EVERY == 0
        if self.glance is not None and self.wanted(("trading",)):
            if local:
                setups = getattr(getattr(self.trading, "alerts", None), "setups", None)
                self.cards["trading"].show_local(setups, getattr(self.trading, "journal", None))
            if force or self._ticks % MARKETS_EVERY == 0:
                self.glance.request()
        if getattr(self, "_has_day", False) and self.wanted(("day",)):
            if local and self.agenda is not None:
                self.cards["day"].show_reminders(self.agenda.pending())
            if self.day is not None and (force or self._ticks % GOOGLE_EVERY == 0):
                self.day.request()

    def _stop_glances(self) -> None:
        for sampler in (self.glance, self.day):
            if sampler is not None:
                sampler.stop()

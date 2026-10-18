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

    def _glance_tick(self, new: set[str], tick: int | None = None) -> None:
        """`new` : les cartes qui viennent d'apparaître (lues tout de suite) ; `tick` : le
        tour de minuterie (les relectures régulières ne se font que là)."""
        due = lambda every: tick is not None and tick % every == 0  # noqa: E731
        local = due(LOCAL_EVERY)
        if self.glance is not None and self.wanted(("trading",)):
            force = "trading" in new
            if local or force:
                setups = getattr(getattr(self.trading, "alerts", None), "setups", None)
                self.cards["trading"].show_local(setups, getattr(self.trading, "journal", None))
            if force or due(MARKETS_EVERY):
                self.glance.request()
        if getattr(self, "_has_day", False) and self.wanted(("day",)):
            force = "day" in new
            if (local or force) and self.agenda is not None:
                self.cards["day"].show_reminders(self.agenda.pending())
            if self.day is not None and (force or due(GOOGLE_EVERY)):
                self.day.request()

    def _stop_glances(self) -> None:
        for sampler in (self.glance, self.day):
            if sampler is not None:
                sampler.stop()

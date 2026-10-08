"""Cassure de l'ouverture de Londres : le range de la nuit (session asiatique, de minuit à 8 h,
heure de Londres) est cassé pendant les trois premières heures de Londres. Une seule entrée
par jour ; stop de l'autre côté du range (au moins N ATR) ; objectif en R. Dans le sens de la
tendance journalière."""

from zoneinfo import ZoneInfo

from friday.trading.strategies.base import Entry, State, Strategy

LONDON = ZoneInfo("Europe/London")
OPEN, WINDOW = 8, 3  # ouverture de Londres (heure locale), et durée de la fenêtre d'entrée


class LondonOpenStrategy(Strategy):
    name = "londres"
    label = "la cassure de l'ouverture de Londres"
    summary = ("cassure du range de la nuit (session asiatique) dans les 3 premières heures de "
               "Londres, dans le sens de la tendance journalière")  # fmt: skip

    def entry(self, state: State, i: int, day: int) -> Entry | None:
        bar = state.hourly[i]
        local = bar.time.astimezone(LONDON)
        if not OPEN <= local.hour < OPEN + WINDOW:
            return None
        midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
        night, morning = [], []
        for c in state.hourly[max(0, i - 24) : i]:  # la nuit et le début de matinée, avant i
            moment = c.time.astimezone(LONDON)
            if moment.date() != local.date() or moment < midnight:
                continue
            (night if moment.hour < OPEN else morning).append(c)
        if len(night) < 4:  # pas de vraie nuit (lundi matin, données manquantes)
            return None
        high, low = max(c.high for c in night), min(c.low for c in night)
        if any(c.close > high or c.close < low for c in morning):
            return None  # déjà cassé plus tôt ce matin : une seule entrée par jour
        close = state.closes[i]
        side = "achat" if close > high else "vente" if close < low else None
        if side is None or side not in self.sides(state, i, day):
            return None
        return self.by_risk(state, i, side, stop=low if side == "achat" else high)

"""Retour à la moyenne : un excès (clôture hors de la bande de Bollinger 20 / 2 et RSI au-delà
de 30 / 70) qui devrait se résorber. Contre le mouvement, donc sans filtre de tendance ;
objectif : la moyenne 20 du moment de l'entrée ; stop d'au moins N ATR."""

from friday.trading.strategies.base import Entry, State, Strategy

PERIOD, WIDTH = 20, 2.0  # bandes de Bollinger
LOW, HIGH = 30, 70  # RSI 14 (1 h)


class ReversionStrategy(Strategy):
    name = "retour"
    label = "le retour à la moyenne"
    summary = (f"clôture hors de la bande de Bollinger ({PERIOD}, {WIDTH:g}) avec un RSI sous "
               f"{LOW} ou au-dessus de {HIGH} : retour visé vers la moyenne")  # fmt: skip
    trend_filter = False

    def add_series(self, state: State) -> None:
        mean, band = [None] * len(state.closes), [None] * len(state.closes)
        for i in range(PERIOD - 1, len(state.closes)):
            window = state.closes[i - PERIOD + 1 : i + 1]
            m = sum(window) / PERIOD
            mean[i] = m
            band[i] = WIDTH * (sum((x - m) ** 2 for x in window) / PERIOD) ** 0.5
        state.extra["mean"], state.extra["band"] = mean, band

    def entry(self, state: State, i: int, day: int) -> Entry | None:
        mean, band, rsi = state.extra["mean"][i], state.extra["band"][i], state.rsi[i]
        if mean is None or rsi is None or not band:
            return None
        close = state.closes[i]
        if close < mean - band and rsi < LOW:
            return self.by_risk(state, i, "achat", target=mean)
        if close > mean + band and rsi > HIGH:
            return self.by_risk(state, i, "vente", target=mean)
        return None

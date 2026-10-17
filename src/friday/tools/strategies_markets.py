"""La comparaison sur plusieurs marchés à la fois (« compare Turtle sur tous les marchés »,
« compare les stratégies sur tous les marchés ») : ce que Friday dit et affiche. Le calcul
est dans trading/backtest/portfolio.py."""

from friday.trading.backtest.compare import FAILED, ICONS, Result
from friday.trading.backtest.portfolio import by_strategy, portfolio
from friday.trading.backtest.report import _n, r_text
from friday.trading.plan_book import PREFIX
from friday.trading.strategies import BY_NAME, strategy_named
from friday.voice.wake import normalize

SHOWN = 3  # marchés cités à l'oral, en tête et en queue


def asked_strategy(choice, strategy: str, request: str) -> str | None:
    """Le nom de la stratégie demandée : un plan écrit nommé (même par son premier mot,
    « Turtle » pour « Turtle Traders »), sinon une stratégie de la bibliothèque ; ou None."""
    plan = choice.book.find(request) if request else None
    if plan is None and request:
        padded = f" {normalize(request)} "
        plan = next((p for p in choice.book.plans() if p["spec"] and len(first := normalize(
            p["nom"]).split(" ")[0]) >= 4 and f" {first} " in padded), None)  # fmt: skip
    if plan is not None and plan["spec"]:
        return PREFIX + plan["id"]
    name = strategy_named(strategy) if strategy else None
    if name == "mon_plan":
        first = choice.first_plan()
        return first.name if first else None
    return name if name in BY_NAME else None


def _verdict(r: Result) -> str:
    return r.verdict + (f" ({r.why()})" if r.why() else "")


def _figures(r: Result) -> str:
    rep = r.report
    return (
        f"{rep.count} trades, {_n(rep.win_rate, 0)} % gagnants, {r_text(rep.expectancy)} "
        f"par trade, total {r_text(rep.total)}, plus forte baisse {_n(rep.drawdown, 1)} R"
    )


def _names(pairs) -> str:
    return ", ".join(f"{m.name} ({r_text(r.report.total)})" for m, r in pairs)


def one_strategy(name: str, markets: list[tuple]) -> tuple[str, list[dict]]:
    """(phrase, lignes affichées) : une stratégie sur chaque marché et en portefeuille."""
    pairs = by_strategy(markets).get(name, [])
    if not pairs:
        return "Cette stratégie n'a pas pu être testée.", []
    whole = portfolio(pairs[0][1].strategy, [r for _, r in pairs])
    traded = sorted((p for p in pairs if p[1].report.count),
                    key=lambda p: -p[1].report.total)  # fmt: skip
    since = min((r.since for _, r in pairs if r.since), default=None)
    daily = f", en journalier depuis {since:%Y}" if since and whole.strategy.unit == "jour" else ""
    spoken = (
        f"{whole.strategy.label} sur {len(pairs)} marchés en même temps{daily} : "
        f"{_figures(whole)} ; verdict : {_verdict(whole)}"
    )
    if traded:
        spoken += f". Le mieux : {_names(traded[:SHOWN])}"
        worst = [p for p in traded[-SHOWN:] if p not in traded[:SHOWN]][::-1]
        if worst:
            spoken += f" ; le moins bien : {_names(worst)}"
    if idle := [m.name for m, r in pairs if not r.report.count]:
        spoken += f" ; aucun trade sur {', '.join(idle)}"
    items = [
        {
            "text": f"{ICONS[whole.verdict]} Tous les marchés · {whole.strategy.label}",
            "meta": whole.report.summary() + (f" — {whole.why()}" if whole.why() else ""),
        }
    ]
    items += [{"text": f"{ICONS[r.verdict]} {m.name}", "meta": r.report.summary()}
              for m, r in sorted(pairs, key=lambda p: -p[1].report.total)]  # fmt: skip
    return spoken + ".", items


def all_strategies(markets: list[tuple]) -> tuple[str, list[dict]]:
    """(phrase, lignes affichées) : chaque stratégie en portefeuille sur tous les marchés,
    puis la meilleure de chaque marché (affichée, avec une mise en garde)."""
    order = {"a fonctionné": 0, "prometteuse": 1, FAILED: 2}
    wholes = sorted((portfolio(pairs[0][1].strategy, [r for _, r in pairs])
                     for pairs in by_strategy(markets).values()),
                    key=lambda w: (order[w.verdict], -(w.report.expectancy or -99)))  # fmt: skip
    kept = [w for w in wholes if w.verdict != FAILED]
    spoken = f"Sur {len(markets)} marchés en même temps : " + (" ; ".join(
        f"{w.strategy.label} {_verdict(w)}, {r_text(w.report.expectancy)} par trade sur "
        f"{w.report.count} trades" for w in kept) or "aucune stratégie n'a gagné")  # fmt: skip
    if failed := [w.strategy.label for w in wholes if w.verdict == FAILED]:
        spoken += f" ; n'ont pas fonctionné : {', '.join(failed)}"
    spoken += (
        ". La meilleure de chaque marché est affichée, mais attention : la choisir "
        "après coup, c'est souvent choisir celle qui a eu de la chance ; une stratégie "
        "qui marche sur l'ensemble des marchés est plus sûre."
    )
    items = [{"text": f"{ICONS[w.verdict]} Tous les marchés · {w.strategy.label}",
              "meta": w.report.summary() + (f" — {w.why()}" if w.why() else "")}
             for w in wholes]  # fmt: skip
    for market, results in markets:
        best = results[0]
        label = best.strategy.label if best.verdict != FAILED else "aucune n'a fonctionné"
        items.append({"text": f"{ICONS[best.verdict]} {market.name} · le mieux : {label}",
                      "meta": best.report.summary()})  # fmt: skip
    return spoken, items

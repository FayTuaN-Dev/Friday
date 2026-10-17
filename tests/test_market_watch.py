"""La surveillance de plusieurs marchés (P2) : « surveille tous les marchés avec Turtle »,
le carnet des setups, et les setups journaliers vus à toute heure mais annoncés pendant les
heures de trading (Friday éteint le week-end ne rate pas celui du samedi)."""

from datetime import UTC, datetime, timedelta

from test_daily_plans import days, turtle

from friday.tools.market_watch import RecentSetupsTool, WatchMarketsTool
from friday.trading.alerts.setup_log import SetupLog
from friday.trading.alerts.store import AlertStore
from friday.trading.alerts.watcher import AlertWatcher
from friday.trading.mode import strategy_request
from friday.trading.plan_book import PlanBook
from friday.trading.strategy_choice import StrategyChoice

SATURDAY = datetime(2020, 2, 8, tzinfo=UTC)  # la journée du setup (cassure des 20 jours)


class Clock:
    def __init__(self, moment):
        self.moment = moment

    def __call__(self):
        return self.moment


def setting(tmp_path, families=("matieres", "crypto")):
    book = PlanBook(tmp_path / "plans.json")
    plan = book.add("Turtle Traders", "Cassure des 20 jours")
    book.save_translation(plan["id"], turtle(), "Cassure des 20 jours")
    book.set_families(plan["id"], list(families))
    choice = StrategyChoice(tmp_path / "choice.json", book)
    clock = Clock(SATURDAY + timedelta(days=1, hours=3))  # dimanche 3 h : hors des heures
    watcher = AlertWatcher(AlertStore(tmp_path / "alerts.json"), tmp_path / "rules.json",
                           days=lambda i: days([100.0] * 33 + [101.0]), now=clock,
                           setups=SetupLog(tmp_path / "setups.json"))  # fmt: skip
    watcher.choice = choice
    said = []
    watcher.on_alert = said.append
    return watcher, choice, clock, said


def test_watching_all_markets_follows_the_plan_families_and_stops_cleanly(tmp_path):
    watcher, choice, _, _ = setting(tmp_path)
    watcher.store.add_level("EURUSD", 1.2, above=True)
    text = WatchMarketsTool(watcher, choice).run(request="surveille tous les marchés avec Turtle")
    watched = sorted(a.symbol for a in watcher.store.all() if a.kind == "setup")
    assert watched == ["BTCUSD", "ETHUSD", "UKOIL", "USOIL", "XAGUSD", "XAUUSD"]
    assert choice.get("XAUUSD").label == "ton plan « Turtle Traders »"
    assert "Je surveille 6 marchés (matières premières, crypto)" in text.text
    assert "à la clôture de chaque journée" in text.text
    stopped = WatchMarketsTool(watcher, choice).run(stop=True).text
    assert "Surveillance arrêtée sur 6 marché(s)" in stopped
    assert [a.kind for a in watcher.store.all()] == ["niveau"]  # l'alerte de prix reste


def test_a_weekend_setup_is_noted_at_night_and_announced_once_on_monday(tmp_path):
    watcher, choice, clock, said = setting(tmp_path)
    WatchMarketsTool(watcher, choice).run(request="surveille tous les marchés avec Turtle")
    watcher.check()  # dimanche 3 h : vu et noté, pas annoncé
    noted = watcher.setups.all()
    assert len(noted) == 6 and not said
    assert noted[0]["bar"] == SATURDAY.isoformat() and noted[0]["unit"] == "jour"
    clock.moment = datetime(2020, 2, 10, 8, 5, tzinfo=UTC)  # lundi 9 h 05 à Paris
    watcher.check()
    watcher.check()
    assert len(said) == 1 and said[0].startswith("6 setups depuis ma dernière annonce.")
    assert "journée du 08/02 fermée à 101,0" in said[0]
    assert len(watcher.setups.all()) == 6  # pas noté deux fois
    shown = RecentSetupsTool(watcher).run()
    assert "Derniers setups : achat sur" in shown.text and "(journée du 08/02)" in shown.text


def test_the_setup_log_survives_a_restart_and_forgets_stale_setups(tmp_path):
    watcher, choice, clock, said = setting(tmp_path)
    WatchMarketsTool(watcher, choice).run(request="surveille tous les marchés avec Turtle")
    watcher.check()
    again = SetupLog(tmp_path / "setups.json")
    assert len(again.all()) == 6 and len(again.waiting(clock.moment)) == 6
    assert again.waiting(clock.moment + timedelta(days=4)) == []  # trop vieux pour l'annoncer


def test_watch_requests_are_routed_by_code():
    assert strategy_request("surveille tous les marchés avec Turtle") == (
        "watch_markets",
        {"strategy": "", "stop": False},
    )
    assert strategy_request("arrête de surveiller les marchés")[1]["stop"] is True
    assert strategy_request("surveille l'or") is None  # un seul marché : watch_setup

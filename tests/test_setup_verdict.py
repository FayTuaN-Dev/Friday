"""L'avis de Claude sur chaque setup (P3), ce que chaque setup aurait donné, et le bilan qui
dira si l'avis de Claude aide vraiment. Activé seulement par l'utilisateur (Réglages)."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from test_daily_plans import days
from test_market_watch import SATURDAY, setting

from friday.tools.market_watch import WatchMarketsTool
from friday.tools.setup_review import SetupReviewTool
from friday.trading.alerts.outcome import follow
from friday.trading.alerts.setup_log import PENDING, SetupLog
from friday.trading.mode import strategy_request
from friday.trading.setup_verdict import SetupJudge, parse_verdict

MONDAY = datetime(2020, 2, 10, 8, 5, tzinfo=UTC)  # 9 h 05 à Paris


def test_the_answer_is_read_as_yes_or_no():
    assert parse_verdict('{"avis": "NON", "raison": "Fed dans 1 h."}') == ("non", "Fed dans 1 h.")
    assert parse_verdict('```json\n{"avis": "oui", "raison": "ok"}\n```') == ("oui", "ok")
    assert parse_verdict("OUI : la tendance est nette.") == ("oui", "la tendance est nette.")
    assert parse_verdict("Je ne sais pas.") is None


class FakeJob:
    def __init__(self, answer):
        self.answer, self.sent = answer, []

    def run(self, content):
        self.sent.append(content)
        return {"ok": True, "result": self.answer}


class FakeBuilder:
    def build(self, question, instrument=None):
        return SimpleNamespace(
            question=question,
            instrument=instrument.symbol,
            price=None,
            render=lambda: f"Question de l'utilisateur : {question}",
        )


class FakeJournal:
    def __init__(self):
        self.sent, self.answers = [], []

    def log_sent(self, question, content, images, instrument, price):
        self.sent.append(question)
        return len(self.sent)

    def log_answer(self, sent_id, answer):
        self.answers.append(answer)


def judge(answer='{"avis": "non", "raison": "Annonce de la Fed dans une heure."}', per_day=10):
    return SetupJudge(FakeBuilder(), FakeJob(answer), FakeJournal(), per_day)


def test_claude_is_asked_about_each_new_setup_and_his_verdict_is_announced(tmp_path):
    watcher, choice, clock, said = setting(tmp_path)
    watcher.notebook.judge = judge()
    WatchMarketsTool(watcher, choice).run(request="surveille tous les marchés avec Turtle")
    watcher.check()  # dimanche : vus, avis demandés
    assert all(e["avis"] == PENDING for e in watcher.setups.all())
    queue = watcher.notebook._queue
    while not queue.empty():
        watcher.notebook.judge_one(*queue.get())
    sent = watcher.notebook.judge.job.sent
    assert len(sent) == 6 and "Setup détecté par la surveillance de Friday" in sent[0]
    assert len(watcher.notebook.judge.journal.sent) == 6  # noté au journal des envois
    clock.moment = MONDAY
    watcher.check()
    assert "Avis de Claude : NON. Annonce de la Fed dans une heure." in said[0]


def test_the_daily_limit_spares_claude_and_a_late_verdict_does_not_block(tmp_path):
    watcher, choice, clock, said = setting(tmp_path)
    watcher.notebook.judge = judge(per_day=2)
    WatchMarketsTool(watcher, choice).run(request="surveille tous les marchés avec Turtle")
    watcher.check()
    avis = [e["avis"] for e in watcher.setups.all()]
    assert avis.count(PENDING) == 2 and avis.count(None) == 4  # 2 avis par jour au plus
    log = SetupLog(None)
    seen = MONDAY
    entry = log.add("XAUUSD", SimpleNamespace(side="achat", bar=SimpleNamespace(
        time=SATURDAY, close=101.0), stop=99.0, target=None, trail=10, strategy=None), "Setup.",
        seen)  # fmt: skip
    log.update(entry["id"], avis=PENDING)
    assert log.waiting(seen + timedelta(minutes=5)) == []  # on attend son avis…
    assert len(log.waiting(seen + timedelta(minutes=16))) == 1  # … mais pas indéfiniment


def test_each_setup_is_followed_to_its_exit_and_the_review_compares_yes_and_no(tmp_path):
    rising = days(
        [100.0] * 33 + [101.0] + [101 + i for i in range(1, 15)] + [114 - 3 * i for i in range(8)]
    )
    entry = {"bar": SATURDAY.isoformat(), "side": "achat", "close": 101.0, "stop": 99.0,
             "target": None, "trail": 5}  # fmt: skip
    closed, result = follow(entry, rising, 0.0)
    assert result > 3 and datetime.fromisoformat(closed) > SATURDAY + timedelta(days=14)
    assert follow(entry, rising[:36], 0.0) is None  # encore en cours
    watcher, choice, clock, said = setting(tmp_path)
    watcher.notebook.judge = judge()
    watcher.days = lambda i: rising
    WatchMarketsTool(watcher, choice).run(request="surveille tous les marchés avec Turtle")
    clock.moment = SATURDAY + timedelta(days=1, hours=3)
    watcher.days = lambda i: days([100.0] * 33 + [101.0])
    watcher.check()
    for k, item in enumerate(watcher.setups.all()):
        watcher.setups.update(item["id"], avis="oui" if k % 2 else "non")
    clock.moment = SATURDAY + timedelta(days=30)
    watcher.days = lambda i: rising
    watcher._read.clear()
    watcher.check()
    assert all(e["result_r"] is not None for e in watcher.setups.all())
    text = SetupReviewTool(watcher).run().text
    assert "Sur 6 setups terminés" in text and "quand Claude dit oui" in text
    assert "trop tôt pour conclure" in text
    assert strategy_request("bilan des setups") == ("setup_review", {})
    assert strategy_request("mes derniers setups") == ("recent_setups", {})

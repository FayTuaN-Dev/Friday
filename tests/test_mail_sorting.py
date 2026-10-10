from types import SimpleNamespace

from friday.google.gmail import Mail
from friday.google.mailbox import Mailbox
from friday.google.sorter import CATEGORIES, Classifier, MailSorter, find_category
from friday.tools.mail_sorting import CategoryMailsTool, SortMailsTool
from friday.tools.mail_trash import TrashMailsTool


class FakeMailbox(Mailbox):
    """Boîte en mémoire : on teste la logique, pas l'API Google."""

    def __init__(self, mails: dict[str, set[str]], labels: dict[str, str] | None = None):
        super().__init__(lambda: None)
        self.mails = mails  # id → étiquettes
        self._labels = dict(labels or {})
        self.trashed: list[str] = []

    def ids(self, query="", label_id=None, limit=500):
        found = [i for i, labels in self.mails.items()
                 if (label_id is None or label_id in labels) and i not in self.trashed
                 and ("rollercoin" in i if "rollercoin" in query else True)]  # fmt: skip
        return found[:limit]

    def metadata(self, ids):
        return [Mail(i, "", f"Expéditeur {i} <x@y.fr>", f"Sujet {i}", "", "",
                     labels=frozenset(self.mails[i])) for i in ids]  # fmt: skip

    def ensure_label(self, category):
        return self._labels.setdefault("Friday/" + category, f"L-{category}")

    def add_label(self, ids, label_id):
        for i in ids:
            self.mails[i].add(label_id)

    def trash(self, ids):
        self.trashed += ids
        return len(ids)


LABELS = {"Friday/Banque & finances": "L-B", "Friday/Promotions & newsletters": "L-P"}


def classify_by_name(mails, extra=()):
    return ["Banque & finances" if "banque" in m.id else "Promotions & newsletters" for m in mails]


def test_find_category():
    known = ["Banque & finances", "Promotions & newsletters", "Jeux & loisirs"]
    assert find_category("banque", known) == "Banque & finances"
    assert find_category("les promotions", known) == "Promotions & newsletters"
    assert find_category("banques", known) == "Banque & finances"  # pluriel
    assert find_category("promotions", known) == "Promotions & newsletters"
    assert find_category("Friday/Jeux & loisirs", known) == "Jeux & loisirs"
    assert find_category("voyages", known) is None


def test_sort_labels_mails_and_skips_already_sorted():
    box = FakeMailbox({"banque1": {"INBOX"}, "promo1": {"INBOX"}, "promo2": {"INBOX"}})
    tool = SortMailsTool(MailSorter(box, classify_by_name))
    result = tool.run(50)
    assert "3 mails triés" in result.text and "Promotions & newsletters : 2" in result.text
    assert "L-Banque & finances" in box.mails["banque1"]
    assert "déjà rangés" in tool.run(50).text  # rien de nouveau à trier


def test_category_mails_and_listing():
    box = FakeMailbox({"banque1": {"L-B"}, "promo1": {"L-P"}}, LABELS)
    tool = CategoryMailsTool(box)
    assert "Expéditeur banque1" in tool.run("banque").text
    assert "« Tes catégories de mails : Banque & finances et Promotions & newsletters. »" in (
        tool.run("").text)  # fmt: skip
    assert "Je n'ai pas de catégorie « voyages »" in tool.run("voyages").text
    assert "pas encore été triés" in CategoryMailsTool(FakeMailbox({})).run("banque").text


def test_trash_a_category_only_after_confirmation():
    box = FakeMailbox({"promo1": {"L-P"}, "promo2": {"L-P"}, "banque1": {"L-B"}}, LABELS)
    tool = TrashMailsTool(box)
    assert tool.needs_confirmation
    question = tool.confirmation({"categories": "promotions"})
    assert "Je mets 2 mail(s) des catégories « Promotions & newsletters »" in question
    assert "corbeille" in tool.run(categories="promotions").text
    assert box.trashed == ["promo1", "promo2"]  # la banque n'est pas touchée


def test_trash_never_happens_without_matching_confirmation():
    box = FakeMailbox({"rollercoin1": {"INBOX"}, "rollercoin2": {"INBOX"}, "autre": {"INBOX"}})
    tool = TrashMailsTool(box)
    assert "« from:rollercoin »" in tool.confirmation({"query": "from:rollercoin"})
    assert "pas été confirmée" in tool.run(query="from:autre chose").text  # pas la même demande
    assert box.trashed == []
    assert tool.confirmation({"categories": "inconnue"}) is None  # pas de question inutile
    assert "inconnue" in tool.run(categories="inconnue").text
    assert "il faut" in tool.run().text
    assert box.trashed == []


def test_classifier_keeps_order_and_fills_gaps():
    replies = iter(['{"categories": ["Factures & abonnements", "Inventée"]}', "pas du json"])

    class Client:
        def chat(self, **kwargs):
            assert kwargs["format"]["properties"]["categories"]["items"]["enum"] == list(CATEGORIES)
            return SimpleNamespace(message=SimpleNamespace(content=next(replies)))

    mails = [Mail(str(i), "", "a", "s", "", "") for i in range(3)]
    classify = Classifier(Client(), "qwen3:8b", 8192)
    assert classify(mails) == ["Factures & abonnements", "Autres", "Autres"]
    assert classify(mails) == ["Autres"] * 3


def test_user_labels_become_categories():
    seen = []

    def classify(mails, extra=()):
        seen.append(extra)
        return ["Mes impôts"] * len(mails)

    box = FakeMailbox({"m1": {"INBOX"}}, {"Friday/Mes impôts": "L-I", "Friday/Jeux": "L-J"})
    MailSorter(box, classify).sort_inbox(10)
    assert seen == [("Mes impôts",)] and "L-I" in box.mails["m1"]


def test_trash_all_categories_except_some():
    labels = {
        "Friday/Jeux": "L-J",
        "Friday/Administratif": "L-A",
        "Friday/Factures & abonnements": "L-F",
    }
    box = FakeMailbox({"jeu1": {"L-J"}, "jeu2": {"L-J"}, "impots": {"L-A"}, "edf": {"L-F"}}, labels)
    tool = TrashMailsTool(box)
    question = tool.confirmation({"except_categories": "administratif, factures"})
    assert "Je mets 2 mail(s) des catégories « Jeux »" in question
    tool.run(except_categories="administratif, factures")
    assert box.trashed == ["jeu1", "jeu2"]


def test_invented_category_syntax_is_refused():
    box = FakeMailbox({"jeu1": {"L-J"}}, {"Friday/Jeux": "L-J"})
    tool = TrashMailsTool(box)
    args = {"query": "category:Jeux OR category:Trading & crypto"}
    assert tool.confirmation(args) is None
    assert "utilise categories" in tool.run(**args).text and box.trashed == []


def test_sorting_everything_runs_in_background():
    import threading

    done = threading.Event()
    announced = []

    def on_background(task, result):
        announced.append(result.text)
        done.set()

    box = FakeMailbox({f"promo{i}": {"INBOX"} for i in range(3)})
    tool = SortMailsTool(MailSorter(box, classify_by_name), on_background)
    assert "arrière-plan" in tool.run(0).text  # 0 = tous
    assert done.wait(5) and "3 mails triés" in announced[0]


def test_refused_requests_are_retried_not_lost(monkeypatch):
    import friday.google.mailbox as mailbox_module

    monkeypatch.setattr(mailbox_module, "PAUSE", 0)
    monkeypatch.setattr(mailbox_module.time, "sleep", lambda seconds: None)
    refused_once = {"b", "d"}

    class Batch:
        def __init__(self, callback):
            self.callback, self.items = callback, []

        def add(self, request, request_id):
            self.items.append(request_id)

        def execute(self):
            for item in self.items:
                if item in refused_once:
                    refused_once.discard(item)
                    self.callback(item, None, Exception("429 rateLimitExceeded"))
                else:
                    self.callback(item, {"id": item}, None)

    service = SimpleNamespace(new_batch_http_request=lambda callback: Batch(callback))
    found = mailbox_module.run_batched(service, list("abcde"), lambda item: item)
    assert sorted(found) == list("abcde")  # b et d récupérés au 2e passage


def test_the_real_category_list_is_given_and_asked_by_the_code():
    from friday.app.prefetch import prefetcher
    from friday.tools.mail_sorting import asks_categories, categories_context

    box = FakeMailbox({}, LABELS)
    assert categories_context(box) == ("Catégories de mails existantes (tri de Friday) : "
                                       "Banque & finances et Promotions & newsletters. N'en "
                                       "cite aucune autre.")  # fmt: skip
    assert "aucune pour l'instant" in categories_context(FakeMailbox({}))

    class Offline:
        def category_labels(self):
            raise ConnectionError("Gmail pas connecté")

    assert categories_context(Offline()) == ""
    for text in ("Quelles catégories ai-je ?", "donne-moi la liste des catégories",
                 "c'est quoi mes catégories de mails"):  # fmt: skip
        assert asks_categories(text), text
    assert not asks_categories("trie mes mails")
    prefetch = prefetcher(None, None, None, mail=True)
    assert prefetch("quelles catégories ai-je ?") == ("category_mails", {})
    assert prefetcher(None, None, None)("quelles catégories ai-je ?") is None  # sans Gmail

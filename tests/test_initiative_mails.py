from datetime import datetime, timedelta

from friday.app.initiative_watch import InitiativeWatch
from friday.google.gmail import Mail
from friday.initiative.guard import Guard
from friday.initiative.mails import ImportantMails, entries, from_sender, important, mail_text

NOW = datetime(2026, 10, 21, 15, 30)


def mail(id="m1", sender="Marie Dupont <marie@exemple.fr>", subject="Bonjour") -> Mail:
    return Mail(id, "t", sender, subject, "21/10 15:20", "", labels=frozenset({"UNREAD"}))


class FakeGmail:
    def __init__(self, mails, fail=False):
        self.mails, self.fail = {m.id: m for m in mails}, fail
        self.queries, self.headers = [], []

    def ids(self, query, limit=20):
        if self.fail:
            raise RuntimeError("déconnecté")
        self.queries.append(query)
        return list(self.mails)

    def header(self, mail_id):
        self.headers.append(mail_id)
        return self.mails[mail_id]


def watch(tmp_path, gmail, senders="", words=""):
    said = []
    source = ImportantMails(gmail, entries(senders), entries(words))
    w = InitiativeWatch(Guard(tmp_path / "vu.json", quiet=(0, 0)),
                        lambda task, result: said.append(result.text), [source])  # fmt: skip
    return w, said


def test_lists_are_read_from_the_settings_text():
    assert entries(" marie@exemple.fr, @impots.gouv.fr ;Banque Populaire,, ") == (
        "marie@exemple.fr", "@impots.gouv.fr", "Banque Populaire")  # fmt: skip
    assert entries("") == ()


def test_a_sender_is_an_address_a_domain_or_a_name():
    m = mail(sender="Impôts <noreply@dgfip.impots.gouv.fr>")
    assert from_sender(m, ("@impots.gouv.fr",))
    assert from_sender(m, ("impots",))  # le nom, sans accent
    assert not from_sender(m, ("@gouv.com",))
    assert from_sender(mail(), ("Marie@Exemple.fr",))
    assert not from_sender(mail(), ("marie@exemple.com",))
    assert from_sender(mail(), ("marie dupont",))
    assert not from_sender(mail(), ("mari",))  # mots entiers seulement


def test_a_word_of_the_subject_makes_a_mail_important():
    assert important(mail(subject="Votre CONVOCATION médicale"), (), ("convocation",))
    assert important(mail(subject="Dépôt de colis"), (), ("depot",))
    assert not important(mail(subject="Dépôts en ligne"), (), ("depot",))


def test_sentences_for_one_or_several_mails():
    assert mail_text([mail(subject="Rendez-vous « lundi »")]) == (
        "Dis EXACTEMENT : « Mail important de Marie Dupont : Rendez-vous lundi. »")  # fmt: skip
    two = mail_text([mail(), mail("m2", "Banque <b@banque.fr>", "Relevé")])
    assert two == ("Dis EXACTEMENT : « 2 mails importants : de Marie Dupont (Bonjour) et de "
                   "Banque (Relevé). »")  # fmt: skip


def test_an_important_mail_is_announced_once(tmp_path):
    gmail = FakeGmail([mail(), mail("m2", "Pub <pub@promo.fr>", "Soldes")])
    w, said = watch(tmp_path, gmail, senders="marie@exemple.fr")
    assert w.check(NOW) == 1
    assert said == ["Dis EXACTEMENT : « Mail important de Marie Dupont : Bonjour. »"]
    assert "is:unread" in gmail.queries[0] and "after:" in gmail.queries[0]
    assert w.check(NOW + timedelta(minutes=5)) == 0
    assert gmail.headers == ["m1", "m2"]  # chaque mail n'est lu qu'une fois


def test_gmail_is_asked_every_two_minutes_only(tmp_path):
    gmail = FakeGmail([])
    w, _ = watch(tmp_path, gmail, words="urgent")
    for minute in range(5):
        w.check(NOW + timedelta(minutes=minute))
    assert len(gmail.queries) == 3


def test_empty_lists_watch_nothing(tmp_path):
    gmail = FakeGmail([mail()])
    w, said = watch(tmp_path, gmail)
    assert w.check(NOW) == 0 and gmail.queries == []


def test_a_new_important_mail_after_the_first_one(tmp_path):
    gmail = FakeGmail([mail()])
    w, said = watch(tmp_path, gmail, senders="marie dupont")
    w.check(NOW)
    gmail.mails["m3"] = mail("m3", subject="Encore moi")
    assert w.check(NOW + timedelta(minutes=3)) == 1
    assert said[-1] == "Dis EXACTEMENT : « Mail important de Marie Dupont : Encore moi. »"


def test_gmail_unreachable_says_nothing(tmp_path):
    w, said = watch(tmp_path, FakeGmail([], fail=True), senders="marie@exemple.fr")
    assert w.check(NOW) == 0 and said == []

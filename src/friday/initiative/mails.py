"""La source « mails importants » (I2) : un mail non lu d'un expéditeur de la liste de
l'utilisateur, ou avec un de ses mots dans l'objet, est annoncé en une phrase. Les listes se
remplissent dans Réglages → Initiative ; vides, rien n'est surveillé."""

import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from email.utils import parseaddr

from friday.google.gmail import Gmail, Mail
from friday.initiative.source import Candidate
from friday.voice.wake import normalize

log = logging.getLogger(__name__)

CHECK_EVERY = timedelta(minutes=2)
WITHIN = timedelta(hours=2)  # plus ancien : le résumé du matin ou « mes mails ? » s'en chargent
MAX_SUBJECT = 70


def entries(text: str) -> tuple[str, ...]:
    """« marie@exemple.fr, @impots.gouv.fr ; Banque » → les trois, sans les vides."""
    return tuple(e.strip() for e in text.replace(";", ",").split(",") if e.strip())


def _has_words(wanted: str, text: str) -> bool:
    """Mots entiers, sans accents ni majuscules : « impots » trouve « Impôts », pas « dépôts »."""
    plain = normalize(wanted)
    return bool(plain) and f" {plain} " in f" {normalize(text)} "


def from_sender(mail: Mail, senders: tuple[str, ...]) -> bool:
    name, address = parseaddr(mail.sender)
    address = address.lower()
    for sender in senders:
        wanted = sender.lower()
        if wanted.startswith("@"):  # un domaine, sous-domaines compris (@dgfip.impots.gouv.fr)
            domain = address.rpartition("@")[2]
            if domain == wanted[1:] or domain.endswith("." + wanted[1:]):
                return True
        elif "@" in wanted:  # une adresse
            if address == wanted:
                return True
        elif _has_words(sender, f"{name} {address}"):  # un nom
            return True
    return False


def important(mail: Mail, senders: tuple[str, ...], words: tuple[str, ...]) -> bool:
    return from_sender(mail, senders) or any(_has_words(w, mail.subject) for w in words)


def _subject(mail: Mail) -> str:
    subject = " ".join(mail.subject.replace("«", "").replace("»", "").split()) or "sans objet"
    if len(subject) > MAX_SUBJECT:
        subject = subject[: MAX_SUBJECT - 1].rsplit(" ", 1)[0] + "…"
    return subject


def mail_text(mails: list[Mail]) -> str:
    if len(mails) == 1:
        said = f"Mail important de {mails[0].sender_name} : {_subject(mails[0])}."
    else:
        each = [f"de {m.sender_name} ({_subject(m)})" for m in mails]
        said = f"{len(mails)} mails importants : {', '.join(each[:-1])} et {each[-1]}."
    return f"Dis EXACTEMENT : « {said} »"


class ImportantMails:
    def __init__(self, gmail: Gmail, senders: tuple[str, ...], words: tuple[str, ...]) -> None:
        self.gmail, self.senders, self.words = gmail, senders, words
        self._headers: dict[str, Mail] = {}  # déjà lus : un mail n'est demandé qu'une fois
        self._checked_at: datetime | None = None

    def candidates(self, now: datetime, said: Callable[[str], bool]) -> list[Candidate]:
        if not (self.senders or self.words):
            return []
        if self._checked_at is not None and now - self._checked_at < CHECK_EVERY:
            return []
        self._checked_at = now
        query = f"in:inbox is:unread after:{int((now - WITHIN).timestamp())}"
        try:
            ids = self.gmail.ids(query)
            for mail_id in ids:
                if mail_id not in self._headers:
                    self._headers[mail_id] = self.gmail.header(mail_id)
        except Exception as error:  # compte déconnecté, réseau…
            log.info("Initiatives : mails illisibles (%s)", error)
            return []
        self._headers = {i: m for i, m in self._headers.items() if i in ids}  # lus : oubliés
        found = [m for i, m in self._headers.items()
                 if not said(f"mail:{i}") and important(m, self.senders, self.words)]  # fmt: skip
        if not found:
            return []
        return [Candidate(tuple(f"mail:{m.id}" for m in found), mail_text(found))]

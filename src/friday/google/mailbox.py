"""Actions sur la boîte Gmail : étiquettes de tri (« Friday/… ») et corbeille.

La corbeille garde les mails 30 jours : rien n'est jamais effacé définitivement (les
autorisations demandées ne le permettent même pas).
"""

import logging
import time
from collections.abc import Callable

from friday.google.gmail import Mail, parse_mail

log = logging.getLogger(__name__)

PREFIX = "Friday/"  # toutes les étiquettes de tri de Friday sont rangées sous « Friday »
BATCH = 20  # requêtes par lot : Gmail freine au-delà d'environ 50 lectures par seconde
PAUSE = 1.0  # secondes entre deux lots (au-delà de ~20 lectures par seconde, Gmail freine)
RETRIES = 5
MAX_IDS = 500  # au-delà, une seule demande en ferait trop d'un coup


def with_retries(call: Callable[[], object]):
    """Réessaie un appel freiné par Gmail (429, 5xx) ou coupé par le réseau."""
    from googleapiclient.errors import HttpError

    for attempt in range(RETRIES):
        try:
            return call()
        except (HttpError, OSError) as error:
            status = getattr(getattr(error, "resp", None), "status", None)
            if isinstance(error, HttpError) and status not in (403, 429, 500, 503):
                raise
            if attempt == RETRIES - 1:
                raise
            log.info("Gmail freine ou réseau coupé (%s) : nouvel essai", status or error)
            time.sleep(2**attempt)
    return None


def run_batched(service, ids: list[str], make_request) -> dict[str, dict]:
    """Exécute une requête par identifiant, par lots, en réessayant les refus de Gmail (au
    lieu de les perdre en silence) ; renvoie les réponses obtenues."""
    results: dict[str, dict] = {}
    pending = list(ids)
    for attempt in range(RETRIES):
        failed: list[str] = []

        def store(request_id, response, exception, failed=failed):
            if exception is None:
                results[request_id] = response
            else:
                failed.append(request_id)

        for start in range(0, len(pending), BATCH):
            batch = service.new_batch_http_request(callback=store)
            for item in pending[start : start + BATCH]:
                batch.add(make_request(item), request_id=item)
            with_retries(batch.execute)
            time.sleep(PAUSE)
        if not failed:
            break
        log.info("%d requête(s) refusée(s) par Gmail : nouvel essai", len(failed))
        pending = failed
        time.sleep(2 ** (attempt + 1))
    return results


class Mailbox:
    def __init__(self, service: Callable[[], object]) -> None:
        self._service = service
        self._labels: dict[str, str] | None = None  # nom → id

    def _users(self):
        return self._service().users()

    # --- Recherche ---

    def ids(self, query: str = "", label_id: str | None = None, limit: int = MAX_IDS) -> list[str]:
        """Identifiants des mails correspondants, du plus récent, sur plusieurs pages."""
        found, page = [], None
        while len(found) < limit:
            kwargs = {"userId": "me", "q": query, "maxResults": min(500, limit - len(found))}
            if label_id:
                kwargs["labelIds"] = [label_id]
            if page:
                kwargs["pageToken"] = page
            response = self._users().messages().list(**kwargs).execute()
            found += [m["id"] for m in response.get("messages", [])]
            page = response.get("nextPageToken")
            if not page:
                break
        return found[:limit]

    def metadata(self, ids: list[str]) -> list[Mail]:
        """En-têtes de nombreux mails, par requêtes groupées (rapide)."""
        service = self._service()
        found = run_batched(service, ids, lambda mail_id: service.users().messages().get(
            userId="me", id=mail_id, format="metadata",
            metadataHeaders=["From", "Subject", "Date", "Message-ID"],
        ))  # fmt: skip
        return [parse_mail(found[i]) for i in ids if i in found]

    # --- Étiquettes de tri ---

    def labels(self) -> dict[str, str]:
        if self._labels is None:
            response = self._users().labels().list(userId="me").execute()
            self._labels = {label["name"]: label["id"] for label in response.get("labels", [])}
        return self._labels

    def category_labels(self) -> dict[str, str]:
        """Catégories créées par Friday : « Banque » → id de l'étiquette « Friday/Banque »."""
        return {n.removeprefix(PREFIX): i for n, i in self.labels().items() if n.startswith(PREFIX)}

    def ensure_label(self, category: str) -> str:
        name = PREFIX + category
        if name not in self.labels():
            body = {"name": name, "labelListVisibility": "labelShow",
                    "messageListVisibility": "show"}  # fmt: skip
            created = self._users().labels().create(userId="me", body=body).execute()
            self.labels()[name] = created["id"]
        return self.labels()[name]

    def add_label(self, ids: list[str], label_id: str) -> None:
        for start in range(0, len(ids), 1000):  # batchModify : 1 000 mails par appel
            body = {"ids": ids[start : start + 1000], "addLabelIds": [label_id]}
            self._users().messages().batchModify(userId="me", body=body).execute()

    # --- Corbeille ---

    def trash(self, ids: list[str]) -> int:
        """Met ces mails à la corbeille (récupérables 30 jours) ; renvoie le nombre traité.
        Une seule requête pour 1 000 mails (au lieu d'une par mail, vite freinée par Gmail)."""
        users = self._users()
        for start in range(0, len(ids), 1000):
            body = {"ids": ids[start : start + 1000], "addLabelIds": ["TRASH"]}
            with_retries(
                lambda body=body: users.messages().batchModify(userId="me", body=body).execute()
            )
        return len(ids)

"""Actions sur la boîte Gmail : étiquettes de tri (« Friday/… ») et corbeille.

La corbeille garde les mails 30 jours : rien n'est jamais effacé définitivement (les
autorisations demandées ne le permettent même pas).
"""

from collections.abc import Callable

from friday.google.gmail import Mail, parse_mail

PREFIX = "Friday/"  # toutes les étiquettes de tri de Friday sont rangées sous « Friday »
BATCH = 50  # requêtes groupées (limite conseillée par Google)
MAX_IDS = 500  # au-delà, une seule demande en ferait trop d'un coup


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
        results: dict[str, Mail] = {}

        def store(request_id, response, exception):
            if exception is None:
                results[request_id] = parse_mail(response)

        service = self._service()
        for start in range(0, len(ids), BATCH):
            batch = service.new_batch_http_request(callback=store)
            for mail_id in ids[start : start + BATCH]:
                batch.add(service.users().messages().get(
                    userId="me", id=mail_id, format="metadata",
                    metadataHeaders=["From", "Subject", "Date", "Message-ID"],
                ), request_id=mail_id)  # fmt: skip
            batch.execute()
        return [results[i] for i in ids if i in results]

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
        """Met ces mails à la corbeille (récupérables 30 jours) ; renvoie le nombre traité."""
        done: list[str] = []

        def record(request_id, response, exception):
            if exception is None:
                done.append(request_id)

        service = self._service()
        for start in range(0, len(ids), BATCH):
            batch = service.new_batch_http_request(callback=record)
            for mail_id in ids[start : start + BATCH]:
                batch.add(service.users().messages().trash(userId="me", id=mail_id),
                          request_id=mail_id)  # fmt: skip
            batch.execute()
        return len(done)

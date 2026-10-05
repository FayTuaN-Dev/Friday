"""Traduction des erreurs Google (compte non connecté, réseau, refus) en réponses claires."""

import logging
from collections.abc import Callable

from friday.google import NotConnected
from friday.tools.base import ToolResult

log = logging.getLogger(__name__)


def guarded(action: Callable[[], ToolResult]) -> ToolResult:
    try:
        return action()
    except NotConnected as error:
        return ToolResult(f"{error} Préviens l'utilisateur.")
    except ValueError as error:  # date, heure ou événement non compris / introuvable
        return ToolResult(f"Je n'ai pas compris : {error}. Demande à l'utilisateur de préciser.")
    except Exception as error:
        from googleapiclient.errors import HttpError

        if isinstance(error, HttpError):
            log.warning("Erreur Google %s : %s", error.status_code, error.reason)
            return ToolResult(
                f"Google a refusé la demande ({error.reason}). Préviens l'utilisateur."
            )
        raise

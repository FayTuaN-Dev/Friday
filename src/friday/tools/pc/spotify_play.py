"""« Lance Nova » par l'API Spotify : la phrase à dire, construite par le code ; None quand
l'API ne peut rien (Spotify injoignable…) et que l'ancienne recherche doit prendre le relais."""

import logging

import httpx

from friday.spotify.auth import NotConnected
from friday.spotify.matching import describe
from friday.spotify.player import Spotify, SpotifyError

log = logging.getLogger(__name__)

CONNECT = ("Dis EXACTEMENT : « Je dois d'abord me connecter à ton compte Spotify : une page "
           "s'ouvre dans ton navigateur. Accepte, puis redemande-moi. »")  # fmt: skip


def play_with_api(spotify: Spotify, query: str) -> str | None:
    try:
        choice = spotify.find(query)
        if choice is None:
            return f"Dis EXACTEMENT : « Je ne trouve pas « {query} » sur Spotify. »"
        spotify.play(choice)
        return f"Dis EXACTEMENT : « Je lance {describe(choice)} sur Spotify. »"
    except NotConnected:
        spotify.account.connect_in_background()
        return CONNECT
    except SpotifyError as error:
        log.warning("Spotify : %s (%d)", error, error.status)
        if error.status == 403:
            return ("Dis EXACTEMENT : « Spotify refuse de lancer la lecture : il faut un compte "
                    "Premium. »")  # fmt: skip
        if error.status == 404:
            return ("Dis EXACTEMENT : « L'appli Spotify ne répond pas : ouvre-la, puis "
                    "redemande-moi. »")  # fmt: skip
        return None
    except httpx.HTTPError as error:
        log.warning("Spotify injoignable : %s", error)
        return None

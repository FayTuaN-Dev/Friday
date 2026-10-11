"""Spotify par son API : connexion PKCE (sans secret), choix de ce qu'on lance (ses playlists
d'abord), lecture sur l'appli du PC (ouverte si besoin), phrases construites par le code."""

import json
import time

import httpx

from friday.app.backup import SKIP_FILES
from friday.spotify.auth import NotConnected, SpotifyAccount, challenge
from friday.spotify.matching import Choice, best, clean, describe
from friday.spotify.player import Spotify
from friday.tools.pc.media import PlayMusicTool
from friday.tools.pc.spotify_play import CONNECT, play_with_api

NOVA = {"name": "Nova", "uri": "spotify:playlist:mine", "owner": {"display_name": "Val"}}
SEARCH = {
    "playlists": {"items": [None, {"name": "Radio Nova Mix", "uri": "spotify:playlist:radio",
                                   "owner": {"display_name": "Nova"}}]},
    "artists": {"items": [{"name": "Daft Punk", "uri": "spotify:artist:dp"}]},
    "albums": {"items": [{"name": "Discovery", "uri": "spotify:album:disc",
                          "artists": [{"name": "Daft Punk"}]}]},
    "tracks": {"items": [{"name": "One More Time", "uri": "spotify:track:omt",
                          "artists": [{"name": "Daft Punk"}]}]},
}  # fmt: skip


class Account:
    configured = True

    def __init__(self, connected=True):
        self.connected, self.asked = connected, 0

    def access_token(self):
        if not self.connected:
            raise NotConnected("non connecté")
        return "jeton"

    def connect_in_background(self):
        self.asked += 1


def fake_api(devices=({"id": "pc", "type": "Computer", "is_active": False},), play_status=204):
    calls = []
    state = {"devices": list(devices)}

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        path = request.url.path
        if path == "/v1/me/playlists":
            return httpx.Response(200, json={"items": [NOVA], "next": None})
        if path == "/v1/search":
            return httpx.Response(200, json=SEARCH)
        if path == "/v1/me/player/devices":
            return httpx.Response(200, json={"devices": state["devices"]})
        if path == "/v1/me/player/play":
            return httpx.Response(play_status, json={"error": {"message": "Premium required"}}
                                  if play_status >= 400 else None)  # fmt: skip
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return client, calls, state


def test_what_to_play_is_chosen_well():
    assert clean("ma playlist Nova sur Spotify") == ("nova", "playlist")
    assert clean("mets-moi un peu de Daft Punk") == ("daft punk", "")
    assert clean("l'album Discovery") == ("discovery", "album")
    assert clean("un peu de jazz") == ("jazz", "playlist")  # un style : une playlist
    mine = Choice("playlist", "Nova", "u1", mine=True)
    radio = Choice("playlist", "Radio Nova Mix", "u2")
    assert best("Nova", [radio, mine]) is mine  # ses playlists d'abord
    album = Choice("album", "Discovery", "u3", "Daft Punk")
    track = Choice("track", "Discovery", "u4", "Daft Punk")
    assert best("l'album Discovery", [track, album]) is album  # le type demandé compte
    assert describe(mine) == "ta playlist « Nova »"
    assert describe(album) == "l'album « Discovery » de Daft Punk"
    assert describe(Choice("artist", "Daft Punk", "u5")) == "les titres de Daft Punk"


def test_the_playlist_is_launched_on_the_pc():
    client, calls, _ = fake_api()
    spotify = Spotify(Account(), client)
    said = play_with_api(spotify, "lance Nova")
    assert said == "Dis EXACTEMENT : « Je lance ta playlist « Nova » sur Spotify. »"
    play = calls[-1]
    assert play.method == "PUT" and play.url.params["device_id"] == "pc"
    assert json.loads(play.content) == {"context_uri": "spotify:playlist:mine"}
    assert all(r.headers["Authorization"] == "Bearer jeton" for r in calls)
    play_with_api(spotify, "la chanson One More Time")
    assert json.loads(calls[-1].content) == {"uris": ["spotify:track:omt"]}  # un titre seul


def test_a_closed_app_is_opened_and_waited_for():
    client, _, state = fake_api(devices=())
    opened = []

    def launch():
        opened.append(1)
        state["devices"] = [{"id": "pc", "type": "Computer", "is_active": False}]

    spotify = Spotify(Account(), client, launch=launch, sleep=lambda s: None)
    assert "Je lance" in play_with_api(spotify, "Discovery") and opened == [1]
    never = Spotify(Account(), fake_api(devices=())[0], launch=lambda: None, sleep=lambda s: None)
    assert "L'appli Spotify ne répond pas" in play_with_api(never, "Nova")


def test_connection_premium_and_fallback():
    account = Account(connected=False)
    assert play_with_api(Spotify(account, fake_api()[0]), "Nova") == CONNECT
    assert account.asked == 1  # la page de connexion s'ouvre (en arrière-plan)
    refused = Spotify(Account(), fake_api(play_status=403)[0])
    assert "il faut un compte Premium" in play_with_api(refused, "Nova")
    opened = []
    down = Spotify(Account(), fake_api(play_status=500)[0])
    tool = PlayMusicTool(True, down, open_uri=opened.append, open_url=opened.append)
    assert "Recherche « Nova » ouverte dans Spotify" in tool.run("Nova").text  # l'ancienne voie
    assert opened == ["spotify:search:Nova"]


def test_token_is_refreshed_and_never_backed_up(tmp_path):
    assert challenge("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk") == (
        "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM")  # exemple de la RFC 7636  # fmt: skip
    path = tmp_path / "spotify_token.json"
    path.write_text(json.dumps({"access_token": "vieux", "refresh_token": "r1",
                                "expires_at": time.time() - 10}), "utf-8")  # fmt: skip
    sent = []

    def handler(request):
        sent.append(dict(httpx.QueryParams(request.content.decode())))
        return httpx.Response(200, json={"access_token": "neuf", "expires_in": 3600})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    account = SpotifyAccount("mon-id", path, http=http)
    assert account.access_token() == "neuf"
    assert sent[0] == {"grant_type": "refresh_token", "refresh_token": "r1", "client_id": "mon-id"}
    assert json.loads(path.read_text("utf-8"))["refresh_token"] == "r1"  # gardé
    assert "client_secret" not in account.authorize_url("v", "s")  # PKCE : aucun secret
    assert "spotify_token.json" in SKIP_FILES
    try:
        SpotifyAccount("mon-id", tmp_path / "absent.json").access_token()
        raise AssertionError("doit demander la connexion")
    except NotConnected:
        pass

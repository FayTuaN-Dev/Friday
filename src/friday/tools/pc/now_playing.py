"""Ce qui joue sur le PC (J4) : titre, artiste, pochette, avancement, d'après Windows (la même
source que le lecteur du menu volume : Spotify, YouTube dans le navigateur, VLC…), et les
commandes lecture/pause, suivant, précédent. API asynchrone de Windows → un fil dédié avec
sa propre boucle ; les méthodes publiques sont synchrones (quelques millisecondes)."""

import asyncio
import logging
import threading
from dataclasses import dataclass

log = logging.getLogger(__name__)

PLAYING = 4  # GlobalSystemMediaTransportControlsSessionPlaybackStatus.PLAYING
TIMEOUT = 3.0


@dataclass
class Track:
    app: str  # « Spotify.exe », « chrome »…
    title: str
    artist: str
    playing: bool
    position: float  # s
    duration: float  # s (0 si inconnue)
    cover: bytes | None = None  # image de la pochette


def app_name(app_id: str) -> str:
    """« Spotify.exe » → « Spotify » ; « MSEdge » → « Edge » ; « 308046B0…!Spotify » → idem."""
    name = app_id.split("!")[-1].removesuffix(".exe")
    return {"msedge": "Edge", "chrome": "Chrome", "firefox": "Firefox"}.get(name.lower(), name)


class NowPlaying:
    def __init__(self) -> None:
        from winrt.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager as Manager,
        )

        self._manager_class = Manager
        self._manager = None
        self._covers: dict[tuple[str, str], bytes | None] = {}
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._loop.run_forever, daemon=True, name="media").start()

    def _run(self, coroutine):
        return asyncio.run_coroutine_threadsafe(coroutine, self._loop).result(TIMEOUT)

    async def _session(self):
        if self._manager is None:
            self._manager = await self._manager_class.request_async()
        return self._manager.get_current_session()

    def current(self) -> Track | None:
        """Le morceau en cours (ou en pause), None si rien n'est ouvert."""
        try:
            return self._run(self._current())
        except Exception as error:  # session fermée entre-temps, Windows occupé…
            log.debug("Lecture en cours illisible : %s", error)
            return None

    async def _current(self) -> Track | None:
        session = await self._session()
        if session is None:
            return None
        props = await session.try_get_media_properties_async()
        if not props or not props.title:
            return None
        timeline = session.get_timeline_properties()
        key = (props.title, props.artist)
        if key not in self._covers:
            self._covers = {key: await self._cover(props.thumbnail)}  # une seule en mémoire
        return Track(app_name(session.source_app_user_model_id), props.title, props.artist or "",
                     session.get_playback_info().playback_status == PLAYING,
                     timeline.position.total_seconds(), timeline.end_time.total_seconds(),
                     self._covers[key])  # fmt: skip

    async def _cover(self, thumbnail) -> bytes | None:
        if thumbnail is None:
            return None
        from winrt.windows.storage.streams import Buffer, InputStreamOptions

        try:
            stream = await thumbnail.open_read_async()
            buffer = Buffer(stream.size)
            await stream.read_async(buffer, buffer.capacity, InputStreamOptions.READ_AHEAD)
            return bytes(memoryview(buffer))
        except Exception as error:
            log.debug("Pochette illisible : %s", error)
            return None

    def command(self, action: str) -> None:
        """« toggle », « next » ou « previous »."""

        async def run() -> None:
            session = await self._session()
            if session is not None:
                await {"toggle": session.try_toggle_play_pause_async,
                       "next": session.try_skip_next_async,
                       "previous": session.try_skip_previous_async}[action]()  # fmt: skip

        try:
            self._run(run())
        except Exception as error:
            log.warning("Commande média « %s » impossible : %s", action, error)

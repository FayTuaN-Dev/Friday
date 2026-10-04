"""Volume du PC (pycaw).

Certains mixeurs virtuels (SteelSeries Sonar…) verrouillent le volume général de Windows :
le réglage est accepté mais sans effet. On vérifie donc toujours en relisant, et si c'est
verrouillé, on règle le volume de chaque application (comme le mélangeur de volume de
Windows), sauf celui de Jarvis pour qu'il reste audible.
"""

import logging
import os
import time

from jarvis.tools.base import Tool, ToolResult

log = logging.getLogger(__name__)

TOLERANCE = 0.02  # écart accepté à la relecture
# Un mixeur virtuel annule le réglage avec un petit retard : on attend avant de relire.
PROBE_DELAY = 0.4


class Volume:
    def __init__(self) -> None:
        self._locked: bool | None = None  # inconnu tant qu'on n'a pas testé

    def _audio(self):
        import comtypes
        from pycaw.pycaw import AudioUtilities

        comtypes.CoInitialize()  # chaque outil tourne dans son propre thread
        return AudioUtilities

    def _endpoint(self):
        return self._audio().GetSpeakers().EndpointVolume

    def _sessions(self) -> list:
        """Volumes des applications qui jouent du son, sauf Jarvis lui-même."""
        return [
            s for s in self._audio().GetAllSessions() if s.Process and s.Process.pid != os.getpid()
        ]

    def locked(self) -> bool:
        """Le volume général est-il verrouillé ? Testé une fois (on essaie une autre valeur
        une fraction de seconde, puis on remet), puis mémorisé.

        Relire après avoir réglé ne suffit pas : demander 100 % à un volume bloqué à 100 %
        « réussit » toujours.
        """
        if self._locked is None:
            endpoint = self._endpoint()
            before = endpoint.GetMasterVolumeLevelScalar()
            probe = before - 0.1 if before > 0.5 else before + 0.1
            endpoint.SetMasterVolumeLevelScalar(probe, None)
            time.sleep(PROBE_DELAY)  # Sonar remet sa valeur avec un léger retard
            self._locked = abs(endpoint.GetMasterVolumeLevelScalar() - probe) > TOLERANCE
            endpoint.SetMasterVolumeLevelScalar(before, None)
            if self._locked:
                log.info("Volume général verrouillé (mixeur virtuel ?) : réglage par application")
        return self._locked

    def get(self) -> int:
        if self.locked() and (sessions := self._sessions()):
            return round(max(s.SimpleAudioVolume.GetMasterVolume() for s in sessions) * 100)
        return round(self._endpoint().GetMasterVolumeLevelScalar() * 100)

    def set(self, level: int) -> str:
        """Renvoie ce qui a été réglé ; lève RuntimeError si rien n'a pu l'être."""
        value = max(0, min(100, level)) / 100
        if not self.locked():
            self._endpoint().SetMasterVolumeLevelScalar(value, None)
            return "volume général"
        names = []
        for session in self._sessions():
            session.SimpleAudioVolume.SetMasterVolume(value, None)
            names.append(session.Process.name().removesuffix(".exe"))
        if not names:
            raise RuntimeError("volume général verrouillé et aucune application ne joue de son")
        return f"volume de chaque application ({', '.join(sorted(set(names)))})"

    def mute(self, muted: bool) -> str:
        endpoint = self._endpoint()
        endpoint.SetMute(int(muted), None)
        if bool(endpoint.GetMute()) == muted:
            return "son général"
        sessions = self._sessions()
        for session in sessions:
            session.SimpleAudioVolume.SetMute(int(muted), None)
        if not sessions:
            raise RuntimeError("son général verrouillé et aucune application ne joue de son")
        return "son de chaque application"


class VolumeTool(Tool):
    name = "set_volume"
    description = (
        "Règle le volume de l'ordinateur : un niveau précis (0 à 100), une variation "
        "(+10 pour monter, -10 pour baisser), ou couper / remettre le son."
    )
    parameters = {
        "level": {"type": "integer", "description": "Niveau voulu, de 0 à 100"},
        "change": {"type": "integer", "description": "Variation : +10, -20…"},
        "mute": {"type": "boolean", "description": "true = couper le son, false = le remettre"},
    }

    def __init__(self, volume=None) -> None:
        self.volume = volume or Volume()

    def label(self, args: dict) -> str:
        return "🔊 Volume"

    def run(self, level: int | None = None, change: int | None = None,
            mute: bool | None = None) -> ToolResult:  # fmt: skip
        try:
            if mute is not None:
                where = self.volume.mute(bool(mute))
                return ToolResult(f"{'Coupé' if mute else 'Remis'} : {where}.")
            if level is None and change is None:
                return ToolResult(f"Le volume est à {self.volume.get()} %.")
            target = int(level) if level is not None else self.volume.get() + int(change)
            target = max(0, min(100, target))
            where = self.volume.set(target)
            self.volume.mute(False)
        except RuntimeError as e:
            return ToolResult(f"Le volume n'a pas pu être changé : {e}. Dis-le honnêtement.")
        return ToolResult(f"Volume réglé à {target} % ({where}).")

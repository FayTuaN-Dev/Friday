"""Volume du PC (pycaw) : général, ou par application.

Certains mixeurs virtuels (SteelSeries Sonar…) verrouillent le volume général de Windows :
le réglage est accepté mais annulé un instant plus tard. On le détecte (une fois), et l'on
règle alors le volume de chaque application, comme le mélangeur de volume de Windows.
Sonar répartit les applications sur plusieurs sorties (Gaming, Chat, Media…) : on les
parcourt toutes. Sonar remet aussi ces volumes à 100 % (constaté) : quand il tourne, le
réglage passe par Sonar lui-même (tools/pc/sonar.py).
"""

import logging
import os
import time
from dataclasses import dataclass
from typing import Any

from friday.tools.base import Tool, ToolResult
from friday.tools.pc.sonar import NAMES, Sonar, SonarUnavailable, channel_of
from friday.voice.wake import normalize

log = logging.getLogger(__name__)

TOLERANCE = 0.02  # écart accepté à la relecture
# Un mixeur virtuel annule le réglage avec un petit retard : on attend avant de relire.
PROBE_DELAY = 0.4
# Processus audio du système ou du mixeur : y toucher changerait le son de tout le PC.
SYSTEM_AUDIO = {"audiodg", "steelseriessonar", "svchost", "systemsettings"}


@dataclass
class AppAudio:
    """Le volume d'une application sur une sortie audio (ISimpleAudioVolume)."""

    name: str  # « Spotify »
    pid: int
    control: Any
    device: str = ""  # la sortie Windows (« SteelSeries Sonar - Media (…) »)

    def get(self) -> float:
        return self.control.GetMasterVolume()

    def set(self, value: float) -> None:
        self.control.SetMasterVolume(value, None)

    def mute(self, muted: bool) -> None:
        self.control.SetMute(int(muted), None)


class Volume:
    def __init__(self, find_sonar=None) -> None:
        self._locked: bool | None = None  # inconnu tant qu'on n'a pas testé
        # Cherché à chaque fois : GG peut être fermé ou relancé
        self._find_sonar = find_sonar or (lambda: Sonar.find())

    def _by_sonar(self, app: str | None, action) -> str | None:
        """Règle par Sonar s'il tourne : le master, ou les sorties de l'application ; None si
        Sonar n'est pas là (ou ne gère pas cette application) : réglage Windows."""
        sonar = self._find_sonar()
        if sonar is None:
            return None
        try:
            if not app:
                action(sonar, "master")
                return "volume général, dans Sonar"
            targets = self._targets(app)
            channels = sorted({c for t in targets if (c := channel_of(t.device))})
            if not channels:
                return None
            for channel in channels:
                action(sonar, channel)
            outputs = ", ".join(NAMES[c] for c in channels)
            apps = ", ".join(sorted({t.name for t in targets}))
            return (f"sortie {outputs} de Sonar, où joue {apps} : les autres applications de "
                    "cette sortie changent aussi")  # fmt: skip
        except SonarUnavailable as error:
            log.warning("%s : réglage par Windows", error)
            return None

    def _endpoint(self):
        import comtypes
        from pycaw.pycaw import AudioUtilities

        comtypes.CoInitialize()  # chaque outil tourne dans son propre thread
        return AudioUtilities.GetSpeakers().EndpointVolume

    def apps(self) -> list[AppAudio]:
        """Les applications qui ont du son, sur toutes les sorties (sauf Friday et le système)."""
        import comtypes
        import psutil
        from pycaw.constants import DEVICE_STATE, EDataFlow
        from pycaw.pycaw import AudioUtilities, IAudioSessionControl2, ISimpleAudioVolume

        comtypes.CoInitialize()
        found = []
        devices = AudioUtilities.GetAllDevices(EDataFlow.eRender.value, DEVICE_STATE.ACTIVE.value)
        for device in devices:
            try:
                sessions = device.AudioSessionManager.GetSessionEnumerator()
            except comtypes.COMError:
                continue
            for i in range(sessions.GetCount()):
                control = sessions.GetSession(i).QueryInterface(IAudioSessionControl2)
                pid = control.GetProcessId()
                if not pid or pid == os.getpid():
                    continue
                try:
                    name = psutil.Process(pid).name().removesuffix(".exe")
                except psutil.Error:
                    continue
                if normalize(name) not in SYSTEM_AUDIO:
                    found.append(
                        AppAudio(
                            name,
                            pid,
                            control.QueryInterface(ISimpleAudioVolume),
                            getattr(device, "FriendlyName", "") or "",
                        )
                    )
        return found

    def locked(self) -> bool:
        """Le volume général est-il verrouillé ? Testé une fois (on essaie une autre valeur
        une fraction de seconde, puis on remet), puis mémorisé. Relire après avoir réglé ne
        suffit pas : demander 100 % à un volume bloqué à 100 % « réussit » toujours."""
        if self._locked is None:
            endpoint = self._endpoint()
            before = endpoint.GetMasterVolumeLevelScalar()
            probe = before - 0.1 if before > 0.5 else before + 0.1
            endpoint.SetMasterVolumeLevelScalar(probe, None)
            time.sleep(PROBE_DELAY)
            self._locked = abs(endpoint.GetMasterVolumeLevelScalar() - probe) > TOLERANCE
            endpoint.SetMasterVolumeLevelScalar(before, None)
            if self._locked:
                log.info("Volume général verrouillé (mixeur virtuel ?) : réglage par application")
        return self._locked

    def _targets(self, app: str | None) -> list[AppAudio]:
        apps = self.apps()
        if app:
            wanted = normalize(app).replace(" ", "")
            apps = [a for a in apps if wanted in normalize(a.name).replace(" ", "")]
            if not apps:
                raise RuntimeError(f"{app} ne joue pas de son en ce moment")
        elif not apps:
            raise RuntimeError("volume général verrouillé et aucune application ne joue de son")
        return apps

    def get(self, app: str | None = None) -> int:
        levels: list[int] = []
        if self._by_sonar(app, lambda sonar, channel: levels.append(sonar.get(channel))):
            return max(levels)
        if app or self.locked():
            return round(max(a.get() for a in self._targets(app)) * 100)
        return round(self._endpoint().GetMasterVolumeLevelScalar() * 100)

    def set(self, level: int, app: str | None = None) -> str:
        """Renvoie ce qui a été réglé ; lève RuntimeError si rien n'a pu l'être."""
        value = max(0, min(100, level)) / 100
        if where := self._by_sonar(app, lambda sonar, channel: sonar.set(level, channel)):
            return where
        if not app and not self.locked():
            self._endpoint().SetMasterVolumeLevelScalar(value, None)
            return "volume général"
        targets = self._targets(app)
        for target in targets:
            target.set(value)
        return f"volume de {', '.join(sorted({t.name for t in targets}))}"

    def mute(self, muted: bool, app: str | None = None) -> str:
        if where := self._by_sonar(app, lambda sonar, channel: sonar.mute(muted, channel)):
            return where.replace("volume", "son")
        if not app:
            endpoint = self._endpoint()
            endpoint.SetMute(int(muted), None)
            if not self.locked():
                return "son général"
        targets = self._targets(app)
        for target in targets:
            target.mute(muted)
        return f"son de {', '.join(sorted({t.name for t in targets}))}"


class VolumeTool(Tool):
    name = "set_volume"
    description = (
        "Règle le volume : un niveau (0 à 100), une variation (+10 / -10), ou couper / remettre "
        "le son. Avec « app », ne règle que cette application (« mets Spotify à 15 % »). "
        "N'utilise jamais media_control pour régler le volume."
    )
    parameters = {
        "level": {"type": "integer", "description": "Niveau voulu, de 0 à 100"},
        "change": {"type": "integer", "description": "Variation : +10, -20…"},
        "mute": {"type": "boolean", "description": "true = couper le son, false = le remettre"},
        "app": {"type": "string", "description": "Une seule application (vide = tout le PC)"},
    }

    def __init__(self, volume=None) -> None:
        self.volume = volume or Volume()

    def label(self, args: dict) -> str:
        return f"🔊 Volume{' : ' + args['app'] if args.get('app') else ''}"

    def run(self, level: int | None = None, change: int | None = None,
            mute: bool | None = None, app: str | None = None) -> ToolResult:  # fmt: skip
        app = app or None
        try:
            if mute is not None:
                where = self.volume.mute(mute, app)
                return ToolResult(f"{'Coupé' if mute else 'Remis'} : {where}.")
            if level is None and change is None:
                return ToolResult(f"Le volume est à {self.volume.get(app)} %.")
            target = int(level) if level is not None else self.volume.get(app) + int(change)
            target = max(0, min(100, target))
            where = self.volume.set(target, app)
        except RuntimeError as e:
            return ToolResult(f"Le volume n'a pas pu être changé : {e}. Dis-le honnêtement.")
        return ToolResult(f"Volume réglé à {target} % ({where}).")

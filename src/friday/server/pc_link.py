"""Le lien du Pi avec le PC (R4, R5).

- R4 : allumer le PC (Wake-on-LAN : le « paquet magique » envoyé sur le réseau de la maison),
  voir s'il est allumé et l'éteindre, par son agent (pc_agent.py, joint par Tailscale).
- R5 : quand le PC est allumé et que sa carte graphique est libre, le Pi PENSE avec lui
  (qwen3:8b, bien plus rapide et plus juste que le petit modèle du Pi) ; sinon, avec le sien.
  « Libre » : le modèle déjà chargé, ou assez de mémoire vidéo (pas en pleine partie)."""

import dataclasses
import logging
import os
import socket
import time
from dataclasses import dataclass

import httpx
import ollama

log = logging.getLogger(__name__)
FRESH = 20.0  # secondes : l'état du PC est relu au plus toutes les 20 s
NEEDED_MB = 6800  # qwen3:8b chargé : ~6,3 Go (mesuré), plus une marge


@dataclass(frozen=True)
class PcSettings:
    agent: str  # http://100.87.38.95:8766
    ollama: str  # http://100.87.38.95:11434
    model: str = "qwen3:8b"
    num_ctx: int = 8192  # le même que le Friday du PC : le modèle chargé sert aux deux
    mac: str = ""  # 40:B0:76:A3:D1:15
    broadcast: str = "192.168.1.255"


def load_pc_settings() -> PcSettings | None:
    agent = os.getenv("FRIDAY_PC_AGENT_URL", "").strip().rstrip("/")
    if not agent:
        return None
    return PcSettings(
        agent, os.getenv("FRIDAY_PC_OLLAMA", "").strip().rstrip("/"),
        os.getenv("FRIDAY_PC_MODEL", "qwen3:8b").strip(),
        int(os.getenv("FRIDAY_PC_NUM_CTX", "8192")), os.getenv("FRIDAY_PC_MAC", "").strip(),
        os.getenv("FRIDAY_PC_BROADCAST", "192.168.1.255").strip(),
    )  # fmt: skip


def magic_packet(mac: str) -> bytes:
    raw = bytes.fromhex(mac.replace(":", "").replace("-", ""))
    if len(raw) != 6:
        raise ValueError(f"adresse MAC invalide : {mac}")
    return b"\xff" * 6 + raw * 16


class PcLink:
    def __init__(self, pc: PcSettings, token: str, get=httpx.get, post=httpx.post,
                 clock=time.monotonic) -> None:  # fmt: skip
        self.pc, self.token, self._get, self._post, self.clock = pc, token, get, post, clock
        self._seen: tuple[float, dict | None] = (-FRESH, None)
        self._local = None  # (client, réglages) du Pi, gardés pour y revenir

    @property
    def _auth(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    def state(self, fresh: bool = False) -> dict | None:
        """L'état donné par l'agent du PC ; None : PC éteint (ou injoignable)."""
        stamp, seen = self._seen
        if not fresh and self.clock() - stamp < FRESH:
            return seen
        try:
            seen = self._get(f"{self.pc.agent}/etat", headers=self._auth, timeout=2).json()
        except (httpx.HTTPError, ValueError):
            seen = None
        self._seen = (self.clock(), seen)
        return seen

    def can_think(self) -> bool:
        """Le PC peut-il penser pour le Pi ? (allumé, Ollama prêt, carte graphique libre)"""
        seen = self.state()
        if not seen or not seen.get("ollama") or not self.pc.ollama:
            return False
        free = seen.get("gpu_libre_mo")
        return bool(seen.get("modele_charge")) or (free is not None and free >= NEEDED_MB)

    def wake(self, send=None) -> None:
        packet = magic_packet(self.pc.mac)
        if send is not None:
            send(packet)
            return
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            for port in (9, 7):
                sock.sendto(packet, (self.pc.broadcast, port))
        self._seen = (-FRESH, None)

    def shutdown(self, delay: int = 60) -> bool:
        try:
            self._post(f"{self.pc.agent}/eteindre", json={"delai": delay}, headers=self._auth,
                       timeout=5).raise_for_status()  # fmt: skip
        except httpx.HTTPError as error:
            log.warning("Extinction du PC impossible : %s", error)
            return False
        self._seen = (-FRESH, None)
        return True

    def apply(self, brain) -> str:
        """Fait penser `brain` avec le PC s'il le peut, sinon avec le Pi : « PC » ou « Pi »."""
        if self._local is None:
            self._local = (brain.client, brain.settings, brain.keep_alive)
        if self.can_think():
            if brain.settings.ollama_model != self.pc.model:
                brain.client = ollama.Client(host=self.pc.ollama)
                brain.settings = dataclasses.replace(
                    self._local[1], ollama_model=self.pc.model, ollama_num_ctx=self.pc.num_ctx
                )
                brain.keep_alive = "30m"  # pas toute la nuit dans la carte graphique du PC
                log.info("Le Pi pense avec le PC (%s)", self.pc.model)
            return "PC"
        if brain.settings is not self._local[1]:
            brain.client, brain.settings, brain.keep_alive = self._local
            log.info("Le Pi pense avec son propre modèle")
        return "Pi"

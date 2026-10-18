"""Le Pi et le PC (R4, R5) : réveil par le réseau, état, extinction confirmée sur le
téléphone, et le Pi qui pense avec la carte graphique du PC quand elle est libre. Rien ne
touche ni le vrai PC ni le réseau : tout est simulé."""

import json
import threading
from dataclasses import dataclass
from http.server import ThreadingHTTPServer

import httpx
import pytest

from friday.brain.events import ConfirmationRequest
from friday.pc_agent import make_handler
from friday.server.http_api import Confirmations, lines_of
from friday.server.pc_link import PcLink, PcSettings, magic_packet
from friday.server.pc_tools import PcStateTool, ShutdownPcTool, WakePcTool

PC = PcSettings("http://pc:8766", "http://pc:11434", mac="40:B0:76:A3:D1:15")


class Answers:
    """L'agent du PC simulé : une suite d'états (None : éteint)."""

    def __init__(self, *states):
        self.states, self.posted = list(states), []

    def get(self, url, headers=None, timeout=None):
        state = self.states.pop(0) if len(self.states) > 1 else self.states[0]
        if state is None:
            raise httpx.ConnectError("éteint")
        return httpx.Response(200, json=state, request=httpx.Request("GET", url))

    def post(self, url, json=None, headers=None, timeout=None):
        self.posted.append((url, json))
        return httpx.Response(200, json={"ok": True}, request=httpx.Request("POST", url))


def link(*states, clock=lambda: 0.0):
    fake = Answers(*states)
    return PcLink(PC, "clé", get=fake.get, post=fake.post, clock=clock), fake


ON = {"allume": True, "session": True, "ollama": True, "modele_charge": False,
      "gpu_libre_mo": 7500}  # fmt: skip


def test_the_magic_packet_wakes_this_mac_only():
    packet = magic_packet("40:B0:76:A3:D1:15")
    assert len(packet) == 102 and packet[:6] == b"\xff" * 6
    assert packet[6:12] == bytes.fromhex("40B076A3D115") and packet.count(packet[6:12]) == 16
    with pytest.raises(ValueError):
        magic_packet("40:B0:76")


def test_the_pi_thinks_with_the_pc_only_when_its_graphics_card_is_free():
    assert link(ON)[0].can_think()
    assert link({**ON, "gpu_libre_mo": 1200, "modele_charge": True})[0].can_think()  # déjà là
    assert not link({**ON, "gpu_libre_mo": 1200})[0].can_think()  # en pleine partie
    assert not link({**ON, "ollama": False})[0].can_think()
    assert not link(None)[0].can_think()  # éteint


@dataclass(frozen=True)
class Brainy:
    ollama_model: str = "qwen3:4b-instruct-2507-q4_K_M"
    ollama_num_ctx: int = 4096


def test_the_brain_switches_to_the_pc_and_back():
    now = [0.0]
    pc, _ = link(ON, None, clock=lambda: now[0])
    brain = type("B", (), {})()
    brain.client, brain.settings, brain.keep_alive = "client du Pi", Brainy(), -1
    assert pc.apply(brain) == "PC"
    assert (brain.settings.ollama_model, brain.settings.ollama_num_ctx) == ("qwen3:8b", 8192)
    assert brain.keep_alive == "30m" and brain.client != "client du Pi"
    now[0] = 30.0
    assert pc.apply(brain) == "Pi"  # 30 s plus tard, le PC est éteint
    assert brain.client == "client du Pi" and brain.settings == Brainy() and brain.keep_alive == -1


def test_waking_the_pc_waits_for_it_and_says_when_it_does_not_answer():
    pc, _ = link(None, None, None, ON)
    sent = []
    pc.wake = lambda: sent.append("paquet")
    assert "Le PC est allumé" in WakePcTool(pc, sleep=lambda s: None).run().text and sent
    pc, _ = link(None)
    pc.wake = lambda: None
    assert "BIOS" in WakePcTool(pc, sleep=lambda s: None).run().text
    assert "déjà allumé" in WakePcTool(link(ON)[0], sleep=lambda s: None).run().text


def test_shutting_down_warns_about_an_open_session_and_asks_the_agent():
    pc, fake = link(ON)
    tool = ShutdownPcTool(pc)
    assert tool.needs_confirmation and "une session est ouverte" in tool.confirmation({})
    assert "s'éteint dans une minute" in tool.run().text
    assert fake.posted == [("http://pc:8766/eteindre", {"delai": 60})]
    assert "éteint" in PcStateTool(link(None)[0]).run().text


def test_the_pc_agent_answers_only_with_the_key():
    stops = []
    handler = make_handler("cle-123", "qwen3:8b", (lambda: ON, stops.append, lambda: None))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        assert httpx.get(f"{url}/etat").status_code == 401
        key = {"Authorization": "Bearer cle-123"}
        assert httpx.get(f"{url}/etat", headers=key).json() == ON
        assert httpx.post(f"{url}/eteindre", json={"delai": 30}, headers=key).status_code == 200
        assert stops == [30]
    finally:
        httpd.shutdown()


def test_a_confirmation_is_answered_from_the_phone_mid_answer():
    class Brain:
        def reply(self, text):
            request = ConfirmationRequest("shutdown_pc", {}, "J'éteins le PC dans une minute ?")
            yield request
            yield "C'est fait." if request.wait(5) else "Rien fait."

    asked = Confirmations()
    pc = type("P", (), {"apply": lambda self, brain: "PC"})()
    lines = lines_of(Brain(), "éteins le PC", asked, pc)
    assert next(lines) == {"cerveau": "PC"}
    question = next(lines)
    assert question["confirmer"] == "J'éteins le PC dans une minute ?"
    assert asked.answer(question["id"], True) and not asked.answer(question["id"], True)
    assert {"texte": "C'est fait."} in list(lines)
    assert json.dumps(question)  # envoyable tel quel au téléphone

from fakes import SETTINGS, EchoTool, FakeClient, tool_call

from jarvis.brain.conversation import TOOL_RESULT_KEEP_CHARS, Conversation
from jarvis.brain.events import ToolFinished, ToolStarted
from jarvis.brain.llm import MAX_TOOL_ROUNDS, Brain
from jarvis.tools import images, web_page, web_search
from jarvis.tools.base import Tool, ToolBox


def brain_with_tool(rounds):
    client = FakeClient(rounds=rounds)
    return Brain(SETTINGS, client=client, toolbox=ToolBox([EchoTool()])), client


def test_tool_round_trip():
    brain, client = brain_with_tool(
        [[tool_call("web_search", query="météo Lyon")], ["Il fait ", "18 degrés."]]
    )
    events = list(brain.reply("Quel temps à Lyon ?"))

    assert isinstance(events[0], ToolStarted)
    assert events[0].label == "🔎 Recherche : météo Lyon"
    assert isinstance(events[1], ToolFinished)
    assert events[1].result.display.kind == "results"
    assert events[2:] == ["Il fait ", "18 degrés."]

    roles = [m["role"] for m in brain.conversation.messages]
    assert roles == ["user", "assistant", "tool", "assistant"]
    assert brain.conversation.messages[1]["tool_calls"][0]["function"]["name"] == "web_search"
    # Le 2e appel au modèle contient le résultat de l'outil
    assert client.calls[1]["messages"][-1]["role"] == "tool"
    assert client.calls[0]["tools"][0]["function"]["name"] == "web_search"


def test_last_round_has_no_tools():
    rounds = [[tool_call("web_search", query="x")]] * MAX_TOOL_ROUNDS + [["Fin."]]
    brain, client = brain_with_tool(rounds)
    assert list(brain.reply("?"))[-1] == "Fin."
    assert client.calls[-1]["tools"] is None  # il doit conclure


def test_prompt_mentions_tools_only_when_available():
    brain, client = brain_with_tool([["ok"]])
    list(brain.reply("?"))
    assert "web_search" in client.calls[0]["messages"][0]["content"]

    plain = Brain(SETTINGS, client=FakeClient(chunks=["ok"]))
    list(plain.reply("?"))
    assert "web_search" not in plain.client.calls[0]["messages"][0]["content"]


def test_tool_results_are_compacted():
    conv = Conversation()
    conv.add("user", "q")
    conv.add("tool", "x" * 5000, tool_name="web_search")
    conv.compact_tool_results()
    assert len(conv.messages[1]["content"]) < TOOL_RESULT_KEEP_CHARS + 10


def test_toolbox_handles_unknown_and_failing_tools():
    class Broken(Tool):
        name = "broken"
        description = "plante"
        parameters = {}

        def run(self):
            raise RuntimeError("boum")

    box = ToolBox([Broken()])
    assert "n'existe pas" in box.run("inconnu", {}).text
    assert "boum" in box.run("broken", {}).text
    assert box.schemas()[0]["function"]["parameters"]["type"] == "object"


class FakeDDGS:
    def text(self, query, region, max_results):
        return [{"title": "Météo Lyon", "href": "https://meteo.fr/lyon", "body": "18°C"}]

    def images(self, query, region, max_results):
        return [
            {"title": f"img{i}", "thumbnail": f"t{i}", "url": f"u{i}", "image": f"i{i}"}
            for i in range(4)
        ]


def test_web_search_tool(monkeypatch):
    monkeypatch.setattr(web_search, "DDGS", FakeDDGS)
    result = web_search.WebSearchTool().run("météo Lyon")
    assert "18°C" in result.text and "meteo.fr" in result.text
    assert result.display.data["results"][0]["url"] == "https://meteo.fr/lyon"


def test_image_tool_skips_failed_downloads(monkeypatch):
    monkeypatch.setattr(images, "DDGS", FakeDDGS)
    monkeypatch.setattr(images, "download", lambda url: None if url == "t1" else b"png")
    result = images.ImageSearchTool(count=6).run("chat")
    assert [i["title"] for i in result.display.data["images"]] == ["img0", "img2", "img3"]


def test_read_webpage_tool(monkeypatch):
    trafilatura = web_page.trafilatura
    monkeypatch.setattr(trafilatura, "fetch_url", lambda url: "<html>")
    monkeypatch.setattr(trafilatura, "extract", lambda html: "Long texte " * 1000)
    monkeypatch.setattr(trafilatura, "extract_metadata", lambda html: None)
    result = web_page.ReadWebPageTool().run("https://exemple.fr/article")
    assert len(result.text) < web_page.LLM_MAX_CHARS + 200
    assert result.display.kind == "article"

    monkeypatch.setattr(trafilatura, "fetch_url", lambda url: None)
    failed = web_page.ReadWebPageTool().run("https://exemple.fr/404")
    assert "Impossible" in failed.text and failed.display is None


def test_retry_recovers_from_a_passing_failure():
    from jarvis.tools.base import retry

    attempts = []

    def flaky():
        attempts.append(1)
        if len(attempts) == 1:
            raise TimeoutError("raté passager")
        return "ok"

    assert retry(flaky, delay=0) == "ok"
    assert len(attempts) == 2


class SlowTool(Tool):
    name = "slow"
    description = "ne répond jamais"
    parameters = {}

    def run(self):
        import time

        time.sleep(30)


def test_toolbox_gives_up_on_slow_tools_and_on_interruption():
    import time

    box = ToolBox([SlowTool()])
    start = time.monotonic()
    assert "pas répondu à temps" in box.run("slow", {}, timeout=0.3).text
    assert "Interrompu" in box.run("slow", {}, cancelled=lambda: True).text
    assert time.monotonic() - start < 2

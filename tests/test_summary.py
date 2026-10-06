from types import SimpleNamespace

from fakes import SETTINGS, FakeClient

from friday.brain import summary as summary_module
from friday.brain.conversation import Conversation
from friday.brain.llm import Brain
from friday.brain.summary import Summarizer, transcript


class SummaryClient:
    def __init__(self, text="Sujet : le Forex. Guide utile : https://a.fr/guide"):
        self.text, self.prompts = text, []

    def chat(self, **kwargs):
        self.prompts.append(kwargs["messages"][-1]["content"])
        return SimpleNamespace(message=SimpleNamespace(content=self.text))


def long_conversation(exchanges=5):
    conv = Conversation()
    for i in range(exchanges):
        conv.add("user", f"question {i}")
        conv.add("tool", f"résultat {i}", tool_name="web_search")
        conv.add("assistant", f"réponse {i}")
    return conv


def test_old_exchanges_are_folded_into_a_summary():
    conv = long_conversation()
    client = SummaryClient()
    summarizer = Summarizer(client, "m", 8192, background=False)
    summarizer.maybe_start(conv, prompt_tokens=1000)  # mémoire peu remplie : rien
    assert not client.prompts
    summarizer.maybe_start(conv, prompt_tokens=6000)
    assert conv.summary.startswith("Sujet : le Forex")
    assert [m["content"] for m in conv.messages if m["role"] == "user"] == [
        "question 3", "question 4"]  # fmt: skip
    assert "Utilisateur : question 0" in client.prompts[0]
    assert "[Résultat de web_search] résultat 1" in client.prompts[0]
    # second résumé : il reprend le premier
    for i in range(5, 7):
        conv.add("user", f"question {i}")
        conv.add("assistant", f"réponse {i}")
    summarizer.maybe_start(conv, prompt_tokens=6000)
    assert "Résumé plus ancien (à reprendre)" in client.prompts[1]


def test_failed_summary_keeps_the_conversation():
    class Broken:
        def chat(self, **kwargs):
            raise ConnectionError("Ollama absent")

    conv = long_conversation()
    Summarizer(Broken(), "m", 8192, background=False).maybe_start(conv, 6000)
    assert len(conv.messages) == 15 and conv.summary == ""


def test_transcript_is_short_and_labelled():
    text = transcript([{"role": "user", "content": "a" * 5000},
                       {"role": "assistant", "content": ""}])  # fmt: skip
    assert len(text) < summary_module.MESSAGE_CHARS + 20 and "Friday" not in text


def test_brain_puts_the_summary_in_its_instructions_and_starts_one_when_full():
    client = FakeClient(rounds=[["ok"], ["ok"]])
    brain = Brain(SETTINGS, client=client)
    brain.conversation = long_conversation()
    brain.conversation.summary = "On parlait du Forex."
    brain.summarizer = Summarizer(SummaryClient("Nouveau résumé."), "m", 8192,
                                  background=False)  # fmt: skip
    brain._prompt_tokens = 0
    list(brain.reply("Et la suite ?"))
    assert "On parlait du Forex." in client.calls[-1]["messages"][0]["content"]
    brain.summarizer.maybe_start(brain.conversation, 7000)
    assert brain.conversation.summary == "Nouveau résumé."
    brain.reset()
    assert brain.conversation.summary == ""

from datetime import datetime
from types import SimpleNamespace

from friday.app.briefing_trigger import morning_request
from friday.briefing import Briefing, BriefingConfig, Section, Sources
from friday.tools.briefing import ConfigureBriefingTool, MorningBriefingTool

MORNING = datetime(2026, 10, 5, 8, 30)


class FakeAgenda:
    def __init__(self, reminders=(), notes=None):
        self._reminders, self._notes = list(reminders), notes or {}

    def pending(self):
        return self._reminders

    def notes(self, key):
        return [SimpleNamespace(text=t) for t in self._notes.get(key, [])]


def make(tmp_path, sections=None, agenda=None, **sources):
    path = tmp_path / "briefing.json"
    BriefingConfig(sections=sections if sections is not None else
                   [Section("meteo"), Section("rappels")]).save(path)  # fmt: skip
    return Briefing(path, Sources(agenda=agenda, **sources))


def test_defaults_and_bad_file(tmp_path):
    assert [s.kind for s in BriefingConfig().sections] == ["meteo", "rappels"]
    bad = tmp_path / "b.json"
    bad.write_text("{abîmé", encoding="utf-8")
    assert BriefingConfig.load(bad).enabled


def test_empty_sections_stay_silent(tmp_path):
    reminder = SimpleNamespace(text="appeler le garage", due_at=MORNING.replace(hour=18))
    tomorrow = SimpleNamespace(text="dentiste", due_at=datetime(2026, 10, 6, 9))
    briefing = make(tmp_path, agenda=FakeAgenda([reminder, tomorrow]),
                    weather=lambda city: "Ensoleillé, 21 °C")  # fmt: skip
    facts = briefing.facts(MORNING)
    assert "Ensoleillé" in facts and "18:30 : appeler le garage" in facts
    assert "dentiste" not in facts  # demain : pas dans le briefing d'aujourd'hui

    nothing = make(tmp_path, agenda=FakeAgenda([tomorrow]))  # pas de météo, aucun rappel
    assert nothing.facts(MORNING) is None and nothing.request(MORNING) is None


def test_broken_source_does_not_spoil_the_briefing(tmp_path):
    def offline(city):
        raise ConnectionError("pas d'internet")

    briefing = make(tmp_path, [Section("meteo"), Section("libre", "une citation")],
                    weather=offline)  # fmt: skip
    facts = briefing.facts(MORNING)
    assert "citation" in facts and "Météo" not in facts


def test_lists_and_news(tmp_path):
    briefing = make(tmp_path, [Section("liste", "mes tâches"), Section("actualites", "tech")],
                    agenda=FakeAgenda(notes={"taches": ["payer EDF"]}),
                    news=lambda topic: [f"Titre {topic} {i}" for i in range(5)])  # fmt: skip
    facts = briefing.facts(MORNING)
    assert "payer EDF" in facts and "Titre tech 2" in facts and "Titre tech 3" not in facts


def test_automatic_briefing_once_a_day_in_the_morning_when_enabled(tmp_path):
    briefing = make(tmp_path, [Section("libre", "un conseil sport")])
    assert morning_request(briefing, MORNING.replace(hour=14)) is None  # l'après-midi
    request = morning_request(briefing, MORNING)
    assert "conseil sport" in request and "Message automatique" in request
    assert morning_request(briefing, MORNING.replace(hour=10)) is None  # déjà fait
    assert morning_request(briefing, datetime(2026, 10, 6, 7)) is not None  # lendemain

    briefing.set_enabled(False)
    assert morning_request(briefing, datetime(2026, 10, 7, 7)) is None


def test_nothing_to_say_is_marked_done_and_silent(tmp_path):
    briefing = make(tmp_path, [Section("rappels")], agenda=FakeAgenda())
    assert morning_request(briefing, MORNING) is None
    assert briefing.config.last_run == "2026-10-05"
    assert morning_request(None) is None


def test_configure_by_voice(tmp_path):
    briefing = make(tmp_path, [Section("meteo")])
    tool = ConfigureBriefingTool(briefing)
    assert "ajoutée : Actualité : tech" in tool.run("add", "actualités", "tech").text
    assert "déjà" in tool.run("add", "actualites", "Tech").text
    assert "Il manque" in tool.run("add", "liste").text
    assert "inconnu" in tool.run("add", "horoscope", "x").text
    assert "retirée : Météo du jour" in tool.run("remove", "météo").text
    assert "désactivé" in tool.run("disable").text and not briefing.config.enabled
    listing = tool.run("list")
    assert "Actualité : tech" in listing.text and listing.display.kind == "items"
    assert "activé" in tool.run("enable").text and briefing.config.enabled


def test_briefing_on_demand(tmp_path):
    briefing = make(tmp_path, [Section("rappels")], agenda=FakeAgenda())
    assert "vide" in MorningBriefingTool(briefing).run().text
    assert briefing.config.last_run is not None  # plus de briefing automatique aujourd'hui


def test_weather_needs_a_city_and_never_invents(tmp_path):
    def weather(city):
        return f"Météo à {city} : 18 °C" if city else None  # comme la vraie source

    briefing = make(tmp_path, [Section("meteo")], weather=weather)
    assert briefing.facts(MORNING) is None  # pas de ville : silence (pas d'invention)
    tool = ConfigureBriefingTool(briefing)
    assert "ville à préciser" in tool.run("list").text
    assert "mise à jour : Météo du jour (Lyon)" in tool.run("add", "meteo", "Lyon").text
    assert len(briefing.config.sections) == 1
    assert "Météo à Lyon" in briefing.facts(MORNING)
    assert "ville à préciser" not in tool.run("list").text

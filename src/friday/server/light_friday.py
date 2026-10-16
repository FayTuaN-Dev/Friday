"""Le Friday léger (R2a) : peu d'outils, toujours les mêmes (brain/light.py), et la mémoire.
Météo, recherche web, notes, rappels, souvenirs. Agenda et mails Google : R2b."""

import logging
from dataclasses import dataclass

import ollama

from friday.brain.llm import Brain
from friday.core.config import DATA_DIR, Settings
from friday.memory.service import format_memories

log = logging.getLogger(__name__)

GUIDES = """- get_weather : la météo (maintenant, demain, la semaine). Jamais de mémoire. Ville non
  dite, « chez moi », « ici » : laisse city VIDE (c'est la ville de l'utilisateur).
- web_search : chercher sur internet (actualité, prix, horaires, faits récents, ou au moindre
  doute). Ne réponds jamais de mémoire à une question d'actualité.
- add_note, list_notes : noter quelque chose, relire les notes.
- set_reminder, list_reminders, cancel_reminder : les rappels (« rappelle-moi de… à 18 h »).
- remember : retenir une information sur l'utilisateur (« replaces » = numéro du souvenir
  dépassé s'il corrige) ; forget_memory : oublier ; list_memories : ce que tu sais de lui."""


@dataclass
class LightFriday:
    brain: Brain
    memory: object | None


def build_light(settings: Settings) -> LightFriday:
    from friday.agenda.store import AgendaStore
    from friday.app.components import load_memory
    from friday.tools import ToolBox
    from friday.tools.notes import AddNoteTool, ListNotesTool
    from friday.tools.reminders import CancelReminderTool, ListRemindersTool, SetReminderTool
    from friday.tools.weather import WeatherTool
    from friday.tools.web_search import WebSearchTool

    DATA_DIR.mkdir(exist_ok=True)
    client = ollama.Client(host=settings.ollama_host)
    agenda = AgendaStore(DATA_DIR / "agenda.db")
    tools = [WeatherTool(settings.home_city),
             WebSearchTool(settings.search_region, backend=settings.search_backend),
             AddNoteTool(agenda), ListNotesTool(agenda), SetReminderTool(agenda),
             ListRemindersTool(agenda), CancelReminderTool(agenda)]  # fmt: skip
    memory = load_memory(settings, client)
    if memory is not None:
        from friday.tools.memory import ForgetTool, ListMemoriesTool, RememberTool

        tools += [RememberTool(memory), ForgetTool(memory), ListMemoriesTool(memory)]
    toolbox = ToolBox(tools)  # aucun ne demande de « oui » (R2b : confirmer à distance)
    recall = (lambda q: format_memories(memory.relevant(q))) if memory else None
    brain = Brain(settings, client=client, toolbox=toolbox, recall=recall, light_guides=GUIDES)
    log.info("Friday léger prêt : %d outils, mémoire %s", len(tools),
             "oui" if memory else "non")  # fmt: skip
    return LightFriday(brain, memory)

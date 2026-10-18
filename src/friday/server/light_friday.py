"""Le Friday léger (R2a) : peu d'outils, toujours les mêmes (brain/light.py), et la mémoire.
Météo, recherche web, notes, rappels, souvenirs ; le PC (R4 : l'allumer, l'éteindre) et sa
carte graphique pour penser quand il est allumé (R5, pc_link.py). Agenda et mails : R2b."""

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
PC_GUIDES = """
- wake_pc : allumer le PC de la maison ; pc_state : est-il allumé ? ; shutdown_pc : l'éteindre
  (l'utilisateur confirme sur son téléphone). L'état du PC change : appelle TOUJOURS l'outil,
  ne réponds jamais d'après une réponse précédente."""


@dataclass
class LightFriday:
    brain: Brain
    memory: object | None
    pc: object | None = None  # PcLink : le PC de la maison (R4, R5), s'il est réglé


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
    pc, guides = _pc_link(), GUIDES
    if pc is not None:
        from friday.server.pc_tools import PcStateTool, ShutdownPcTool, WakePcTool

        tools += [WakePcTool(pc), PcStateTool(pc), ShutdownPcTool(pc)]
        guides += PC_GUIDES
    toolbox = ToolBox(tools)  # « oui » éventuels : confirmés sur le téléphone (http_api.py)
    recall = (lambda q: format_memories(memory.relevant(q))) if memory else None
    brain = Brain(settings, client=client, toolbox=toolbox, recall=recall, light_guides=guides)
    log.info("Friday léger prêt : %d outils, mémoire %s", len(tools),
             "oui" if memory else "non")  # fmt: skip
    return LightFriday(brain, memory, pc)


def _pc_link():
    from friday.server.pc_link import PcLink, load_pc_settings
    from friday.server.settings import load_server_settings

    pc = load_pc_settings()
    return PcLink(pc, load_server_settings().token) if pc is not None else None

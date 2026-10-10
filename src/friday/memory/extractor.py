"""Mémorisation automatique : le LLM relit un échange et en tire les faits durables sur
l'utilisateur."""

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime

import ollama

from friday.brain.prompts import french_date
from friday.memory.categories import CATEGORIES, HINTS, OTHER, checked
from friday.memory.service import format_memories
from friday.memory.store import Memory

log = logging.getLogger(__name__)

PROMPT = """Tu es le module mémoire d'un assistant personnel. Lis la phrase de l'utilisateur et
retiens UNIQUEMENT les informations durables et personnelles qu'il donne sur lui-même :
identité, famille, proches, animaux, travail, études, lieu de vie, goûts, habitudes, santé,
allergies, projets, objectifs, ou préférences sur la façon dont l'assistant doit lui répondre.

Ne retiens PAS :
- les questions, demandes ponctuelles ou sujets de recherche (« quel temps fait-il », « parle-moi
  de Napoléon ») ;
- les ordres donnés à l'assistant et leur suivi (« supprime le numéro 1 », « ajoute un
  rendez-vous jeudi », « ouvre Spotify », « tu as réussi à le supprimer ? ») : ce sont des
  actions, pas des faits sur l'utilisateur ;
- les informations générales qui ne concernent pas l'utilisateur ;
- ce que dit l'assistant ;
- ce qui est déjà dans les souvenirs existants (même formulé autrement).

Chaque fait : une phrase courte à la 3e personne, qui commence par « L'utilisateur » (ou par
la personne concernée, ex. « La sœur de l'utilisateur, Clara, … »). Garde les prénoms
et garde les expressions de temps telles quelles (« samedi », « le mois dernier »).
Si un fait corrige ou remplace un souvenir existant (déménagement, changement de travail…),
mets le numéro de ce souvenir dans « replaces », sinon null.
« category » : le thème du fait, parmi : {categories} ({hints}).
S'il n'y a rien à retenir, renvoie une liste vide : c'est le cas le plus fréquent.

Souvenirs existants :
{memories}

Ce que l'assistant venait de dire (seulement pour comprendre la phrase, ne rien en retenir) :
« {context} »
Si la phrase répond à une question de l'assistant, comprends-la dans ce contexte : « le nom
c'est Rollercoin » en réponse à « quels mails ? » parle de mails, pas du nom de l'utilisateur.

Phrase de l'utilisateur :
« {user_text} »"""

SCHEMA = {
    "type": "object",
    "properties": {
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "replaces": {"type": ["integer", "null"]},
                    "category": {"type": "string", "enum": list(CATEGORIES)},
                },
                "required": ["text", "replaces", "category"],
            },
        }
    },
    "required": ["facts"],
}

RELATIVE_TIME = re.compile(
    r"\b(aujourd'hui|demain|hier|ce soir|ce matin|en ce moment|actuellement|bientôt|"
    r"lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche|"
    r"(la semaine|le mois|l'année|l'an) (dernier|dernière|prochain|prochaine)|"
    r"dans \w+ (jours?|semaines?|mois|ans?)|il y a \w+ (jours?|semaines?|mois|ans?))\b",
    re.IGNORECASE,
)

MIN_WORDS = 3  # « oui », « merci », « stop » : rien à retenir


@dataclass
class Fact:
    text: str
    replaces: int | None = None
    category: str = OTHER


class FactExtractor:
    def __init__(self, client: ollama.Client, model: str, num_ctx: int) -> None:
        self.client = client
        self.model = model
        self.num_ctx = num_ctx

    def extract(self, user_text: str, known: list[Memory], context: str = "") -> list[Fact]:
        answers_a_question = context.strip().endswith(
            "?"
        )  # « Bordeaux » après « où habitez-vous ? »
        if len(user_text.split()) < MIN_WORDS and not answers_a_question:
            return []
        prompt = PROMPT.format(
            memories=format_memories(known) or "(aucun)",
            categories=", ".join(CATEGORIES),
            hints=HINTS,
            user_text=user_text.strip(),
            context=(context or "(rien)").strip()[-600:],
        )
        response = self.client.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            format=SCHEMA,  # sortie JSON garantie conforme
            think=False,
            keep_alive="30m",
            options={"num_ctx": self.num_ctx, "temperature": 0},
        )
        try:
            facts = json.loads(response.message.content)["facts"]
        except (json.JSONDecodeError, KeyError, TypeError):
            log.warning("Réponse de mémorisation illisible : %r", response.message.content)
            return []
        known_ids = {m.id for m in known}
        return [
            Fact(
                date_relative_terms(f["text"].strip(), datetime.now()),
                f.get("replaces") if f.get("replaces") in known_ids else None,
                checked(f.get("category")),
            )
            for f in facts
            if f.get("text", "").strip()
        ]


CLASSIFY = """Range chaque souvenir dans UN thème parmi : {categories} ({hints}).
{memories}"""


def categorize(client: ollama.Client, model: str, memories: list[Memory]) -> dict[int, str]:
    """Le thème des souvenirs d'avant la mémoire vivante (une seule fois, en arrière-plan)."""
    if not memories:
        return {}
    schema = {"type": "object", "properties": {"themes": {"type": "array", "items": {
        "type": "object", "properties": {"id": {"type": "integer"},
                                         "category": {"type": "string", "enum": list(CATEGORIES)}},
        "required": ["id", "category"]}}}, "required": ["themes"]}  # fmt: skip
    prompt = CLASSIFY.format(categories=", ".join(CATEGORIES), hints=HINTS,
                             memories=format_memories(memories))  # fmt: skip
    response = client.chat(model=model, messages=[{"role": "user", "content": prompt}],
                           format=schema, think=False, options={"temperature": 0})  # fmt: skip
    try:
        themes = json.loads(response.message.content)["themes"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return {}
    ids = {m.id for m in memories}
    return {t["id"]: checked(t.get("category")) for t in themes if t.get("id") in ids}


def date_relative_terms(text: str, today: datetime) -> str:
    """« … samedi » n'aura plus de sens dans un mois : on note quand ça a été dit.
    (Le LLM se trompe trop souvent en convertissant lui-même les dates.)"""
    if RELATIVE_TIME.search(text):
        return f"{text.rstrip('.')} (noté le {french_date(today)})."
    return text

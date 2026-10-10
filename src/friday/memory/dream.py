"""Le rêve nocturne (J2) : Friday relit les échanges d'une journée ENTIERS (mémoire de la
journée, F5) pour retrouver les faits que la mémorisation au fil de l'eau a manqués (une
réponse étalée sur plusieurs phrases…), puis prépare un rapport de ménage : souvenirs
contradictoires ou en double, faits jamais reconfirmés, erreurs répétées du journal.
Les faits manqués sont retenus ; le ménage est seulement PROPOSÉ, jamais appliqué seul."""

import json
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from friday.memory.categories import CATEGORIES, HINTS, checked
from friday.memory.extractor import Fact, date_relative_terms
from friday.memory.service import format_memories
from friday.memory.store import Memory

log = logging.getLogger(__name__)

CHUNK = 30  # phrases relues par appel au modèle
STALE_DAYS = 180  # un fait déduit, jamais redit depuis 6 mois : à reconfirmer
REPEATED = 3  # une même erreur au moins 3 fois dans le journal

FACTS_PROMPT = """Tu es le module mémoire d'un assistant personnel. Voici des phrases dites par
l'utilisateur {day} (numérotées ; entre crochets, ce que l'assistant venait de dire).
Relis-les ENSEMBLE et retrouve les informations durables et personnelles qu'il a données sur
lui-même (identité, proches, animaux, travail, lieu de vie, goûts, habitudes, santé, projets,
façon de lui parler, argent et trading) qui ne sont PAS déjà dans les souvenirs existants, même
formulées autrement. Une information peut être répartie sur plusieurs phrases (l'assistant
pose une question, l'utilisateur répond).
Ne retiens PAS les questions, les demandes ponctuelles, les ordres donnés à l'assistant, les
informations générales, ni ce que dit l'assistant.
Chaque fait : une phrase courte à la 3e personne qui commence par « L'utilisateur » ; « line »
= le numéro de la phrase d'où il vient ; « replaces » = le numéro du souvenir qu'il corrige,
sinon null ; « category » parmi : {categories} ({hints}).
S'il n'y a rien de nouveau, renvoie une liste vide.

Souvenirs existants :
{memories}

Phrases de l'utilisateur :
{lines}"""

PAIRS_PROMPT = """Voici ce qu'un assistant sait de l'utilisateur, un souvenir par ligne.
Trouve les paires qui se CONTREDISENT (les deux ne peuvent pas être vraies en même temps :
deux villes où il habite, deux métiers actuels, deux prénoms) ou qui disent EXACTEMENT la même
chose (doublon). Ne signale PAS deux faits simplement liés ou complémentaires.
S'il n'y en a aucune, renvoie une liste vide.

{memories}"""

FACTS_SCHEMA = {"type": "object", "required": ["facts"], "properties": {"facts": {
    "type": "array", "items": {"type": "object", "required": ["text", "line", "replaces",
                                                              "category"],
    "properties": {"text": {"type": "string"}, "line": {"type": "integer"},
                   "replaces": {"type": ["integer", "null"]},
                   "category": {"type": "string", "enum": list(CATEGORIES)}}}}}}  # fmt: skip
YOU_PROMPT = """Réécris chaque phrase en t'adressant directement à l'utilisateur (tutoiement),
sans rien changer d'autre, sans majuscule au début ni point à la fin. Exemples : « L'utilisateur
aime le jazz. » → « tu aimes le jazz » ; « La sœur de l'utilisateur s'appelle Clara. » →
« ta sœur s'appelle Clara ». Autant de phrases, dans le même ordre.

{lines}"""
YOU_SCHEMA = {"type": "object", "required": ["phrases"], "properties": {
    "phrases": {"type": "array", "items": {"type": "string"}}}}  # fmt: skip
PAIRS_SCHEMA = {"type": "object", "required": ["pairs"], "properties": {"pairs": {
    "type": "array", "items": {"type": "object", "required": ["a", "b", "kind"],
    "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}, "kind": {
        "type": "string", "enum": ["contradiction", "doublon"]}}}}}}  # fmt: skip


@dataclass
class Pair:
    first: Memory
    second: Memory
    kind: str  # « contradiction » ou « doublon »


@dataclass
class Report:
    day: str  # AAAA-MM-JJ : la journée relue
    exchanges: int = 0
    added: list[str] = field(default_factory=list)  # faits retrouvés et retenus
    pairs: list[Pair] = field(default_factory=list)  # à vérifier par l'utilisateur
    stale: list[Memory] = field(default_factory=list)  # à reconfirmer
    errors: list[tuple[str, int]] = field(default_factory=list)  # (message, nombre)
    you: dict[str, str] = field(default_factory=dict)  # fait → « tu … » (pour le dire)

    @property
    def to_check(self) -> int:
        return len(self.pairs) + len(self.stale) + len(self.errors)


class Dreamer:
    def __init__(self, client, model: str, num_ctx: int) -> None:
        self.client, self.model, self.num_ctx = client, model, num_ctx

    def _ask(self, prompt: str, schema: dict, key: str) -> list[dict]:
        response = self.client.chat(
            model=self.model, messages=[{"role": "user", "content": prompt}], format=schema,
            think=True, options={"num_ctx": self.num_ctx, "temperature": 0})  # fmt: skip
        try:
            return list(json.loads(response.message.content)[key])
        except (json.JSONDecodeError, KeyError, TypeError):
            log.warning("Rêve : réponse illisible : %r", response.message.content[:200])
            return []

    def missed_facts(self, exchanges, known: list[Memory], day_name: str) -> list[tuple[Fact, str]]:
        """(fait, phrase d'où il vient) pour les faits absents de la mémoire."""
        found, ids = [], {m.id for m in known}
        for start in range(0, len(exchanges), CHUNK):
            chunk = exchanges[start : start + CHUNK]
            lines = []
            for n, (_, said, _) in enumerate(chunk, 1):
                before = exchanges[start + n - 2][2][:120] if start + n >= 2 else ""
                lines.append(f"{n}. " + (f"[« {before} »] " if before else "") + said)
            prompt = FACTS_PROMPT.format(
                day=day_name, categories=", ".join(CATEGORIES), hints=HINTS,
                memories=format_memories(known) or "(aucun)", lines="\n".join(lines))  # fmt: skip
            for item in self._ask(prompt, FACTS_SCHEMA, "facts"):
                text, line = (item.get("text") or "").strip(), item.get("line")
                if not text or not isinstance(line, int) or not 1 <= line <= len(chunk):
                    continue
                when = chunk[line - 1][0]
                fact = Fact(date_relative_terms(text, when),
                            item.get("replaces") if item.get("replaces") in ids else None,
                            checked(item.get("category")))  # fmt: skip
                found.append((fact, chunk[line - 1][1]))
        return found

    def to_you(self, texts: list[str]) -> dict[str, str]:
        """Chaque fait au tutoiement, pour que le CODE construise la phrase du rapport."""
        texts = list(dict.fromkeys(texts))
        if not texts:
            return {}
        lines = "\n".join(f"{n}. {text}" for n, text in enumerate(texts, 1))
        found = self._ask(YOU_PROMPT.format(lines=lines), YOU_SCHEMA, "phrases")
        if len(found) != len(texts):
            return {}
        return {text: re.sub(r"^\d+\.\s*", "", str(you)).strip().rstrip(".")
                for text, you in zip(texts, found, strict=True)}  # fmt: skip

    def pairs(self, memories: list[Memory]) -> list[Pair]:
        if len(memories) < 2:
            return []
        by_id, seen, found = {m.id: m for m in memories}, set(), []
        prompt = PAIRS_PROMPT.format(memories=format_memories(memories))
        for item in self._ask(prompt, PAIRS_SCHEMA, "pairs"):
            a, b = item.get("a"), item.get("b")
            key = frozenset((a, b))
            if a in by_id and b in by_id and a != b and key not in seen:
                seen.add(key)
                found.append(Pair(by_id[a], by_id[b], item.get("kind", "contradiction")))
        return found


def stale(memories: list[Memory], now: datetime) -> list[Memory]:
    """Déduits, jamais redits, notés il y a plus de 6 mois : peut-être plus vrais."""
    limit = (now - timedelta(days=STALE_DAYS)).isoformat()
    return [m for m in memories if m.source == "auto" and m.confirmations <= 1
            and m.created_at and m.created_at < limit]  # fmt: skip


def repeated_errors(log_file: Path, tail: int = 5000) -> list[tuple[str, int]]:
    """Les avertissements et erreurs qui reviennent (chiffres ignorés), les plus fréquents."""
    try:
        lines = log_file.read_text("utf-8", errors="replace").splitlines()[-tail:]
    except OSError:
        return []
    counts: Counter = Counter()
    for line in lines:
        if found := re.match(r"\d\d:\d\d:\d\d \[(?:WARNING|ERROR)\] [\w.]+: (.+)", line):
            counts[re.sub(r"\d+", "#", found.group(1))[:140]] += 1
    return [(text, n) for text, n in counts.most_common(3) if n >= REPEATED]

"""Briefing du matin : rubriques choisies par l'utilisateur, dites une fois par jour."""

from friday.briefing.briefing import Briefing
from friday.briefing.config import BriefingConfig, Section
from friday.briefing.sections import Sources

__all__ = ["Briefing", "BriefingConfig", "Section", "Sources"]

"""Les thèmes des souvenirs : une liste FERMÉE (le modèle choisit, il n'invente pas), pour
ranger la fiche lisible (data/memoire.md) et la fenêtre « Ce que je sais sur vous »."""

CATEGORIES = (
    "identité", "famille et proches", "lieu de vie", "travail et études", "santé",
    "goûts et loisirs", "habitudes", "projets et objectifs", "argent et trading",
    "façon de lui parler", "autre",
)  # fmt: skip
OTHER = "autre"
HINTS = (
    "comment l'appeler (surnom, vouvoiement), comment lui répondre (longueur, ton) → « façon "
    "de lui parler » ; prénom, âge, nationalité → « identité » ; proches et animaux → "
    "« famille et proches » ; budget, placements, trading → « argent et trading »"
)


def checked(category: str | None) -> str:
    """Une catégorie connue, sinon « autre »."""
    category = (category or "").strip().lower()
    return category if category in CATEGORIES else OTHER

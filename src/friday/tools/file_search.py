"""Outils : chercher un fichier (Documents, Bureau, Téléchargements, Images, Musique) et
l'ouvrir."""

from pathlib import Path

from friday.files.content_search import search_contents
from friday.files.opener import CannotOpen, human_size, open_file, reveal_file, short_date
from friday.files.readers import clean_path
from friday.files.search import KINDS, FileEntry, FileFinder, split_kind
from friday.tools.base import Display, Tool, ToolResult

SHOWN = 8  # résultats donnés au LLM (le pop-up en montre davantage)


def location(entry: FileEntry, folders: dict[str, Path]) -> str:
    """« Documents › Factures › 2026 »"""
    root = folders.get(entry.folder)
    parts = entry.path.parent.relative_to(root).parts if root else ()
    return " › ".join([entry.folder, *parts])


class SearchFilesTool(Tool):
    name = "search_files"
    description = (
        "Cherche des fichiers de l'utilisateur par leur nom, dans Documents, Bureau, "
        "Téléchargements, Images et Musique (« trouve mon devis de mars », « où est ma photo de "
        "vacances ? », « mes derniers PDF »). Ensuite : read_file pour le lire, open_file "
        "pour l'ouvrir."
    )
    parameters = {
        "query": {
            "type": "string",
            "description": "Mots du nom du fichier, et éventuellement un mois ou une année "
            "(« devis mars »). Vide pour les plus récents.",
        },
        "kind": {
            "type": "string",
            "enum": sorted(KINDS),
            "description": "Type de fichier, SEULEMENT si l'utilisateur le dit (« mes PDF », "
            "« la photo »). Sinon, ne rien mettre.",
        },
        "in_content": {
            "type": "boolean",
            "description": "Chercher aussi les mots DANS les documents (plus lent) : si rien "
            "n'est trouvé par le nom, ou si l'utilisateur parle du contenu",
        },
    }

    def __init__(self, finder: FileFinder) -> None:
        self.finder = finder
        self.timeout = 25  # la recherche dans le contenu peut prendre ~10 s

    def label(self, args: dict) -> str:
        where = " (contenu)" if args.get("in_content") else ""
        return (
            f"🗂️ Recherche de fichiers : {args.get('query') or args.get('kind') or 'récents'}{where}"
        )

    def run(self, query: str = "", kind: str | None = None, in_content: bool = False) -> ToolResult:
        words, kind = split_kind(query, kind)  # « PDF », « photo » : un type, pas un mot
        hits, partial = self.finder.find(words, kind, limit=20), False
        if not hits and kind and words:  # le type était peut-être une supposition du modèle
            hits = self.finder.find(words, None, limit=20)
        if in_content and words:
            extensions = KINDS.get(kind or "")
            pool = [e for e in self.finder.entries()
                    if not extensions or e.path.suffix.lower() in extensions]  # fmt: skip
            more, partial = search_contents(pool, words, limit=10)
            hits += [e for e in more if e not in hits]
        if not hits:
            hint = "" if in_content else " Propose de chercher aussi dans le contenu des documents."
            return ToolResult(
                f"Aucun fichier trouvé pour « {query} » dans "
                f"{', '.join(self.finder.folders)}.{hint}"
            )
        folders = self.finder.folders
        lines = [
            f"[{i}] {e.path.name} — {location(e, folders)} — modifié le {short_date(e.modified)}"
            f" — {human_size(e.size)}\n    chemin : {e.path}"
            for i, e in enumerate(hits[:SHOWN], 1)
        ]
        note = "\n(Recherche dans le contenu interrompue : trop de documents.)" if partial else ""
        items = [
            {"path": str(e.path), "name": e.path.name, "where": location(e, folders),
             "meta": f"{short_date(e.modified)} · {human_size(e.size)}"}
            for e in hits
        ]  # fmt: skip
        return ToolResult(
            f"{len(hits)} fichier(s) trouvé(s), affichés à l'écran (le meilleur en premier) :\n"
            + "\n".join(lines)
            + note
            + "\nÀ l'oral, sois brève : dis combien de fichiers tu as trouvés et cite seulement "
            "le ou les deux premiers (nom et dossier) ; la liste complète est déjà à l'écran. "
            "Pas de liste, pas de chemins, pas de Markdown. L'utilisateur peut dire « ouvre le "
            "numéro 3 » : ce sont les numéros ci-dessus.",
            Display("files", f"Fichiers : {query or kind or 'récents'}", {"files": items}),
        )


class OpenFileTool(Tool):
    name = "open_file"
    description = (
        "Ouvre un fichier avec son application habituelle (PDF, image, Word…), ou montre-le "
        "dans son dossier (reveal=true). Le chemin vient de search_files ou d'un fichier joint."
    )
    parameters = {
        "path": {"type": "string", "description": "Chemin complet du fichier"},
        "reveal": {"type": "boolean", "description": "Ouvrir le dossier au lieu du fichier"},
    }
    required = ("path",)

    def __init__(self, finder: FileFinder | None = None) -> None:
        """`finder` : pour retrouver un fichier dont le chemin donné n'existe pas."""
        self.finder = finder

    def label(self, args: dict) -> str:
        verb = "Dossier de" if args.get("reveal") else "Ouverture :"
        return f"📂 {verb} {clean_path(args.get('path', '')).name}"

    def run(self, path: str, reveal: bool = False) -> ToolResult:
        target = clean_path(path)
        if not target.exists() and self.finder is not None:
            # Constaté : « lance panda.png dans le dossier Download » → « /Download/panda.png »
            # inventé par qwen, au lieu de chercher d'abord
            same = [e for e in self.finder.find(target.stem, limit=20)
                    if e.path.name.lower() == target.name.lower()]  # fmt: skip
            if len(same) > 1:
                places = "\n".join(f"- {e.path}" for e in same[:SHOWN])
                return ToolResult(f"Plusieurs fichiers « {target.name} » :\n{places}\nDemande "
                                  "lequel ouvrir (dis seulement les dossiers).")  # fmt: skip
            if same:
                target = same[0].path
        try:
            (reveal_file if reveal else open_file)(target)
        except CannotOpen as error:
            return ToolResult(f"{error} Préviens l'utilisateur.")
        return ToolResult(f"{'Dossier ouvert' if reveal else 'Fichier ouvert'} : {target.name}.")

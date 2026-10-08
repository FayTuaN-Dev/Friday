"""Diagnostic (Réglages → Diagnostic) : l'état de ce dont Friday dépend, en un coup d'œil —
Ollama et ses modèles, la carte graphique, la voix et le micro, la dernière sauvegarde. Chaque
ligne : (rubrique, état, détail) ; état ✅ / ⚠️ / ❌."""

import subprocess
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from friday.app.backup import last_backup
from friday.app.gpu_check import gpu_share

OK, WARN, BAD = "✅", "⚠️", "❌"
Line = tuple[str, str, str]


def _ollama(client, settings) -> list[Line]:
    try:
        installed = {m.model for m in client.list().models}
    except Exception as error:
        return [("Ollama", BAD, f"injoignable ({type(error).__name__}) : lancez Ollama")]
    lines = [("Ollama", OK, f"joignable, {len(installed)} modèle(s) installé(s)")]
    for role, name in (("Modèle de conversation", settings.ollama_model),
                       ("Modèle de la mémoire", settings.embed_model)):  # fmt: skip
        found = any(m == name or m.split(":")[0] == name.split(":")[0] for m in installed)
        lines.append((role, OK if found else BAD,
                      name + ("" if found else f" absent : « ollama pull {name} »")))  # fmt: skip
    share = gpu_share(client, settings.ollama_model)
    if share is None:
        lines.append(("Chargement", WARN, "modèle pas encore chargé (il le sera à la 1re demande)"))
    else:
        lines.append(("Chargement", OK if share >= 0.99 else WARN,
                      f"{share:.0%} du modèle dans la carte graphique"
                      + ("" if share >= 0.99 else " : Friday sera lente")))  # fmt: skip
    return lines


def _speed(watch) -> list[Line]:
    if watch is None or watch.normal is None:
        return [("Vitesse", WARN, "pas encore mesurée (après la première réponse)")]
    last = watch.last or watch.normal
    slow = last < watch.normal * 0.35
    text = f"dernière réponse {last:.0f} jetons/s (normale : {watch.normal:.0f})"
    if watch.reloads:
        text += f" ; modèle rechargé {len(watch.reloads)} fois depuis le démarrage"
    return [("Vitesse", WARN if slow else OK, text)]


def gpu(run: Callable = subprocess.run) -> list[Line]:
    query = "name,memory.used,memory.total,temperature.gpu"
    try:
        out = run(["nvidia-smi", f"--query-gpu={query}", "--format=csv,noheader,nounits"],
                  capture_output=True, text=True, timeout=5).stdout.strip()  # fmt: skip
        name, used, total, temp = [x.strip() for x in out.splitlines()[0].split(",")]
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return [("Carte graphique", WARN, "nvidia-smi indisponible")]
    used, total, temp = int(used), int(total), int(temp)
    state = OK if used < 0.95 * total and temp < 85 else WARN
    return [("Carte graphique", state, f"{name} : {used} / {total} Mo utilisés, {temp} °C")]


def _voice(components, settings) -> list[Line]:
    speaker, recorder = getattr(components, "speaker", None), getattr(components, "recorder", None)
    return [
        ("Voix", OK if speaker else WARN, settings.tts_voice if speaker else "désactivée"),
        ("Micro et écoute", OK if recorder and getattr(components, "stt", None) else WARN,
         f"{settings.mic_device or 'micro par défaut'}, Whisper {settings.stt_model}"
         if recorder else "écoute désactivée : clavier seulement"),
    ]  # fmt: skip


def _backup(data_dir: Path, copy_to: str) -> list[Line]:
    last = last_backup(data_dir)
    if last is None:
        return [("Sauvegarde", WARN, "aucune pour l'instant (la première se fait au démarrage)")]
    when = datetime.fromtimestamp(last.stat().st_mtime)
    age = (datetime.now() - when).total_seconds() / 3600
    where = (
        f" ; copie dans {copy_to}" if copy_to else " ; pas de copie ailleurs (Réglages → Fonctions)"
    )
    return [("Sauvegarde", OK if age < 48 else WARN,
             f"{when:%d/%m à %H:%M}, {last.stat().st_size // 1024} Ko{where}")]  # fmt: skip


def collect(components, settings, data_dir: Path, run: Callable = subprocess.run) -> list[Line]:
    brain = getattr(components, "brain", None)
    client = getattr(brain, "client", None)
    lines = _ollama(client, settings) if client is not None else [
        ("Ollama", WARN, "Friday démarre encore")]  # fmt: skip
    lines += _speed(getattr(brain, "speed", None))
    lines += gpu(run)
    lines += _voice(components, settings)
    lines += _backup(data_dir, settings.backup_dir)
    return lines

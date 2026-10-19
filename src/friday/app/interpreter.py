"""Interprète (D2) : « Friday, traduis la vidéo ». Le son du PC est découpé en phrases (même
détection de parole que les mains libres), Whisper les écrit, qwen les traduit de l'anglais
vers le français, et elles s'affichent en sous-titres par-dessus l'écran. Tout sur le PC.

Sous-titres plutôt que voix : la voix de Friday couvrirait la vidéo, et le son du PC la
réentendrait.
"""

import logging
import queue
import re
import threading
from collections.abc import Callable

import numpy as np

from friday.voice.wake import normalize

log = logging.getLogger(__name__)

# « traduis la vidéo », « traduis ce que j'entends » ; pas « traduis son mail en anglais »
ON = re.compile(r"\b(tradui\w*|sous titre\w*)\b.*\b(videos?|films?|youtube|series?|entends|"
                r"son du pc|le son|en direct)\b|\bmode interprete\b")  # fmt: skip
OFF = re.compile(r"\b(arrete|stop|stoppe|coupe|fin|termine|desactive)\b.*\b(tradu|interpret"
                 r"|sous titre)")  # fmt: skip
BACKLOG = 3  # phrases en attente au-delà : on saute les plus anciennes pour rester en direct
SEGMENT_MS = 8000  # une phrase de sous-titre : 8 s au plus, même sans pause dans la vidéo

INSTRUCTIONS = (
    "Tu traduis en direct les sous-titres d'une vidéo, de l'anglais vers le français. Réponds "
    "uniquement par la traduction de la dernière phrase : naturelle, fidèle, sans guillemets, "
    "sans commentaire. La phrase précédente n'est là que pour le contexte."
)


def command(text: str) -> str | None:
    """« traduis la vidéo » → "on", « arrête de traduire » → "off", sinon None."""
    plain = normalize(text)
    if OFF.search(plain):
        return "off"
    return "on" if ON.search(plain) else None


class Translator:
    def __init__(self, client, model: str, num_ctx: int) -> None:
        self.client, self.model, self.num_ctx = client, model, num_ctx  # même num_ctx : pas
        self.previous = ""  # de rechargement du modèle

    def __call__(self, text: str) -> str:
        context = f"Phrase précédente : {self.previous}\n" if self.previous else ""
        response = self.client.chat(
            model=self.model,
            messages=[{"role": "system", "content": INSTRUCTIONS},
                      {"role": "user", "content": f"{context}Dernière phrase : {text}"}],
            think=False, keep_alive="30m",
            options={"num_ctx": self.num_ctx, "num_predict": 200, "temperature": 0.2},
        )  # fmt: skip
        self.previous = text
        return (response.message.content or "").strip().strip('«»"').strip()


class Interpreter:
    def __init__(self, transcribe: Callable[[np.ndarray], tuple[str, str]],
                 translate: Callable[[str], str], show: Callable[[str, str], None],
                 make_capture: Callable, make_segmenter: Callable) -> None:  # fmt: skip
        self.transcribe, self.translate, self.show = transcribe, translate, show
        self._make_capture, self._make_segmenter = make_capture, make_segmenter
        self._phrases: queue.Queue = queue.Queue()
        self._capture = None
        self.on = False

    def start(self) -> None:
        if self.on:
            return
        self.on = True
        self._phrases = queue.Queue()
        segmenter = self._make_segmenter(self._phrases.put)
        self._capture = self._make_capture(segmenter.feed)
        self._capture.start()
        threading.Thread(target=self._work, args=(self._phrases,), daemon=True,
                         name="interprete").start()  # fmt: skip
        log.info("Interprète activé")

    def stop(self) -> None:
        if not self.on:
            return
        self.on = False
        self._capture.stop()
        self._phrases.put(None)  # le fil de traduction s'arrête
        log.info("Interprète désactivé")

    def _work(self, phrases: queue.Queue) -> None:
        while (segment := phrases.get()) is not None:
            while phrases.qsize() > BACKLOG:  # en retard : on saute pour rester en direct
                if (segment := phrases.get()) is None:
                    return
            try:
                text, language = self.transcribe(segment)
                if not text or not self.on:
                    continue
                self.show(text if language == "fr" else self.translate(text), text)
            except Exception:
                log.exception("Phrase de l'interprète perdue")

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
import time
from collections.abc import Callable

import numpy as np

from friday.voice.wake import normalize

log = logging.getLogger(__name__)

# « traduis la vidéo », « traduis ce que j'entends » ; pas « traduis son mail en anglais »
ON = re.compile(r"\b(tradui\w*|sous titre\w*)\b.*\b(videos?|films?|youtube|series?|entends|"
                r"son du pc|le son|en direct)\b|\bmode interprete\b")  # fmt: skip
OFF = re.compile(r"\b(arrete|stop|stoppe|coupe|fin|termine|desactive)\b.*\b(tradu|interpret"
                 r"|sous titre)")  # fmt: skip
BACKLOG = 2  # phrases en attente au-delà : on saute les plus anciennes pour rester en direct
# Découpage du son : constaté, les anglophones rapides ne marquent presque pas de pause, et
# 8 s par morceau laissaient les sous-titres très en retard
SILENCE_MS, SEGMENT_MS = 300, 4500

INSTRUCTIONS = (
    "Tu traduis en direct les sous-titres d'une vidéo anglaise en français. Traduis TOUT en "
    "français, y compris l'argot, les expressions et les mots isolés ; ne garde en anglais que "
    "les noms propres (personnes, marques, lieux). La phrase peut être coupée au milieu : "
    "traduis ce qu'il y a. Réponds uniquement par la traduction de la dernière phrase, sans "
    "guillemets ni commentaire. La phrase précédente n'est là que pour le contexte."
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

    def warm(self) -> None:
        """Charge qwen tout de suite (mesuré : 9,7 s pour la première phrase si le modèle
        n'est pas en mémoire, 0,3 s ensuite)."""
        self.client.chat(model=self.model, messages=[], keep_alive="30m",
                         options={"num_ctx": self.num_ctx})  # fmt: skip

    def __call__(self, text: str) -> str:
        context = f"Phrase précédente : {self.previous}\n" if self.previous else ""
        response = self.client.chat(
            model=self.model,
            messages=[{"role": "system", "content": INSTRUCTIONS},
                      {"role": "user", "content": f"{context}Dernière phrase : {text}"}],
            think=False, keep_alive="30m",
            options={"num_ctx": self.num_ctx, "num_predict": 120, "temperature": 0.2},
        )  # fmt: skip
        self.previous = text
        return (response.message.content or "").strip().strip('«»"').strip()


class Interpreter:
    """Deux fils à la chaîne : Whisper écrit la phrase suivante pendant que qwen traduit
    celle d'avant (constaté : à la suite, le retard s'accumulait)."""

    def __init__(self, transcribe: Callable[[np.ndarray], str], translate: Callable[[str], str],
                 show: Callable[[str, str], None], make_capture: Callable,
                 make_segmenter: Callable) -> None:  # fmt: skip
        self.transcribe, self.translate, self.show = transcribe, translate, show
        self._make_capture, self._make_segmenter = make_capture, make_segmenter
        self._phrases: queue.Queue = queue.Queue()
        self._capture = None
        self.on = False

    def start(self) -> None:
        if self.on:
            return
        self.on = True
        self._phrases, texts = queue.Queue(), queue.Queue()
        segmenter = self._make_segmenter(self._phrases.put)
        self._capture = self._make_capture(segmenter.feed)
        self._capture.start()
        for work, args in ((self._hear, (self._phrases, texts)), (self._translate, (texts,))):
            threading.Thread(target=work, args=args, daemon=True, name="interprete").start()
        log.info("Interprète activé")

    def stop(self) -> None:
        if not self.on:
            return
        self.on = False
        self._capture.stop()
        self._phrases.put(None)  # les deux fils s'arrêtent
        log.info("Interprète désactivé")

    @staticmethod
    def _next(items: queue.Queue):
        """L'élément suivant ; en retard, les plus anciens sont sautés pour rester en direct."""
        item = items.get()
        while item is not None and items.qsize() > BACKLOG:
            item = items.get()
        return item

    def _hear(self, phrases: queue.Queue, texts: queue.Queue) -> None:
        while (segment := self._next(phrases)) is not None:
            try:
                started = time.monotonic()
                if (text := self.transcribe(segment)) and self.on:
                    texts.put((text, started))
            except Exception:
                log.exception("Phrase de l'interprète perdue")
        texts.put(None)

    def _translate(self, texts: queue.Queue) -> None:
        try:
            getattr(self.translate, "warm", lambda: None)()
        except Exception as error:
            log.warning("Préchargement de qwen impossible : %s", error)
        while (item := self._next(texts)) is not None:
            text, started = item
            try:
                french = self.translate(text)
                if self.on and french:
                    self.show(french, text)
                    log.info("Interprète (%.1f s) : « %s » → « %s »",
                             time.monotonic() - started, text, french)  # fmt: skip
            except Exception:
                log.exception("Phrase de l'interprète perdue")

"""La voix attend que la scène soit affichée (U8). Constaté : la météo, la carte ou le globe
se mettaient en place pendant que Friday parlait déjà, tout à-coups (la voix, le moteur web
et la carte graphique en même temps). Une scène annoncée ferme le portillon ; l'interface
le rouvre une fois le fond révélé (au plus WAIT secondes plus tard). Le texte, lui,
s'affiche sans attendre."""

import threading

WAIT = 4.0  # secondes au plus : une scène qui ne vient pas ne coupe pas la parole


class SceneGate:
    def __init__(self, kinds: set[str]) -> None:
        """`kinds` : les affichages montrés en scène (« weather » si les scènes sont activées,
        « place », « world »)."""
        self.kinds = kinds
        self._open = threading.Event()
        self._open.set()

    def expect(self, display) -> None:
        if display.kind in self.kinds:
            self._open.clear()

    def ready(self) -> None:
        self._open.set()

    def wait(self) -> None:
        self._open.wait(WAIT)
        self._open.set()  # délai passé : on ne réattend pas à chaque phrase

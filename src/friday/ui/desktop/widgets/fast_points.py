"""Des milliers de points pour QPainter.drawPoints, écrits directement depuis numpy.

Constaté : bâtir la liste de QPointF en Python prenait 5 ms par image pour les 2 600 points
de la sphère (30 fois par seconde, même pendant que Friday parle), et Python, occupé à
peindre, privait la voix de son fil (coupures). Écrire dans la mémoire d'un QPolygonF :
0,3 ms.
"""

import ctypes

import numpy as np
import shiboken6
from PySide6.QtGui import QPolygonF


class PointBuffer:
    """Un QPolygonF réutilisé d'une image à l'autre (un par usage : ne pas partager)."""

    def __init__(self) -> None:
        self.polygon = QPolygonF()

    def fill(self, xs: np.ndarray, ys: np.ndarray) -> QPolygonF:
        n = len(xs)
        if self.polygon.size() != n:
            self.polygon.resize(n)
        if n:
            address = shiboken6.getCppPointer(self.polygon.data())[0]  # QPointF : deux doubles
            view = np.ctypeslib.as_array((ctypes.c_double * (2 * n)).from_address(address))
            view[0::2], view[1::2] = xs, ys
        return self.polygon

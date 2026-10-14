"""Une seule Friday à la fois (S1) : lancée avec Windows PUIS à la main, il y en aurait eu
deux (deux micros à l'écoute, deux fois les modèles sur la carte graphique). La seconde
demande à la première de se montrer, puis s'arrête."""

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

NAME = "friday-desktop"
WAIT_MS = 500


def wake_running(name: str = NAME) -> bool:
    """True si une Friday tourne déjà (elle vient d'être priée de se montrer)."""
    socket = QLocalSocket()
    socket.connectToServer(name)
    if not socket.waitForConnected(WAIT_MS):
        return False
    socket.write(b"show")
    socket.flush()
    socket.waitForBytesWritten(WAIT_MS)
    socket.disconnectFromServer()
    return True


class InstanceServer(QObject):
    """Écoute les Friday lancées en plus : chacune demande que la fenêtre se montre."""

    show_requested = Signal()

    def __init__(self, name: str = NAME, parent: QObject | None = None) -> None:
        super().__init__(parent)
        QLocalServer.removeServer(name)  # nom laissé par une Friday qui a planté
        self.server = QLocalServer(self)
        self.server.newConnection.connect(self._connected)
        self.server.listen(name)

    def _connected(self) -> None:
        while (socket := self.server.nextPendingConnection()) is not None:
            socket.readyRead.connect(lambda s=socket: self._read(s))
            socket.disconnected.connect(socket.deleteLater)
            if socket.bytesAvailable():  # déjà arrivé (l'autre Friday est rapide)
                self._read(socket)

    def _read(self, socket: QLocalSocket) -> None:
        if b"show" in bytes(socket.readAll()):
            self.show_requested.emit()

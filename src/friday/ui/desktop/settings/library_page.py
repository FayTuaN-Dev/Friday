"""Page « Bibliothèque » : les documents indexés, ajouter (copie), retirer (déplacé dans
_retires, jamais effacé), ouvrir le dossier, mettre à jour. Appliqué tout de suite."""

import os
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from friday.files.readers import SUPPORTED
from friday.library.catalog import CATALOG

FILTER = "Documents (" + " ".join(f"*{e}" for e in sorted(SUPPORTED)) + ")"


class LibraryPage(QWidget):
    changed = Signal()  # émis depuis le fil d'indexation : rafraîchit dans le fil de l'écran

    def __init__(self, library) -> None:
        super().__init__(objectName="SettingsPage")
        self.library = library
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(8)
        layout.addWidget(QLabel("Bibliothèque", objectName="SettingsTitle"))
        if library is None:
            layout.addWidget(QLabel(
                "Bibliothèque désactivée (Fonctions → Bibliothèque de documents ; elle demande "
                "aussi la mémoire à long terme).", objectName="Hint", wordWrap=True))  # fmt: skip
            layout.addStretch()
            return
        layout.addWidget(QLabel(
            "Vos PDF, livres, cours et notes : Friday y cherche avant internet (« que dit mon "
            "livre sur… »). Tout reste sur ce PC.", objectName="Hint", wordWrap=True))  # fmt: skip
        buttons = QHBoxLayout()
        for text, action in (("Ajouter des fichiers…", self._add), ("Ouvrir le dossier",
                             self._open_folder), ("Mettre à jour", self._sync)):  # fmt: skip
            button = QPushButton(text, objectName="SettingsSmall")
            button.clicked.connect(action)
            buttons.addWidget(button)
        buttons.addStretch()
        layout.addLayout(buttons)
        trading = QHBoxLayout()
        catalog = QPushButton("Ajouter la bibliothèque de trading", objectName="SettingsSmall")
        catalog.clicked.connect(self._add_trading)
        trading.addWidget(catalog)
        trading.addWidget(QLabel(
            f"{len(CATALOG)} documents gratuits et légaux (Wikipédia, AMF, Banque de France, "
            "Fed, BRI). "
            "Les livres s'achètent : voir docs/livres-trading.md.", objectName="Hint",
            wordWrap=True), 1)  # fmt: skip
        layout.addLayout(trading)
        self.status = QLabel(objectName="Hint", wordWrap=True)
        layout.addWidget(self.status)
        self.rows = QVBoxLayout()
        self.rows.setSpacing(6)
        layout.addLayout(self.rows)
        layout.addStretch()
        self._confirming: str | None = None
        self.changed.connect(self.refresh)
        self.destroyed.connect(self._closed)
        self._open = True
        self.refresh()

    def _closed(self) -> None:
        self._open = False

    def _notify(self) -> None:
        """Appelé par l'indexation (autre fil) : la page a pu être fermée entre-temps."""
        if self._open:
            try:
                self.changed.emit()
            except RuntimeError:  # détruite pendant l'appel : l'indexation continue
                pass

    def refresh(self) -> None:
        while self.rows.count():
            self.rows.takeAt(0).widget().deleteLater()
        documents = self.library.store.documents()
        for document in documents:
            pages = f" · {document.pages} pages" if document.pages else ""
            self.rows.addWidget(self._row(document.path, f"{document.name}{pages}"))
        status = f"{len(documents)} document(s)." if documents else "Aucun document."
        if self.library.indexing:
            status += f" Indexation en cours : {self.library.indexing}…"
        self.status.setText(status)

    def _row(self, path: str, text: str) -> QFrame:
        row = QFrame(objectName="SettingsRow")
        line = QHBoxLayout(row)
        line.setContentsMargins(14, 8, 10, 8)
        line.addWidget(QLabel(text, objectName="SettingsLabel", wordWrap=True), 1)
        confirming = self._confirming == path
        remove = QPushButton("Confirmer ?" if confirming else "Retirer", objectName="SettingsSmall")
        remove.clicked.connect(lambda _=False, p=path: self._remove(p))
        line.addWidget(remove)
        return row

    def _remove(self, path: str) -> None:
        if self._confirming != path:  # deux clics : on ne retire pas par mégarde
            self._confirming = path
        else:
            self._confirming = None
            self.library.retire(path)
        self.refresh()

    def _add(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "Ajouter à la bibliothèque", "", FILTER)
        if files:
            self.library.add_files([Path(f) for f in files])
            self._sync()

    def _open_folder(self) -> None:
        os.startfile(self.library.folder)  # noqa: S606 (dossier de Friday)

    def _add_trading(self) -> None:
        self.status.setText("Téléchargement de la bibliothèque de trading…")
        self.library.add_trading_catalog(self._notify)

    def _sync(self) -> None:
        self.status.setText("Mise à jour…")
        self.library.sync_in_background(self._notify)

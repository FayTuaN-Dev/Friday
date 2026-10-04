"""Pop-up du compte rendu de Claude Code : texte (Markdown, avec le code), fichiers, dossier."""

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QTextBrowser

from jarvis.tools.base import Display
from jarvis.ui.desktop.popups.base import Popup


class ClaudePopup(Popup):
    def __init__(self, display: Display) -> None:
        data = display.data
        status = "✅" if data.get("ok") else "⚠️"
        super().__init__("🤖", f"Claude Code {status} · {display.title}", (560, 620))

        result = QTextBrowser(objectName="ClaudeResult")
        result.setOpenExternalLinks(True)
        result.setMarkdown(data.get("result", ""))
        self.body.addWidget(result, 1)

        files = data.get("files") or []
        summary = "\n".join(f"📄 {f}" for f in files[:12]) or "Aucun fichier créé ou modifié."
        if len(files) > 12:
            summary += f"\n… et {len(files) - 12} autres"
        self.body.addWidget(QLabel(summary, objectName="ClaudeFiles", wordWrap=True))

        footer = QHBoxLayout()
        if seconds := data.get("seconds"):
            footer.addWidget(QLabel(f"Durée : {seconds // 60} min {seconds % 60:02d} s",
                                    objectName="Hint"))  # fmt: skip
        footer.addStretch()
        workspace = data.get("workspace")
        if workspace:
            button = QPushButton("📂 Ouvrir le dossier", objectName="OpenFolder")
            button.clicked.connect(
                lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(workspace))))
            )
            footer.addWidget(button)
        self.body.addLayout(footer)

"""Les menus de Friday (☰ des pages, icône de la barre des tâches) : un panneau arrondi en verre
sombre, avec un titre espacé à la couleur d'accent comme les cartes de côté."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMenu, QWidget, QWidgetAction


def glass_menu(parent: QWidget | None = None, title: str = "") -> QMenu:
    menu = QMenu(parent, objectName="GlassMenu")
    # Coins arrondis : la fenêtre du menu doit être transparente autour du panneau
    menu.setWindowFlags(menu.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
    menu.setAttribute(Qt.WA_TranslucentBackground)
    if title:
        head = QWidgetAction(menu)
        head.setDefaultWidget(QLabel(title.upper(), objectName="MenuTitle"))
        head.setEnabled(False)
        menu.addAction(head)
    return menu

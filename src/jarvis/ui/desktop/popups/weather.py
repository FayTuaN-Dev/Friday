"""Pop-up météo : conditions actuelles en grand, puis les 7 prochains jours."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout

from jarvis.tools.base import Display
from jarvis.ui.desktop.popups.base import Popup


def current_block(now: dict) -> QFrame:
    block = QFrame(objectName="WeatherNow")
    row = QHBoxLayout(block)
    row.setContentsMargins(14, 10, 14, 10)
    row.addWidget(QLabel(now["icon"], objectName="WeatherIcon"))
    row.addWidget(QLabel(f"{now['temperature']}°", objectName="WeatherTemp"))
    details = QLabel(
        f"{now['label'].capitalize()}\nRessenti {now['feels_like']}°\n"
        f"Vent {now['wind']} km/h · Humidité {now['humidity']} %",
        objectName="WeatherDetails",
    )
    row.addWidget(details, 1)
    return block


class WeatherPopup(Popup):
    def __init__(self, display: Display) -> None:
        super().__init__("🌦️", f"Météo · {display.title}", (400, 430))
        self.body.addWidget(current_block(display.data["current"]))

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        for row, day in enumerate(display.data["days"]):
            cells = [
                (day["day"], "WeatherDay", Qt.AlignLeft),
                (day["icon"], "WeatherDayIcon", Qt.AlignCenter),
                (f"{day['min']}° / {day['max']}°", "WeatherRange", Qt.AlignRight),
                (f"💧 {day['rain']} %", "WeatherRain", Qt.AlignRight),
            ]
            for column, (text, name, align) in enumerate(cells):
                label = QLabel(text, objectName=name)
                label.setToolTip(day["label"])
                grid.addWidget(label, row, column, alignment=align)
        container = QVBoxLayout()
        container.setContentsMargins(4, 10, 4, 0)
        container.addLayout(grid)
        self.body.addLayout(container)
        self.body.addStretch()

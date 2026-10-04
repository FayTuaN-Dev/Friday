"""Outil : météo actuelle et prévisions sur 7 jours (Open-Meteo, gratuit et sans clé)."""

from datetime import date

import httpx

from jarvis.brain.prompts import JOURS
from jarvis.tools.base import Display, Tool, ToolResult
from jarvis.tools.weather_codes import describe_weather

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
CURRENT = "temperature_2m,apparent_temperature,weather_code,wind_speed_10m,relative_humidity_2m"
DAILY = "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"


def day_name(iso_day: str, today: date) -> str:
    day = date.fromisoformat(iso_day)
    delta = (day - today).days
    return {0: "Aujourd'hui", 1: "Demain"}.get(delta, JOURS[day.weekday()].capitalize())


class WeatherTool(Tool):
    name = "get_weather"
    description = (
        "Donne la météo actuelle et les prévisions des 7 prochains jours pour une ville. "
        "À utiliser pour toute question de météo, de température, de pluie ou de vent. "
        "Sans ville précisée : donne la ville de l'utilisateur si ta mémoire la connaît, "
        "sinon laisse « city » vide (sa ville par défaut sera utilisée). Ne devine jamais."
    )
    parameters = {"city": {"type": "string", "description": "La ville (vide = chez l'utilisateur)"}}

    def __init__(self, home_city: str = "", client: httpx.Client | None = None) -> None:
        self.home_city = home_city
        self.client = client or httpx.Client(timeout=8)

    def label(self, args: dict) -> str:
        return f"🌦️ Météo : {args.get('city') or self.home_city or '?'}"

    def run(self, city: str = "") -> ToolResult:
        city = (city or self.home_city).strip()
        if not city:
            return ToolResult(
                "Aucune ville connue : demande à l'utilisateur pour quelle ville il veut la météo."
            )
        place = self._locate(city)
        if place is None:
            return ToolResult(f"Je ne trouve pas la ville « {city} ».")
        forecast = self.client.get(
            FORECAST_URL,
            params={
                "latitude": place["latitude"],
                "longitude": place["longitude"],
                "current": CURRENT,
                "daily": DAILY,
                "timezone": "auto",
                "forecast_days": 7,
            },
        )
        forecast.raise_for_status()
        return self._result(place, forecast.json())

    def _locate(self, city: str) -> dict | None:
        response = self.client.get(
            GEOCODING_URL, params={"name": city, "count": 1, "language": "fr"}
        )
        response.raise_for_status()
        results = response.json().get("results")
        return results[0] if results else None

    def _result(self, place: dict, data: dict) -> ToolResult:
        now, daily = data["current"], data["daily"]
        today = date.fromisoformat(daily["time"][0])
        label, icon = describe_weather(now["weather_code"])
        name = place["name"] + (f" ({place['country']})" if place.get("country") else "")
        current = {
            "temperature": round(now["temperature_2m"]),
            "feels_like": round(now["apparent_temperature"]),
            "label": label,
            "icon": icon,
            "wind": round(now["wind_speed_10m"]),
            "humidity": now["relative_humidity_2m"],
        }
        days = []
        for i, iso_day in enumerate(daily["time"]):
            day_label, day_icon = describe_weather(daily["weather_code"][i])
            days.append(
                {
                    "day": day_name(iso_day, today),
                    "label": day_label,
                    "icon": day_icon,
                    "min": round(daily["temperature_2m_min"][i]),
                    "max": round(daily["temperature_2m_max"][i]),
                    "rain": daily["precipitation_probability_max"][i] or 0,
                }
            )
        lines = [
            f"Météo à {name}, maintenant : {current['temperature']} °C (ressenti "
            f"{current['feels_like']} °C), {label}, vent {current['wind']} km/h, "
            f"humidité {current['humidity']} %."
        ]
        lines += [
            f"{d['day']} : {d['label']}, de {d['min']} à {d['max']} °C, "
            f"risque de pluie {d['rain']} %."
            for d in days
        ]
        lines.append("Les prévisions détaillées sont affichées à l'écran : résume l'essentiel.")
        return ToolResult(
            "\n".join(lines),
            Display("weather", name, {"current": current, "days": days}),
        )

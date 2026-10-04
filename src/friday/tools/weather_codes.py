"""Codes météo WMO (utilisés par Open-Meteo) → description française + icône."""

WEATHER_CODES: dict[int, tuple[str, str]] = {
    0: ("ciel dégagé", "☀️"),
    1: ("plutôt dégagé", "🌤️"),
    2: ("partiellement nuageux", "⛅"),
    3: ("couvert", "☁️"),
    45: ("brouillard", "🌫️"),
    48: ("brouillard givrant", "🌫️"),
    51: ("bruine légère", "🌦️"),
    53: ("bruine", "🌦️"),
    55: ("bruine forte", "🌧️"),
    56: ("bruine verglaçante", "🌧️"),
    57: ("bruine verglaçante forte", "🌧️"),
    61: ("pluie faible", "🌦️"),
    63: ("pluie", "🌧️"),
    65: ("forte pluie", "🌧️"),
    66: ("pluie verglaçante", "🌧️"),
    67: ("forte pluie verglaçante", "🌧️"),
    71: ("neige faible", "🌨️"),
    73: ("neige", "🌨️"),
    75: ("forte neige", "❄️"),
    77: ("grains de neige", "🌨️"),
    80: ("averses faibles", "🌦️"),
    81: ("averses", "🌧️"),
    82: ("violentes averses", "⛈️"),
    85: ("averses de neige", "🌨️"),
    86: ("fortes averses de neige", "❄️"),
    95: ("orage", "⛈️"),
    96: ("orage avec grêle", "⛈️"),
    99: ("orage avec forte grêle", "⛈️"),
}


def describe_weather(code: int | None) -> tuple[str, str]:
    return WEATHER_CODES.get(code if code is not None else -1, ("temps inconnu", "🌡️"))

"""Trouver LE périphérique audio voulu. Windows présente souvent le même micro plusieurs
fois, une par système audio (MME, DirectSound, WASAPI) et sous le même nom : la bibliothèque
refuse alors de choisir (« Multiple input devices found »). On prend celui du système audio
par défaut de Windows."""

import logging

import sounddevice as sd

log = logging.getLogger(__name__)


def default_hostapi() -> int:
    return sd.default.hostapi


def resolve_device(value: int | str | None, kind: str) -> int | None:
    """`value` : numéro, nom (ou morceau de nom), ou None pour celui de Windows.
    `kind` : « input » ou « output »."""
    if value is None or value == "":
        return None
    if isinstance(value, int) or str(value).isdigit():
        return int(value)
    channels = "max_input_channels" if kind == "input" else "max_output_channels"
    wanted = str(value).strip().lower()
    matches = [(index, device) for index, device in enumerate(sd.query_devices())
               if device[channels] > 0 and wanted in device["name"].lower()]  # fmt: skip
    if not matches:
        raise ValueError(f"Périphérique audio introuvable : « {value} »")
    preferred = [m for m in matches if m[1]["hostapi"] == default_hostapi()] or matches
    index, device = preferred[0]
    if len(matches) > 1:
        log.info("« %s » : %d périphériques trouvés, n°%d choisi (%s)", value, len(matches),
                 index, sd.query_hostapis(device["hostapi"])["name"])  # fmt: skip
    return index

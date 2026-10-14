"""Mémoire de la carte graphique utilisée par chaque programme (compteurs de performances de
Windows, « GPU Process Memory » : ce que montre le Gestionnaire des tâches). Lu directement
par PDH : instantané, là où PowerShell met 3 s. nvidia-smi ne le donne pas sous Windows."""

import ctypes
import logging
import re
import sys
from ctypes import wintypes

log = logging.getLogger(__name__)

COUNTER = r"\GPU Process Memory(*)\Dedicated Usage"
PDH_FMT_LARGE = 0x00000400
PDH_MORE_DATA = 0x800007D2
PID = re.compile(r"pid_(\d+)_")


class _Value(ctypes.Structure):
    _fields_ = [("CStatus", wintypes.DWORD), ("largeValue", ctypes.c_longlong)]


class _Item(ctypes.Structure):
    _fields_ = [("szName", wintypes.LPWSTR), ("FmtValue", _Value)]


class GpuMemory:
    """`by_pid()` → {pid : octets dédiés}. Vide hors de Windows ou si le compteur manque."""

    def __init__(self) -> None:
        self._query = self._counter = None
        if sys.platform != "win32":
            return
        try:
            self._pdh = ctypes.WinDLL("pdh")
            query, counter = wintypes.HANDLE(), wintypes.HANDLE()
            if self._pdh.PdhOpenQueryW(None, None, ctypes.byref(query)):
                return
            if self._pdh.PdhAddEnglishCounterW(query, COUNTER, None, ctypes.byref(counter)):
                return
            self._query, self._counter = query, counter
            self._pdh.PdhCollectQueryData(query)
        except OSError as error:
            log.info("Compteurs de la carte graphique indisponibles : %s", error)

    def by_pid(self) -> dict[int, int]:
        if self._query is None or self._pdh.PdhCollectQueryData(self._query):
            return {}
        size, count = wintypes.DWORD(0), wintypes.DWORD(0)
        status = self._pdh.PdhGetFormattedCounterArrayW(
            self._counter, PDH_FMT_LARGE, ctypes.byref(size), ctypes.byref(count), None
        )
        if status & 0xFFFFFFFF != PDH_MORE_DATA or not size.value:  # code signé côté ctypes
            return {}
        buffer = (ctypes.c_byte * size.value)()
        if self._pdh.PdhGetFormattedCounterArrayW(
            self._counter, PDH_FMT_LARGE, ctypes.byref(size), ctypes.byref(count), buffer
        ):
            return {}
        items = ctypes.cast(buffer, ctypes.POINTER(_Item))
        found: dict[int, int] = {}
        for n in range(count.value):
            if match := PID.match(items[n].szName or ""):
                pid = int(match.group(1))  # un programme peut avoir plusieurs lignes
                found[pid] = found.get(pid, 0) + max(0, items[n].FmtValue.largeValue)
        return found

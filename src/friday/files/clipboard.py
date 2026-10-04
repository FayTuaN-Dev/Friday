"""Presse-papier Windows : texte copié, ou fichiers copiés dans l'explorateur.

API Windows directement (ctypes) : utilisable depuis n'importe quel thread, sans Qt, donc
aussi en mode terminal.
"""

import ctypes
import sys
import time
from ctypes import wintypes
from dataclasses import dataclass, field

CF_UNICODETEXT = 13
CF_HDROP = 15
GMEM_MOVEABLE = 0x0002


@dataclass
class ClipboardContent:
    text: str = ""
    files: list[str] = field(default_factory=list)


class ClipboardError(Exception):
    pass


def _api():
    if sys.platform != "win32":
        raise ClipboardError("Le presse-papier n'est géré que sous Windows.")
    user32, kernel32, shell32 = ctypes.windll.user32, ctypes.windll.kernel32, ctypes.windll.shell32
    # Types 64 bits explicites : sans eux, les poignées seraient tronquées
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    shell32.DragQueryFileW.restype = wintypes.UINT
    shell32.DragQueryFileW.argtypes = [
        wintypes.HANDLE,
        wintypes.UINT,
        wintypes.LPWSTR,
        wintypes.UINT,
    ]
    return user32, kernel32, shell32


def _open(user32) -> None:
    for _ in range(10):  # une autre application peut le tenir ouvert un court instant
        if user32.OpenClipboard(None):
            return
        time.sleep(0.05)
    raise ClipboardError("Le presse-papier est occupé par une autre application.")


def read_clipboard() -> ClipboardContent:
    user32, kernel32, shell32 = _api()
    _open(user32)
    try:
        content = ClipboardContent()
        if user32.IsClipboardFormatAvailable(CF_HDROP):
            handle = user32.GetClipboardData(CF_HDROP)
            count = shell32.DragQueryFileW(handle, 0xFFFFFFFF, None, 0)
            for i in range(count):
                buffer = ctypes.create_unicode_buffer(
                    shell32.DragQueryFileW(handle, i, None, 0) + 1
                )
                shell32.DragQueryFileW(handle, i, buffer, len(buffer))
                content.files.append(buffer.value)
        if user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
            handle = user32.GetClipboardData(CF_UNICODETEXT)
            pointer = kernel32.GlobalLock(handle)
            if pointer:
                try:
                    content.text = ctypes.wstring_at(pointer)
                finally:
                    kernel32.GlobalUnlock(handle)
        return content
    finally:
        user32.CloseClipboard()


def write_clipboard(text: str) -> None:
    user32, kernel32, _ = _api()
    data = ctypes.create_unicode_buffer(text)
    size = ctypes.sizeof(data)
    handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, size)
    if not handle:
        raise ClipboardError("Mémoire insuffisante pour le presse-papier.")
    pointer = kernel32.GlobalLock(handle)
    ctypes.memmove(pointer, data, size)
    kernel32.GlobalUnlock(handle)
    _open(user32)
    try:
        user32.EmptyClipboard()
        if not user32.SetClipboardData(CF_UNICODETEXT, handle):  # Windows devient propriétaire
            raise ClipboardError("Impossible d'écrire dans le presse-papier.")
    finally:
        user32.CloseClipboard()

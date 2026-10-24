"""Localiza o Blender padrão sem executar programas nem fixar versões."""

import ctypes
import os
import shutil
from ctypes import wintypes
from pathlib import Path


def windows_associated_executable() -> str | None:
    """Consulta a associação .blend do Windows (ASSOCSTR_EXECUTABLE)."""
    if os.name != "nt":
        return None
    try:
        query = ctypes.WinDLL("shlwapi").AssocQueryStringW
        query.argtypes = [wintypes.DWORD, ctypes.c_int, wintypes.LPCWSTR,
                          wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        query.restype = ctypes.c_long
        size = wintypes.DWORD(0)
        query(0, 2, ".blend", "open", None, ctypes.byref(size))
        if not size.value:
            return None
        buffer = ctypes.create_unicode_buffer(size.value)
        if query(0, 2, ".blend", "open", buffer, ctypes.byref(size)) == 0:
            return buffer.value
    except (OSError, AttributeError):
        pass
    return None


def detect_blender() -> str:
    associated = windows_associated_executable()
    if associated:
        path = Path(os.path.expandvars(associated))
        if path.is_file() and path.stem.casefold() == "blender":
            return str(path)
    return shutil.which("blender") or ""

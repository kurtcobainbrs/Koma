"""Estado atual dos modificadores para gestos que não recebem eventos de teclado."""

import sys
from functools import lru_cache


@lru_cache(maxsize=1)
def _key_reader():
    import ctypes
    reader = ctypes.WinDLL('user32', use_last_error=True).GetAsyncKeyState
    reader.argtypes = [ctypes.c_int]
    reader.restype = ctypes.c_short
    return reader


def pressed_modifiers():
    if sys.platform != 'win32':
        return None
    try:
        reader = _key_reader()
        return {name for name, codes in (
            ('Shift', (0x10,)), ('Ctrl', (0x11,)), ('Alt', (0x12,)), ('Meta', (0x5B, 0x5C)),
        ) if any(reader(code) & 0x8000 for code in codes)}
    except OSError:
        return set()

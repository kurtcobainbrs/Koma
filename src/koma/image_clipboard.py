"""Image clipboard capability adapter; native work stays outside the UI thread."""
import asyncio
import sys
from pathlib import Path
import flet as ft
from flet.controls.exceptions import FletUnsupportedPlatformException

MAX_CLIPBOARD_IMAGE_BYTES = 80_000_000


def read_image(path):
    path = Path(path)
    if not 0 < path.stat().st_size <= MAX_CLIPBOARD_IMAGE_BYTES:
        raise ValueError('A imagem está vazia ou excede o limite de cópia.')
    return path.read_bytes()


async def copy_image(path):
    data = await asyncio.to_thread(read_image, path)
    try:
        await ft.Clipboard().set_image(data)
    except FletUnsupportedPlatformException:
        if sys.platform != 'win32':
            raise ValueError('Copiar imagens não está disponível nesta plataforma.') from None
        from koma.windows_clipboard import copy_image_bytes
        await asyncio.to_thread(copy_image_bytes, data)

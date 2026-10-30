"""Shared text presentation for live preview and encoded pictures."""
from functools import lru_cache
from importlib.resources import files
import os
from pathlib import Path
from PIL import ImageFont


def font_path(name='Archivo'):
    if name == 'Arial':
        path = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / 'arial.ttf'
        if path.is_file():
            return str(path)
    return str(files('koma').joinpath('assets/fonts/Archivo-SemiBold.ttf'))


@lru_cache(maxsize=32)
def text_font(size, name='Archivo'):
    return ImageFont.truetype(font_path(name), size)


def configured(base, values):
    if values is None:
        return base
    return dict(base, text=values['color'],
        background=values['background'] + f'{round(values["opacity"] * 255 / 100):02X}',
        font_size_ratio=values['size'] / 100, font_ratio=values['size'] / 100,
        bottom_margin_ratio=values['margin'] / 100, margin_ratio=values['margin'] / 100,
        font=values['font'], align=values['align'], position=values['position'])

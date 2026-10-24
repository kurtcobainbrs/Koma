"""Mesma composição de legenda para o player e os quadros do MP4."""

import json
from functools import lru_cache
from importlib.resources import files

from PIL import Image, ImageColor, ImageDraw, ImageFont


@lru_cache(maxsize=1)
def style():
    return json.loads(files('koma').joinpath('assets', 'storyboard-subtitles.json').read_text(encoding='utf-8'))


def normalized(text):
    return ' '.join(text.split())


def wrap(text, font, width):
    """Quebra palavras muito longas sem permitir que escapem da margem segura."""
    lines, line = [], ''
    for word in text.split():
        candidate = f'{line} {word}' if line else word
        if font.getlength(candidate) <= width:
            line = candidate
            continue
        if line:
            lines.append(line)
        line = ''
        for character in word:
            if line and font.getlength(line + character) > width:
                lines.append(line)
                line = ''
            line += character
    if line:
        lines.append(line)
    return lines


def render_subtitle(text, size):
    overlay = Image.new('RGBA', size)
    text = normalized(text)
    if not text:
        return overlay
    config = style()
    width, height = size
    padding = max(4, round(height * config['padding_ratio']))
    available = round(width * config['safe_width_ratio']) - padding * 2
    font_path = str(files('koma').joinpath('assets', 'fonts', 'Archivo-SemiBold.ttf'))
    minimum = max(10, round(height * config['minimum_size_ratio']))
    font_size = max(minimum, round(height * config['font_size_ratio']))
    while True:
        font = ImageFont.truetype(font_path, font_size)
        lines = wrap(text, font, available)
        line_height = round(font_size * 1.3)
        if len(lines) * line_height + padding * 2 <= height * config['max_height_ratio'] or font_size <= minimum:
            break
        font_size -= 1
    box_width = min(width, round(max(font.getlength(line) for line in lines)) + padding * 2)
    box_height = len(lines) * line_height + padding * 2
    left = (width - box_width) // 2
    top = height - round(height * config['bottom_margin_ratio']) - box_height
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle((left, top, left + box_width, top + box_height),
        radius=max(3, padding // 2), fill=ImageColor.getcolor(config['background'], 'RGBA'))
    for index, line in enumerate(lines):
        draw.text((width / 2, top + padding + (index + .5) * line_height), line,
            font=font, anchor='mm', fill=ImageColor.getcolor(config['text'], 'RGBA'))
    return overlay

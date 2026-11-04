"""Optional reference burn-ins; counters describe the actual exported MP4 frames."""
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
import json
import re
from math import ceil

from PIL import Image, ImageDraw, ImageFont
from koma.exports.subtitles import normalized, wrap
from koma.editor.production_numbers import shot_code, scene_code
from koma.exports.presentation_style import configured, text_font

REFERENCE_FIELDS = {
    'project': 'Projeto', 'scene': 'Cena', 'sequence': 'Sequência', 'shot': 'Shot', 'duration_frames': 'Duração (frames)',
    'duration_seconds': 'Duração (segundos)', 'shot_frame': 'Frame do shot',
    'current_frame': 'Frame atual do vídeo', 'total_frames': 'Total de frames',
    'elapsed_seconds': 'Tempo do vídeo', 'fps': 'FPS', 'resolution': 'Resolução',
}


def reference_fields(values):
    if not isinstance(values, (tuple, list)) or any(not isinstance(key, str) or key not in REFERENCE_FIELDS for key in values):
        raise ValueError('Escolha dados de referência válidos.')
    return tuple(key for key in REFERENCE_FIELDS if key in values)


@dataclass(frozen=True)
class FrameReference:
    scene: object = None
    number: int = 1
    project: object = None
    groups: tuple = ()
    scene_code: str = ''
    scene_number: int = 0

    def validate(self):
        if type(self.number) is not int or self.number < 1 or (self.scene is not None and not self.scene.node_type.starts_scene):
            raise ValueError('Referência de quadro inválida.')
        if not isinstance(self.groups, tuple) or any(not node.sequence for node in self.groups):
            raise ValueError('Referência de sequência inválida.')


def frame_references(timeline):
    from koma.editor.sequences import SequenceIndex
    board = getattr(timeline, 'board', None)
    hierarchy = SequenceIndex(board) if board is not None else None
    root = getattr(timeline, 'root', None)
    return tuple(FrameReference(root, hierarchy.production.shots.get(frame.id, index + 1) if hierarchy else index + 1, board,
        tuple(hierarchy.nodes[key] for key in reversed(hierarchy.ancestors(frame.id))) if hierarchy else (),
        hierarchy.production.code(root.id) if hierarchy and root else '',
        hierarchy.production.scenes.get(root.id, 0) if hierarchy and root else 0)
        for index, frame in enumerate(timeline.frames))


def reference_values(frame, reference, *, local_frame, count, current_frame, total_frames, fps, size, preferences=None):
    timing = preferences['timeline'] if preferences else {}
    identity = preferences['identity'] if preferences else None
    digits = max(timing.get('counter_digits', style()['counter_digits']), len(str(total_frames)), len(str(count)))
    def counter(value):
        return f'{value:0{digits}d}'
    decimals = timing.get('seconds_decimals', 3)
    seconds_width = max(timing.get('counter_digits', style()['counter_digits']), len(str(int(total_frames / fps)))) + (decimals + 1 if decimals else 0)
    def seconds(value):
        return f'{value:0{seconds_width}.{decimals}f}'
    return {
        'project': f'Proj.: {normalized(reference.project.title)}' if reference.project and normalized(reference.project.title) else '',
        'scene': ' · '.join(part for part in (scene_code(reference.scene_number, identity) if reference.scene_number else reference.scene_code,
            normalized(reference.scene.title)) if part) if reference.scene else '',
        'sequence': 'Seq.: ' + ' > '.join(normalized(node.title) for node in reference.groups if normalized(node.title))
            if any(normalized(node.title) for node in reference.groups) else '',
        'shot': ' · '.join(part for part in (shot_code(reference.number, identity), normalized(frame.title)) if part),
        'duration_frames': f'Dur.: {counter(count)} f',
        'duration_seconds': f'Dur.: {seconds(count / fps)} s',
        'shot_frame': f'Shot: {counter(local_frame)}/{counter(count)}',
        'current_frame': f'Frame: {counter(current_frame)}',
        'total_frames': f'Total: {counter(total_frames)} f',
        'elapsed_seconds': f'Tempo: {seconds((current_frame - 1) / fps)} s',
        'fps': f'{fps:g} FPS',
        'resolution': f'{size[0]} × {size[1]}',
    }


@lru_cache(maxsize=1)
def style():
    return json.loads(files('koma').joinpath('assets', 'storyboard-reference.json').read_text(encoding='utf-8'))


@lru_cache(maxsize=16)
def reference_font(size):
    return ImageFont.truetype(str(files('koma').joinpath('assets/fonts/Archivo-SemiBold.ttf')), size)


class ReferenceTypography:
    """Tabular digits without relying on optional font features or native shaping."""
    def __init__(self, font):
        self.font = font
        self.digit_width = max(font.getlength(digit) for digit in '0123456789')

    def runs(self, text):
        return re.split(r'([0-9]+)', text)

    def getlength(self, text):
        return sum(len(run) * self.digit_width if run.isascii() and run.isdigit()
            else self.font.getlength(run) for run in self.runs(text))

    def draw(self, draw, position, text, fill):
        x, y = position
        for run in self.runs(text):
            if run.isascii() and run.isdigit():
                for digit in run:
                    draw.text((x + (self.digit_width - self.font.getlength(digit)) / 2, y), digit,
                        font=self.font, fill=fill, anchor='la')
                    x += self.digit_width
            else:
                draw.text((x, y), run, font=self.font, fill=fill, anchor='la')
                x += self.font.getlength(run)


def reference_rows(parts, font, width):
    """Pack complete fields into compact lines; only oversized fields wrap."""
    gap = max(1, ceil(font.getlength(' ')))
    widths = tuple(min(width, ceil(font.getlength(text)) + gap) for text in parts)
    rows, row, used = [], [], 0
    for index, size in enumerate(widths):
        required = size + (gap if row else 0)
        if row and used + required > width:
            rows.append(tuple(row))
            row, used = [], 0
        used += size + (gap if row else 0)
        row.append(index)
    if row:
        rows.append(tuple(row))
    return tuple(rows), widths, gap


class ReferenceOverlay:
    def __init__(self, size, fields, options=None):
        self.fields = reference_fields(fields)
        self.size = size
        config = self.config = configured(style(), options)
        unit = size[1]
        self.padding = max(1, round(unit * config['padding_ratio']))
        self.margin = max(0, min(round(unit * config['margin_ratio']), (size[0] - 1) // 2, (size[1] - 1) // 2))
        self.available = max(1, size[0] - (self.margin + self.padding) * 2)
        font_size = max(config['minimum_font_size'], round(unit * config['font_ratio']))
        self.font = text_font(font_size, config.get('font', 'Archivo'))

    def apply(self, picture, values):
        if not self.fields:
            return picture
        font = self.font
        parts = self.parts(values, font)
        if not parts:
            return picture
        maximum_height = max(1, round(self.size[1] * self.config['maximum_height_ratio']))
        while True:
            typography = ReferenceTypography(font)
            rows, _, _ = reference_rows(parts, typography, self.available)
            lines = [line for row in rows for line in wrap('  '.join(parts[index] for index in row), typography, self.available)]
            line_height = max(1, round(font.size * self.config['line_height_ratio']))
            height = len(lines) * line_height + self.padding * 2
            if height <= maximum_height or font.size == 1:
                break
            font = text_font(font.size - 1, self.config.get('font', 'Archivo'))
        panel = Image.new('RGBA', (max(1, self.size[0] - self.margin * 2), height), self.config['background'])
        draw = ImageDraw.Draw(panel)
        for index, line in enumerate(lines):
            align = self.config.get('align', 'Esquerda')
            spare = self.available - typography.getlength(line)
            x = self.padding + (spare if align == 'Direita' else spare / 2 if align == 'Centro' else 0)
            typography.draw(draw, (x, self.padding + index * line_height), line, self.config['text'])
        result = picture.copy()
        top = self.size[1] - self.margin - height if self.config.get('position', 'Em cima') == 'Embaixo' else self.margin
        result.paste(panel, (self.margin, max(0, top)), panel)
        return result

    def parts(self, values, font):
        return [values[key] for key in self.fields if values.get(key)]

"""Optional reference burn-ins; counters describe the actual exported MP4 frames."""
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
import json
import re

from PIL import Image, ImageDraw, ImageFont
from koma.exports.subtitles import normalized, wrap
from koma.editor.production_numbers import shot_code, scene_code
from koma.exports.presentation_style import configured, text_font

REFERENCE_FIELDS = {
    'project': 'Projeto', 'scene': 'Cena', 'sequence': 'Sequência', 'shot': 'Quadro', 'duration_frames': 'Duração (frames)',
    'duration_seconds': 'Duração (segundos)', 'shot_frame': 'Frame do quadro',
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
        'project': f'Projeto: {normalized(reference.project.title)}' if reference.project else 'Projeto sem nome',
        'scene': ' · '.join(part for part in (scene_code(reference.scene_number, identity) if reference.scene_number else reference.scene_code,
            normalized(reference.scene.title) or 'Sem título') if part) if reference.scene else 'Sem cena',
        'sequence': 'Sequência: ' + (' > '.join(normalized(node.title) or 'Sem título' for node in reference.groups) or '—'),
        'shot': f'{shot_code(reference.number, identity)} · {normalized(frame.title) or "Sem título"}',
        'duration_frames': f'Duração: {counter(count)} f',
        'duration_seconds': f'Duração: {seconds(count / fps)} s',
        'shot_frame': f'Frame do quadro: {counter(local_frame)}/{counter(count)}',
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
        maximum_height = max(1, round(self.size[1] * self.config['maximum_height_ratio']))
        while True:
            typography = ReferenceTypography(font)
            lines = wrap(' · '.join(self.parts(values, typography)), typography, self.available)
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
        parts = []
        for key in self.fields:
            text = values[key]
            # Node names cannot make a reference band occupy the whole image.
            if key in ('project', 'scene', 'sequence', 'shot'):
                limit = self.available * self.config['name_width_ratio']
                while len(text) > 1 and font.getlength(text + '…') > limit:
                    text = text[:-1]
                if text != values[key]:
                    text += '…'
            parts.append(text)
        return parts

"""Immutable per-frame vector layer in normalized project coordinates."""
from dataclasses import dataclass
import math
import re
from koma.editor.drawing_hit_test import stroke_hit

MAX_STROKES = 2048
MAX_STROKE_POINTS = 8192
MAX_LAYER_POINTS = 65536
MIN_BRUSH_WIDTH = 1
MAX_BRUSH_WIDTH = 64
DEFAULT_BRUSH_WIDTH = 4


@dataclass(frozen=True)
class DrawingStroke:
    points: tuple
    color: str = '#FF5252'
    width: float = .004

    def validate(self):
        if not isinstance(self.points, tuple) or not 1 <= len(self.points) <= MAX_STROKE_POINTS:
            raise ValueError('Traço vazio ou grande demais.')
        if not isinstance(self.color, str) or not re.fullmatch(r'#[a-fA-F0-9]{6}', self.color):
            raise ValueError('Cor do desenho inválida.')
        if type(self.width) not in (int, float) or not math.isfinite(self.width) or not 0 < self.width <= 1:
            raise ValueError('Espessura do desenho inválida.')
        for point in self.points:
            if not isinstance(point, tuple) or len(point) != 2 or any(type(v) not in (int, float)
                    or not math.isfinite(v) or not 0 <= v <= 1 for v in point):
                raise ValueError('Ponto do desenho inválido.')


@dataclass(frozen=True)
class DrawingLayer:
    strokes: tuple = ()
    visible: bool = True

    def validate(self):
        if type(self.visible) is not bool or not isinstance(self.strokes, tuple) or len(self.strokes) > MAX_STROKES:
            raise ValueError('Camada de desenho inválida ou grande demais.')
        count = 0
        for stroke in self.strokes:
            if not isinstance(stroke, DrawingStroke):
                raise ValueError('Traço inválido.')
            stroke.validate()
            count += len(stroke.points)
        if count > MAX_LAYER_POINTS:
            raise ValueError('A camada atingiu o limite de pontos. Apague traços antes de continuar.')

    @classmethod
    def from_document(cls, raw):
        if not isinstance(raw, dict) or set(raw) - {'strokes', 'visible'}:
            raise ValueError('Camada de desenho inválida.')
        items = raw.get('strokes', [])
        if not isinstance(items, list) or len(items) > MAX_STROKES:
            raise ValueError('Lista de traços inválida.')
        strokes = []
        count = 0
        for item in items:
            if not isinstance(item, dict) or set(item) != {'points', 'color', 'width'}:
                raise ValueError('Traço inválido.')
            points = item['points']
            if not isinstance(points, list) or len(points) > MAX_STROKE_POINTS:
                raise ValueError('Lista de pontos inválida.')
            count += len(points)
            if count > MAX_LAYER_POINTS:
                raise ValueError('Camada de desenho grande demais.')
            if any(not isinstance(point, list) for point in points):
                raise ValueError('Ponto inválido.')
            strokes.append(DrawingStroke(tuple(tuple(p) for p in points), item['color'], item['width']))
        layer = cls(tuple(strokes), raw.get('visible', True))
        layer.validate()
        return layer


def erase_strokes(strokes, start, end, radius, aspect):
    """Stroke eraser: sweep a capsule through aspect-correct normalized space."""
    return tuple(stroke for stroke in strokes if not stroke_hit(stroke, start, end, radius, aspect))

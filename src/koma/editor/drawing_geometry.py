"""Shape creation in project space; outputs the existing owned vector strokes."""
from dataclasses import dataclass
from types import MappingProxyType
from collections.abc import Callable
import math

PENCIL = 'pencil'
ERASER = 'eraser'
SELECT = 'select'
CURVE_TOLERANCE_PX = .5
MIN_CIRCLE_SEGMENTS = 16
MAX_CIRCLE_SEGMENTS = 512
ARROW_HEAD_FRACTION = .25
ARROW_HEAD_MIN_FRACTION = .015
ARROW_HEAD_STROKE_MULTIPLIER = 4
ARROW_HEAD_ANGLE = math.pi / 6


def drawing_tool(tool):
    if tool not in (PENCIL, ERASER, SELECT) and tool not in SHAPE_TOOLS:
        raise ValueError('Ferramenta de desenho desconhecida.')
    return tool


def _line(start, end, size, width):
    return (start, end) if start != end else ()


def _circle_bounds(start, end, size):
    width, height = size
    dx, dy = (end[0] - start[0]) * width, (end[1] - start[1]) * height
    side = min(abs(dx), abs(dy))
    x = start[0] + math.copysign(side / width, dx)
    y = start[1] + math.copysign(side / height, dy)
    return min(start[0], x), min(start[1], y), side / width, side / height


def _rectangle(start, end, size, width):
    x, y = min(start[0], end[0]), min(start[1], end[1])
    w, h = abs(end[0] - start[0]), abs(end[1] - start[1])
    return ((x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)) if w and h else ()


def _circle(start, end, size, width):
    x, y, w, h = _circle_bounds(start, end, size)
    if not w or not h:
        return ()
    radius = w * size[0] / 2
    segments = MIN_CIRCLE_SEGMENTS if radius <= CURVE_TOLERANCE_PX else math.ceil(
        math.pi / math.acos(max(-1, 1 - CURVE_TOLERANCE_PX / radius)))
    segments = max(MIN_CIRCLE_SEGMENTS, min(MAX_CIRCLE_SEGMENTS, segments))
    points = tuple((x + w * (1 + math.cos(math.tau * i / segments)) / 2,
        y + h * (1 + math.sin(math.tau * i / segments)) / 2) for i in range(segments))
    return (*points, points[0])


def _arrow(start, end, size, width):
    project_width, project_height = size
    dx, dy = (end[0] - start[0]) * project_width, (end[1] - start[1]) * project_height
    length = math.hypot(dx, dy)
    if not length:
        return ()
    short_side = min(size)
    head = min(length * ARROW_HEAD_FRACTION, max(width * short_side * ARROW_HEAD_STROKE_MULTIPLIER,
        short_side * ARROW_HEAD_MIN_FRACTION))
    angle = math.atan2(dy, dx)
    def tip(sign):
        return (end[0] - head * math.cos(angle + sign * ARROW_HEAD_ANGLE) / project_width,
            end[1] - head * math.sin(angle + sign * ARROW_HEAD_ANGLE) / project_height)
    return start, end, tip(-1), end, tip(1)


@dataclass(frozen=True)
class DrawingShape:
    key: str
    label: str
    build: Callable

    def points(self, start, end, size, width):
        return tuple((max(0, min(1, x)), max(0, min(1, y)))
            for x, y in self.build(start, end, size, width))


SHAPE_TOOLS = MappingProxyType({shape.key: shape for shape in (
    DrawingShape('rectangle', 'Retângulo', _rectangle), DrawingShape('circle', 'Círculo', _circle),
    DrawingShape('line', 'Linha', _line), DrawingShape('arrow', 'Seta', _arrow))})

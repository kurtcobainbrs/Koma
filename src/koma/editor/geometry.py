"""Geometria do espaço de trabalho; posições não alteram a ordem narrativa."""

from dataclasses import dataclass, replace
from math import ceil

from koma.editor.models import MAX_POSITION

GRID_STEP = 24
NODE_WIDTH = 336
NODE_HEIGHT = 252
NODE_EXPANDED_HEIGHT = 800
INITIAL_COLUMNS = 3
COLUMN_STEP = NODE_WIDTH + 2 * GRID_STEP
ROW_STEP = NODE_HEIGHT + 3 * GRID_STEP
MIN_ZOOM = 0.15
MAX_ZOOM = 2.5
ZOOM_STEP = 1.1
WHEEL_ZOOM_FACTOR = 1200
INITIAL_CANVAS_WIDTH = 3200
INITIAL_CANVAS_HEIGHT = 2400
CANVAS_GROWTH_STEP = 768
CANVAS_EDGE_MARGIN = GRID_STEP * 12


def expanded_canvas_size(current_width, current_height, required_width, required_height):
    """Reserva espaço ao redor dos nodes e cresce em blocos, sem encolher ao editar."""
    return (
        max(current_width, INITIAL_CANVAS_WIDTH,
            ceil((required_width + CANVAS_EDGE_MARGIN) / CANVAS_GROWTH_STEP) * CANVAS_GROWTH_STEP),
        max(current_height, INITIAL_CANVAS_HEIGHT,
            ceil((required_height + CANVAS_EDGE_MARGIN) / CANVAS_GROWTH_STEP) * CANVAS_GROWTH_STEP),
    )


def coordinate(value, snap=True):
    value = max(-MAX_POSITION, min(MAX_POSITION, value))
    if snap:
        limit = (MAX_POSITION // GRID_STEP) * GRID_STEP
        value = max(-limit, min(limit, round(value / GRID_STEP) * GRID_STEP))
    return max(-MAX_POSITION, min(MAX_POSITION, value))


def frame_bounds(frames, heights=None):
    """Retângulo lógico, inclusive posições negativas; não depende do tamanho do canvas."""
    heights = heights or {}
    placed = [frame for frame in frames if frame.x is not None]
    if not placed:
        return 0, 0, NODE_WIDTH, NODE_HEIGHT
    return (min(frame.x for frame in placed), min(frame.y for frame in placed),
            max(frame.x + NODE_WIDTH for frame in placed),
            max(frame.y + heights.get(frame.id, NODE_HEIGHT) for frame in placed))


@dataclass
class CanvasExtent:
    width: float = INITIAL_CANVAS_WIDTH
    height: float = INITIAL_CANVAS_HEIGHT
    origin_x: float = 0
    origin_y: float = 0
    initialized: bool = False

    def include(self, frames):
        """Centraliza o conjunto inicial; depois expande em todas as direções."""
        if not frames:
            return 0, 0
        left, top, right, bottom = frame_bounds(frames)
        bottom = max(frame.y + NODE_EXPANDED_HEIGHT for frame in frames)
        if not self.initialized:
            self.width, self.height = expanded_canvas_size(self.width, self.height, right - left, bottom - top)
            # Usa a altura fechada para o centro inicial, preservando a grade.
            _, _, _, closed_bottom = frame_bounds(frames)
            self.origin_x = round((self.width / 2 - (left + right) / 2) / GRID_STEP) * GRID_STEP
            self.origin_y = round((self.height / 2 - (top + closed_bottom) / 2) / GRID_STEP) * GRID_STEP
            self.initialized = True
            return 0, 0
        dx = max(0, ceil((CANVAS_EDGE_MARGIN - (left + self.origin_x)) / CANVAS_GROWTH_STEP)) * CANVAS_GROWTH_STEP
        dy = max(0, ceil((CANVAS_EDGE_MARGIN - (top + self.origin_y)) / CANVAS_GROWTH_STEP)) * CANVAS_GROWTH_STEP
        self.origin_x += dx
        self.origin_y += dy
        self.width, self.height = expanded_canvas_size(self.width + dx, self.height + dy,
            right + self.origin_x, bottom + self.origin_y)
        return dx, dy


def next_position(frames):
    occupied = [(f.x, f.y) for f in frames if f.x is not None]
    for index in range(len(frames) * 6 + 1):
        x = GRID_STEP + (index % INITIAL_COLUMNS) * COLUMN_STEP
        y = GRID_STEP + (index // INITIAL_COLUMNS) * ROW_STEP
        if all(abs(x - ox) >= NODE_WIDTH + GRID_STEP or abs(y - oy) >= NODE_HEIGHT + GRID_STEP
               for ox, oy in occupied):
            return x, y
    # Cada quadro pode bloquear poucos slots. O limite acima mantém a busca finita.
    return GRID_STEP, coordinate(max((y for _, y in occupied), default=0) + ROW_STEP)


def group_delta(positions, dx, dy, *, anchor, snap=False):
    """Um único deslocamento preserva o espaçamento, inclusive no snap e nos limites."""
    if snap:
        dx = coordinate(anchor[0] + dx) - anchor[0]
        dy = coordinate(anchor[1] + dy) - anchor[1]
    xs, ys = zip(*positions.values())
    return (max(-MAX_POSITION - min(xs), min(MAX_POSITION - max(xs), dx)),
            max(-MAX_POSITION - min(ys), min(MAX_POSITION - max(ys), dy)))


def place_missing(board):
    placed = [frame for frame in board.frames if frame.x is not None]
    frames = []
    for frame in board.frames:
        if frame.x is None:
            x, y = next_position(placed)
            frame = replace(frame, x=x, y=y)
            placed.append(frame)
        frames.append(frame)
    return replace(board, frames=tuple(frames))


def content_bounds(frames):
    return (max((frame.x + NODE_WIDTH for frame in frames if frame.x is not None), default=NODE_WIDTH) + GRID_STEP,
            max((frame.y + NODE_EXPANDED_HEIGHT for frame in frames if frame.y is not None),
                default=NODE_HEIGHT) + GRID_STEP)

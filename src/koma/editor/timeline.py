"""Sequência temporal e escala, independentes do player e dos controles Flet."""

from bisect import bisect_right
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
import math

from koma.editor.graph import ordered
from koma.editor.models import MAX_DURATION, SUPPORTED_FPS
from koma.editor.scenes import principal, scene_frames


class Timeline:
    def __init__(self, board, active=None):
        self.board = board
        sequence_board = ordered(board)
        self.root = principal(sequence_board, active)
        has_scenes = any(frame.node_type.starts_scene for frame in sequence_board.frames)
        sequence = scene_frames(sequence_board, self.root) if self.root else () if has_scenes else sequence_board.frames
        self.frames = tuple(frame for frame in sequence if frame.node_type.timed and not frame.muted
                            and not (self.root and self.root.muted))
        self.starts = []
        self.total = 0.0
        for frame in self.frames:
            self.starts.append(self.total)
            self.total += frame.duration
        self.picture_total = self.total
        scope = self.root.id if self.root else ''
        self.audio_tracks = tuple(track for track in board.audio_tracks if track.scene_id == scope)
        self.markers = tuple(sorted((marker for marker in board.markers if marker.scene_id == scope), key=lambda marker: (marker.position, marker.id)))
        if self.frames:
            self.total = max(self.total, *(track.start + track.duration for track in self.audio_tracks), self.total)

    def index_at(self, seconds):
        return max(0, min(len(self.frames) - 1, bisect_right(self.starts, seconds) - 1))


@dataclass(frozen=True)
class TimeScale:
    pixels_per_second: float

    def __post_init__(self):
        if not math.isfinite(self.pixels_per_second) or self.pixels_per_second <= 0:
            raise ValueError('Escala temporal inválida.')

    @classmethod
    def fit(cls, width, duration):
        if not math.isfinite(width) or not math.isfinite(duration) or width <= 0 or duration <= 0:
            raise ValueError('Dimensões temporais inválidas.')
        return cls(width / duration)

    def pixels(self, seconds):
        return seconds * self.pixels_per_second

    def seconds(self, pixels):
        return pixels / self.pixels_per_second


def snap_duration(seconds, fps):
    """Arraste trabalha em frames inteiros; limites vêm do modelo do documento."""
    if type(fps) is not int or fps not in SUPPORTED_FPS or not math.isfinite(seconds):
        raise ValueError('Duração ou FPS inválido.')
    count = int((Decimal(str(seconds)) * fps).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return max(1, min(MAX_DURATION * fps, count)) / fps

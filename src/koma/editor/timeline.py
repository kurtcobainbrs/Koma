"""Sequência temporal e escala, independentes do player e dos controles Flet."""

from bisect import bisect_right
from dataclasses import dataclass, replace
from copy import copy
from decimal import Decimal, ROUND_HALF_UP
import math

from koma.editor.graph import ordered
from koma.editor.models import MIN_DURATION, MAX_DURATION, SUPPORTED_FPS
from koma.editor.scenes import principal, scene_frames


class Timeline:
    local_editing = True
    def __init__(self, board, active=None):
        self.board = board
        sequence_board = ordered(board)
        self.root = principal(sequence_board, active)
        has_scenes = any(frame.node_type.starts_scene for frame in sequence_board.frames)
        from koma.editor.sequences import SequenceIndex
        hierarchy = SequenceIndex(sequence_board)
        sequence = scene_frames(sequence_board, self.root) if self.root else () if has_scenes else tuple(
            item for frame in sequence_board.frames if frame.id not in hierarchy.parents
            for item in hierarchy.playback(frame.id))
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

    def with_duration(self, identifier, seconds):
        """Transient timing snapshot; a duration edit cannot change graph topology."""
        return self.with_durations({identifier: seconds})

    def with_board(self, board):
        """Reuse established scene order for node-property edits; rebuild only topology."""
        if (self.board.links != board.links or len(self.board.frames) != len(board.frames)
                or any((before.id, before.kind, before.muted, before.sequence) !=
                    (after.id, after.kind, after.muted, after.sequence)
                    for before, after in zip(self.board.frames, board.frames))):
            return Timeline(board, self.root.id if self.root else None)
        nodes = {frame.id: frame for frame in board.frames}
        preview = copy(self)
        preview.board = board
        preview.frames = tuple(nodes[frame.id] for frame in self.frames)
        preview.root = nodes[self.root.id] if self.root else None
        scope = preview.root.id if preview.root else ''
        preview.audio_tracks = tuple(track for track in board.audio_tracks if track.scene_id == scope)
        preview.markers = tuple(sorted((marker for marker in board.markers if marker.scene_id == scope),
            key=lambda marker: (marker.position, marker.id)))
        preview.starts, preview.picture_total = [], 0.0
        for frame in preview.frames:
            preview.starts.append(preview.picture_total)
            preview.picture_total += frame.duration
        preview.total = max(preview.picture_total,
            *(track.start + track.duration for track in preview.audio_tracks), preview.picture_total) if preview.frames else 0
        return preview

    def with_durations(self, values):
        """Change only timing; immutable drawings/media need no pointer-event validation."""
        if not values.keys() <= {frame.id for frame in self.frames}:
            raise ValueError('O quadro não está mais na timeline.')
        if any(type(seconds) not in (float, int) or not math.isfinite(seconds)
                or not MIN_DURATION <= seconds <= MAX_DURATION for seconds in values.values()):
            raise ValueError('Duração inválida.')
        changes = {frame.id: replace(frame, duration=values[frame.id]) for frame in self.frames if frame.id in values}
        preview = copy(self)
        preview.frames = tuple(changes.get(frame.id, frame) for frame in self.frames)
        preview.board = replace(self.board, frames=tuple(changes.get(frame.id, frame) for frame in self.board.frames))
        delta = 0
        preview.starts = []
        for start, frame in zip(self.starts, self.frames):
            preview.starts.append(start + delta)
            delta += values.get(frame.id, frame.duration) - frame.duration
        preview.picture_total = self.picture_total + delta
        preview.total = max(preview.picture_total,
            *(track.start + track.duration for track in self.audio_tracks), preview.picture_total)
        return preview


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

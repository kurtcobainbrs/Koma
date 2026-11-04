"""Navegação temporal sem persistência ou dependência de controles visuais."""

from dataclasses import dataclass
import math

from koma.editor.timeline import TimeScale


def frame_position(seconds, total, fps):
    """Limita a busca à sequência e alinha a agulha ao frame do projeto."""
    if not all(math.isfinite(value) for value in (seconds, total)) or total < 0 or fps <= 0:
        raise ValueError('Posição temporal inválida.')
    return min(total, max(0, math.floor(seconds * fps + .5) / fps))


def signed_frame_position(seconds, limit, fps):
    return math.copysign(frame_position(abs(seconds), limit, fps), seconds)


def stop_positions(timeline):
    """Pontos comuns de navegação: início/fim, cortes e marcadores da cena."""
    first, end = timeline.playback_start, timeline.playback_end
    return tuple(sorted({first, end, *timeline.starts,
        *(marker.position for marker in timeline.markers if first <= marker.position <= end)}))


def adjacent_stop(timeline, position, delta):
    points = stop_positions(timeline)
    if delta > 0:
        return next((point for point in points if point > position + 1e-8), timeline.playback_end)
    return next((point for point in reversed(points) if point < position - 1e-8), timeline.playback_start)


def ruler_ticks(scale, offset, width, total, fps, label_spacing):
    """Gera apenas marcas visíveis, com intervalos inteiros em frames."""
    desired = max(1, math.ceil(scale.seconds(label_spacing) * fps))
    magnitude = 10 ** math.floor(math.log10(desired))
    step = next(factor * magnitude for factor in (1, 2, 5, 10) if factor * magnitude >= desired)
    start = max(0, math.floor(scale.seconds(offset) * fps / step) * step)
    end = min(total * fps, scale.seconds(offset + width) * fps)
    return tuple((frame / fps, scale.pixels(frame / fps))
        for frame in range(start, math.floor(end) + 1, step))


@dataclass(frozen=True)
class ScrubGesture:
    pointer_x: float
    position: float
    scale: TimeScale
    targets: object


class TimelineNavigator:
    def __init__(self, player):
        self.player = player
        self.gesture = None

    @property
    def available(self):
        player = self.player
        return (player.opened and bool(player.timeline and player.timeline.frames)
            and not player.editing)

    def seek(self, seconds, *, snap=False, targets=None, scale=None):
        if not self.available or not math.isfinite(seconds):
            return
        player = self.player
        if snap:
            targets = targets or player.snapping.capture(player.timeline)
            seconds = player.snapping.resolve(seconds, scale or player.strip.scale, targets,
                minimum=player.timeline.playback_start, maximum=player.timeline.playback_end)
        position = frame_position(seconds, player.timeline.total, player.view.board.fps)
        position = max(player.timeline.playback_start, min(player.timeline.playback_end, position))
        if position == player.position and not player.playing:
            return
        player.playing = False
        player.position = position
        player.render_position()

    def begin(self, pointer_x, scale, seconds=None):
        if not self.available or not math.isfinite(pointer_x):
            return
        targets = self.player.snapping.capture(self.player.timeline)
        origin = self.player.position if seconds is None else seconds
        self.seek(origin, snap=True, targets=targets, scale=scale)
        self.gesture = ScrubGesture(pointer_x, origin, scale, targets)

    def move(self, pointer_x):
        if self.gesture and math.isfinite(pointer_x):
            gesture = self.gesture
            self.seek(gesture.position + gesture.scale.seconds(pointer_x - gesture.pointer_x),
                snap=True, targets=gesture.targets, scale=gesture.scale)

    def end(self, e=None):
        if e is not None and getattr(e, 'global_position', None) is not None:
            self.move(e.global_position.x)
        self.gesture = None

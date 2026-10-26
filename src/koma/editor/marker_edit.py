"""Gesto transacional de marcadores: prévia, snap e uma confirmação no histórico."""

from dataclasses import dataclass, replace
import math

from koma.editor.timeline_navigation import frame_position


def marker_position(seconds, timeline, fps, scale, candidates=(), tolerance=0):
    position = frame_position(seconds, timeline.total, fps)
    if candidates:
        target = min(candidates, key=lambda value: abs(value - position))
        if abs(scale.pixels(target - position)) <= tolerance:
            position = frame_position(target, timeline.total, fps)
    return position


@dataclass(frozen=True)
class MarkerDrag:
    marker: object
    board: object
    session: object
    scope: object
    pointer_x: float
    scale: object
    previous_position: float
    candidates: tuple


class MarkerEditor:
    def __init__(self, player):
        self.player, self.view = player, player.view
        self.selected = None
        self.drag = None
        self.position = None
        self.committing = False
        self.snap_enabled = True

    def select(self, identifier):
        if not self.player.editing:
            marker = next((item for item in self.player.timeline.markers if item.id == identifier), None)
            if marker:
                self.selected = identifier
                self.player.strip.navigator.seek(marker.position)
                self.player.focus_timeline()

    def begin(self, identifier, pointer_x, scale):
        if self.player.editing or not self.player.opened or not self.view.editable() or not math.isfinite(pointer_x):
            return None
        timeline = self.player.timeline
        marker = next((item for item in timeline.markers if item.id == identifier), None)
        if marker is None:
            return None
        candidates = {0.0, timeline.total, *timeline.starts}
        candidates.update(item.position for item in timeline.markers if item.id != identifier)
        candidates.add(self.player.position)
        for track in timeline.audio_tracks:
            candidates.update((track.start, track.start + track.duration))
        self.drag = MarkerDrag(marker, self.view.board, self.view.session, self.player.scene_anchor,
            pointer_x, scale, self.player.position, tuple(sorted(candidates)))
        self.position = marker.position
        self.selected = identifier
        self.player.playing = False
        self.player.strip.navigator.end()
        self.view.lock(True)
        self.player.render()
        return self.drag

    def move(self, token, pointer_x):
        if token is None or token is not self.drag or not math.isfinite(pointer_x):
            return
        if (self.view.board is not token.board or self.view.session is not token.session
                or self.player.scene_anchor != token.scope):
            self.cancel()
            return
        self.position = marker_position(token.marker.position + token.scale.seconds(pointer_x - token.pointer_x),
            self.player.timeline, token.board.fps, token.scale,
            token.candidates if self.snap_enabled else (), self.player.strip.style.snap_distance)
        self.player.position = self.position
        self.player.render()

    def cancel(self, *, update=True):
        token, self.drag = self.drag, None
        self.position = None
        if token:
            self.player.position = token.previous_position
            self.view.lock(False)
            if update and self.player.opened:
                self.player.render()

    async def finish(self, token):
        if token is None or token is not self.drag:
            return
        position, self.position, self.drag = self.position, None, None
        self.committing = True
        self.view.lock(False)
        try:
            if (self.view.board is not token.board or self.view.session is not token.session
                    or self.player.scene_anchor != token.scope or not self.player.opened):
                return
            if position != token.marker.position:
                markers = tuple(replace(item, position=position) if item.id == token.marker.id else item for item in token.board.markers)
                await self.player.media.commit(replace(token.board, markers=markers))
        finally:
            self.committing = False
            if self.player.opened:
                self.player.render()
                self.player.focus_timeline()

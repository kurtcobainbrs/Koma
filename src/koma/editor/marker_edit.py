"""Gesto transacional de marcadores: prévia, snap e uma confirmação no histórico."""

from dataclasses import dataclass, replace
import math

from koma.editor.timeline_navigation import frame_position
from koma.editor.timeline_snap import SnapTargets, TimelineSnapping


def marker_position(seconds, timeline, fps, scale, candidates=(), tolerance=0):
    """Compatibility adapter over the shared snap resolver."""
    positions = tuple(sorted(set(candidates)))
    targets = SnapTargets(positions, tuple(frozenset({('target', value)}) for value in positions))
    seconds = TimelineSnapping(tolerance).resolve(seconds, scale, targets, maximum=timeline.total)
    return frame_position(seconds, timeline.total, fps)


@dataclass(frozen=True)
class MarkerDrag:
    marker: object
    board: object
    session: object
    scope: object
    pointer_x: float
    scale: object
    previous_position: float
    candidates: SnapTargets


class MarkerEditor:
    @property
    def snap_enabled(self):
        return self.player.snapping.enabled

    @snap_enabled.setter
    def snap_enabled(self, value):
        self.player.snapping.enabled = value
    def __init__(self, player):
        self.player, self.view = player, player.view
        self.selected = None
        self.drag = None
        self.position = None
        self.committing = False
        self.snap_enabled = True

    def clear_selection(self):
        selected, self.selected = self.selected, None
        return selected is not None

    async def delete_selected(self):
        if self.selected:
            await self.player.media.remove_marker(self.selected)

    def select(self, identifier):
        if not self.player.editing:
            marker = next((item for item in self.player.timeline.markers if item.id == identifier), None)
            if marker:
                self.player.edit_selection.claim(self)
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
        self.player.edit_selection.claim(self)
        candidates = self.player.snapping.capture(timeline, exclude=(('marker', identifier),),
            playhead=self.player.position)
        self.drag = MarkerDrag(marker, self.view.board, self.view.session, self.player.scene_anchor,
            pointer_x, scale, self.player.position, candidates)
        self.position = marker.position
        self.selected = identifier
        self.player.pause_for_edit()
        self.player.strip.navigator.end()
        self.view.lock(True, update=False)
        self.player.set_gesture_locked(True)
        self.refresh_lane()
        return self.drag

    def move(self, token, pointer_x):
        if token is None or token is not self.drag or not math.isfinite(pointer_x):
            return
        if (self.view.board is not token.board or self.view.session is not token.session
                or self.player.scene_anchor != token.scope):
            self.cancel()
            return
        seconds = self.player.snapping.resolve(token.marker.position + token.scale.seconds(pointer_x - token.pointer_x),
            token.scale, token.candidates, maximum=self.player.timeline.total,
            minimum=self.player.media.scene_offset(token.marker.scene_id))
        position = frame_position(seconds, self.player.timeline.total, token.board.fps)
        if position != self.position:
            self.position = position
            self.player.strip.marker_lane.preview(token.marker.id)

    def refresh_lane(self):
        self.player.strip.marker_lane.sync()
        if self.player.presenting:
            self.view.page.update(self.player.strip.marker_lane.content, self.player.strip.marker_lane.guides)

    def cancel(self, *, update=True):
        token, self.drag = self.drag, None
        self.position = None
        if token:
            self.player.position = token.previous_position
            self.view.lock(False, update=False)
            if update and self.player.opened:
                self.player.set_gesture_locked(False)
                self.refresh_lane()
            else:
                self.player.controls.disabled = False

    async def finish(self, token):
        if token is None or token is not self.drag:
            return
        position, self.position, self.drag = self.position, None, None
        self.committing = True
        self.view.lock(False, update=False)
        changed = False
        try:
            if (self.view.board is not token.board or self.view.session is not token.session
                    or self.player.scene_anchor != token.scope or not self.player.opened):
                return
            if position != token.marker.position:
                offset = self.player.media.scene_offset(token.marker.scene_id)
                markers = tuple(replace(item, position=max(0, position - offset)) if item.id == token.marker.id else item for item in token.board.markers)
                await self.player.media.commit(replace(token.board, markers=markers), render=False, label='Mover marcador')
                changed = True
        finally:
            self.committing = False
            self.player.controls.disabled = False
            if self.player.opened:
                if changed:
                    self.player.render()
                else:
                    self.player.set_gesture_locked(False)
                    self.refresh_lane()
                self.player.focus_timeline()

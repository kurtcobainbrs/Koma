"""Arraste de duração: prévia transitória, cancelamento e um commit no histórico."""

from dataclasses import dataclass
import math

from koma.editor.timeline import snap_duration
from koma.editor.timing import parse_duration


@dataclass
class DurationDrag:
    identifier: str
    board: object
    session: object
    pointer_x: float
    scale: object
    duration: float
    value: float
    position: float
    previous_position: float
    timeline: object


class TimelineEditor:
    def __init__(self, player):
        self.player, self.view = player, player.view
        self.drag = None
        self.committing = False

    async def set_duration(self, identifier, expression, board, session):
        """Confirma uma entrada textual pela mesma operação de propriedades."""
        if (not self.player.opened or self.drag or self.committing or not self.view.editable()
                or self.view.board is not board or self.view.session is not session
                or not any(frame.id == identifier for frame in self.player.timeline.frames)):
            raise ValueError('O quadro mudou. Feche a edição e tente novamente.')
        seconds = parse_duration(expression, board.fps, frames=True)
        self.player.playing = False
        self.committing = True
        try:
            await self.view.set_frame_properties(identifier, duration=seconds)
            self.view.properties.sync()
            self.view.page.update(self.view.properties.content)
        finally:
            self.committing = False
            self.player.rebuild_timeline()
            if self.player.opened:
                self.player.render()

    def begin(self, identifier, pointer_x, scale):
        player, view = self.player, self.view
        if (self.drag or self.committing or not player.opened or not view.editable() or
                not math.isfinite(pointer_x)):
            return None
        index = next((i for i, frame in enumerate(player.timeline.frames) if frame.id == identifier), None)
        if index is None:
            return None
        frame = player.timeline.frames[index]
        self.drag = DurationDrag(identifier, view.board, view.session, pointer_x, scale,
            frame.duration, frame.duration, player.timeline.starts[index], player.position, player.timeline)
        player.playing = False
        player.position = self.drag.position
        view.lock(True)
        player.render()
        return self.drag

    def move(self, token, pointer_x):
        if token is None or token is not self.drag or not math.isfinite(pointer_x):
            return
        drag = self.drag
        if self.view.session is not drag.session or self.view.board is not drag.board:
            self.cancel()
            return
        delta = pointer_x - drag.pointer_x
        value = drag.duration if delta == 0 else snap_duration(
            drag.duration + drag.scale.seconds(delta), drag.board.fps)
        if value == drag.value:
            return
        drag.value = value
        self.player.timeline = drag.timeline.with_duration(drag.identifier, value)
        frame = next(frame for frame in self.player.timeline.frames if frame.id == drag.identifier)
        self.view.cards[drag.identifier].sync_duration(frame)
        self.player.render_duration_preview(frame)

    def restore_card(self, drag):
        frame = next((frame for frame in self.view.board.frames if frame.id == drag.identifier), None)
        if frame and drag.identifier in self.view.cards:
            self.view.cards[drag.identifier].sync(frame)
            if not self.view.closing:
                self.view.page.update(self.view.cards[drag.identifier].content)

    def cancel(self, e=None, *, update=True):
        if self.drag is None:
            return
        drag, self.drag = self.drag, None
        self.restore_card(drag)
        self.view.lock(False)
        self.player.position = drag.previous_position
        self.player.rebuild_timeline()
        if update and self.player.opened:
            self.player.render()

    async def finish(self, token):
        if token is None or token is not self.drag:
            return
        drag, self.drag = self.drag, None
        self.committing = True
        self.restore_card(drag)
        self.view.lock(False)
        try:
            if (self.view.session is not drag.session or self.view.board is not drag.board or
                    not self.view.editable()):
                return
            if drag.value != drag.duration:
                await self.view.set_frame_properties(drag.identifier, duration=drag.value)
                self.view.properties.sync()
                self.view.page.update(self.view.properties.content)
        finally:
            self.committing = False
            self.player.rebuild_timeline()
            if self.player.opened:
                self.player.render()

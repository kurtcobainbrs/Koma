"""Arraste de duração: prévia transitória, cancelamento e um commit no histórico."""

from dataclasses import dataclass
import math

from koma.editor.timing import parse_duration
from koma.editor.duration_trim import DurationTrim


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
    trim: DurationTrim
    ripple: bool
    values: dict
    targets: object


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

    def begin(self, identifier, pointer_x, scale, *, ripple=False):
        player, view = self.player, self.view
        if (self.drag or self.committing or not player.opened or not view.editable() or
                not math.isfinite(pointer_x)):
            return None
        index = next((i for i, frame in enumerate(player.timeline.frames) if frame.id == identifier), None)
        if index is None:
            return None
        frame = player.timeline.frames[index]
        trim = DurationTrim.at(player.timeline, index)
        moving_cut = player.timeline.starts[index] + frame.duration
        exclude = {('boundary', moving_cut)}
        if ripple:
            for following, start in zip(player.timeline.frames[index + 1:], player.timeline.starts[index + 1:]):
                exclude.update((('boundary', start), ('boundary', start + following.duration), ('key', following.id)))
        elif index + 1 < len(player.timeline.frames):
            exclude.add(('key', player.timeline.frames[index + 1].id))
        targets = player.snapping.capture(player.timeline, exclude=exclude, playhead=player.position)
        self.drag = DurationDrag(identifier, view.board, view.session, pointer_x, scale,
            frame.duration, frame.duration, player.timeline.starts[index], player.position, player.timeline,
            trim, ripple, {identifier: frame.duration} if ripple else trim.originals, targets)
        player.playing = False
        player.position = self.drag.position
        view.lock(True, update=False)
        player.render_position()
        player.render_duration_preview(frame)
        return self.drag

    def move(self, token, pointer_x):
        if token is None or token is not self.drag or not math.isfinite(pointer_x):
            return
        drag = self.drag
        if self.view.session is not drag.session or self.view.board is not drag.board:
            self.cancel()
            return
        delta = pointer_x - drag.pointer_x
        boundary = self.player.snapping.resolve(drag.position + drag.duration + drag.scale.seconds(delta),
            drag.scale, drag.targets, minimum=drag.position + 1 / drag.board.fps)
        values = drag.trim.resolve(boundary - drag.position, ripple=drag.ripple)
        if values == drag.values:
            return
        drag.values = values
        drag.value = values[drag.identifier]
        self.player.timeline = drag.timeline.with_durations(values)
        frame = next(frame for frame in self.player.timeline.frames if frame.id == drag.identifier)
        for item in self.player.timeline.frames:
            if item.id in values and item.id in self.view.cards:
                self.view.cards[item.id].sync_duration(item)
        self.player.render_duration_preview(frame)

    def restore_card(self, drag):
        controls = []
        identifiers = drag.trim.originals.keys()
        for frame in self.view.board.frames:
            if frame.id in identifiers and frame.id in self.view.cards:
                card = self.view.cards[frame.id]
                card.sync_duration(frame)
                controls.append(card.duration)
        if controls and not self.view.closing:
            self.view.page.update(*controls)

    def cancel(self, e=None, *, update=True):
        if self.drag is None:
            return
        drag, self.drag = self.drag, None
        self.restore_card(drag)
        self.view.lock(False, update=False)
        self.player.position = drag.previous_position
        self.player.rebuild_timeline()
        if update and self.player.opened:
            self.player.render()

    async def finish(self, token):
        if token is None or token is not self.drag:
            return
        drag, self.drag = self.drag, None
        self.committing = True
        self.view.lock(False, update=False)
        try:
            if (self.view.session is not drag.session or self.view.board is not drag.board or
                    not self.view.editable()):
                self.restore_card(drag)
                return
            if drag.value != drag.duration:
                await self.view.set_frames_properties({key: {'duration': seconds}
                    for key, seconds in drag.values.items()},
                    label='Ajustar corte' if len(drag.values) > 1 else 'Alterar duração')
                self.view.properties.sync()
                self.view.page.update(self.view.properties.content)
        finally:
            self.committing = False
            self.player.rebuild_timeline()
            if self.player.opened:
                self.player.render()

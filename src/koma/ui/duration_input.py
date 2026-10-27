"""Entrada de duração da timeline; conversão e confirmação pertencem ao editor."""

import flet as ft

from koma.editor.timing import duration_text
from koma.expressions import MAX_EXPRESSION_LENGTH
from koma.ui.design import CONTROL_HEIGHT, COMPACT_CONTROL_HEIGHT, input_style


class DurationInput:
    def __init__(self, player):
        self.player = player
        self.focused = False
        self.saving = False
        self.target = None
        self.identifier = None
        self.field = ft.TextField(width=CONTROL_HEIGHT * 2, suffix=ft.Text('f'),
            max_length=MAX_EXPRESSION_LENGTH, counter=ft.Container(width=0, height=0),
            on_focus=self.focus, on_blur=self.cancel, on_submit=self.save, on_change=self.changed,
            tooltip='Frames do quadro · aceita 24*2 · Enter aplica; Esc cancela.',
            **input_style(height=COMPACT_CONTROL_HEIGHT))

    def active_frame(self):
        timeline, index = self.player.timeline, self.player.current
        return timeline.frames[index] if timeline and 0 <= index < len(timeline.frames) else None

    def sync(self):
        frame = self.active_frame()
        identifier = frame.id if frame else None
        if identifier != self.identifier:
            self.focused = False
            self.target = None
            self.field.error_text = None
        self.identifier = identifier
        self.field.disabled = (not frame or not self.player.view.editable()
            or self.player.duration_editor.drag is not None or (self.player.duration_editor.committing and not self.saving))
        if not self.focused:
            self.field.value = duration_text(frame.duration, self.player.view.board.fps, frames=True) if frame else ''

    def focus(self, e=None):
        frame = self.active_frame()
        if frame and not self.field.disabled:
            self.player.playing = False
            self.player.strip.navigator.end()
            self.focused = True
            self.target = (frame.id, self.player.view.board, self.player.view.session)
            self.player.render()

    def changed(self, e=None):
        if not self.focused:
            self.focus()

    async def save(self, e=None):
        if not self.focused or self.saving:
            return
        self.saving = True
        try:
            identifier, board, session = self.target
            await self.player.duration_editor.set_duration(identifier, self.field.value or '', board, session)
            self.target = (identifier, self.player.view.board, self.player.view.session)
            frame = self.active_frame()
            if frame and frame.id == identifier:
                self.field.value = duration_text(frame.duration, self.player.view.board.fps, frames=True)
            self.field.error_text = None
            self.focused = False
            self.target = None
            self.player.focus_timeline()
        except ValueError as exc:
            self.field.error_text = str(exc)
        finally:
            self.saving = False
            self.sync()
            if self.player.opened:
                self.player.view.page.update(self.field)

    def cancel(self, e=None):
        self.focused = False
        self.target = None
        self.field.error_text = None
        self.sync()
        if self.player.opened:
            self.player.view.page.update(self.field)

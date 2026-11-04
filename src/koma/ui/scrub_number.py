"""Reusable numeric readout: drag to preview, click to type, release to confirm."""
from inspect import isawaitable
import flet as ft
from koma.expressions import arithmetic_value
from koma.ui.design import COMPACT_CONTROL_HEIGHT, BORDER, APP_PADDING, input_style, DRAG_INTERVAL_MS
from koma.ui.typography import TEXT_BODY
from koma.ui.event_updates import explicit_updates


class ScrubNumber:
    def __init__(self, page, *, label, minimum, maximum, sensitivity, on_begin, on_preview,
                 on_commit, on_cancel, on_submit, on_focus, on_blur):
        self.page, self.minimum, self.maximum, self.sensitivity = page, minimum, maximum, sensitivity
        self.on_begin, self.on_preview, self.on_commit, self.on_cancel = on_begin, on_preview, on_commit, on_cancel
        self.origin = self.start = self.current = None
        self.entry = ft.TextField(tooltip=label, visible=False, on_focus=on_focus, on_blur=on_blur,
            on_submit=self.submit, **input_style(COMPACT_CONTROL_HEIGHT))
        self.submit_action = on_submit
        self.text = ft.Text(size=TEXT_BODY, max_lines=1)
        self.readout = ft.GestureDetector(on_tap=self.edit, on_pan_down=self.press, on_pan_start=self.begin,
            on_pan_update=self.move, on_pan_end=self.finish, on_pan_cancel=self.cancel,
            drag_interval=DRAG_INTERVAL_MS, mouse_cursor=ft.MouseCursor.RESIZE_LEFT_RIGHT,
            content=ft.Container(height=COMPACT_CONTROL_HEIGHT, padding=ft.Padding.symmetric(horizontal=APP_PADDING * 2),
                alignment=ft.Alignment.CENTER_RIGHT, border=ft.Border.all(1, BORDER), content=self.text))
        self.content = ft.Container(width=112, height=COMPACT_CONTROL_HEIGHT,
            content=ft.Stack([self.entry, self.readout], fit=ft.StackFit.EXPAND))

    def sync(self):
        self.text.value = self.entry.value

    def set_editing(self, editing):
        self.entry.visible = editing
        self.readout.visible = not editing

    async def edit(self, e=None):
        self.set_editing(True)
        self.page.update(self.content)
        await self.entry.focus()

    async def submit(self, e=None):
        result = self.submit_action(e)
        if isawaitable(result):
            result = await result
        if result is not False:
            self.set_editing(False)
            self.sync()
            self.page.update(self.content)

    @explicit_updates
    def press(self, e):
        self.origin = e.global_position.x

    @explicit_updates
    def begin(self, e):
        try:
            self.start = arithmetic_value(self.entry.value or '')
        except ValueError:
            return
        if self.on_begin() is False:
            self.start = None
            return
        self.origin = e.global_position.x if self.origin is None else self.origin
        self.current = self.start

    @explicit_updates
    def move(self, e):
        if self.start is None:
            return
        value = max(self.minimum, min(self.maximum, self.start + (e.global_position.x - self.origin) * self.sensitivity))
        if value != self.current:
            self.current = value
            self.entry.value = f'{value:.6g}'
            self.sync()
            self.on_preview(value)
            self.page.update(self.text)

    @explicit_updates
    async def finish(self, e=None):
        if self.start is None:
            return
        if e is not None and getattr(e, 'global_position', None) is not None:
            self.move(e)
        value = self.current
        self.start = self.origin = None
        result = self.on_commit(value)
        if isawaitable(result):
            await result

    @explicit_updates
    def cancel(self, e=None):
        if self.start is not None:
            self.start = self.origin = None
            self.on_cancel()

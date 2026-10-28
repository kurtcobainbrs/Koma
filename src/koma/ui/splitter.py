"""Immediate draggable dividers, separate from editor commands."""
import flet as ft
from koma.ui.design import BORDER, APP_PADDING, DRAG_INTERVAL_MS


class Splitter:
    def __init__(self, page, target, *, horizontal=False, minimum=120, maximum=600, reverse=False):
        self.page, self.target = page, target
        self.horizontal, self.minimum, self.maximum, self.reverse = horizontal, minimum, maximum, reverse
        self.origin = self.value = None
        self.user_resized = False
        self.content = ft.GestureDetector(on_pan_start=self.begin, on_pan_update=self.move,
            on_pan_end=self.end, on_pan_cancel=self.cancel, drag_interval=DRAG_INTERVAL_MS,
            mouse_cursor=ft.MouseCursor.RESIZE_UP_DOWN if horizontal else ft.MouseCursor.RESIZE_LEFT_RIGHT,
            content=ft.Container(bgcolor=BORDER, height=APP_PADDING if horizontal else None,
                width=None if horizontal else APP_PADDING))

    def begin(self, e):
        self.origin = e.global_position.y if self.horizontal else e.global_position.x
        self.value = (self.target.height if self.horizontal else self.target.width) or self.minimum

    def move(self, e):
        if self.origin is None:
            return
        point = e.global_position.y if self.horizontal else e.global_position.x
        available = self.page.height if self.horizontal else self.page.width
        maximum = min(self.maximum, available * .65) if type(available) in (int, float) else self.maximum
        value = max(self.minimum, min(maximum, round(self.value + (point - self.origin) * (-1 if self.reverse else 1))))
        current = self.target.height if self.horizontal else self.target.width
        if current == value and (not self.horizontal or self.target.expand is False):
            return
        self.user_resized = True
        if self.horizontal:
            self.target.height, self.target.expand = value, False
        else:
            self.target.width = value
        self.page.update(self.target)

    def end(self, e=None):
        # The release position may be newer than the last throttled update.
        if e is not None:
            self.move(e)
        self.cancel()

    def cancel(self, e=None):
        self.origin = self.value = None

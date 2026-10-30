"""Bounded numeric editor: precise entry, step buttons and optional slider."""
import flet as ft
from koma.ui.design import input_style
from koma.ui.event_updates import explicit_updates
from koma.ui.form_layout import FORM_LAYOUT, form_row


class NumberInput:
    VALUE_WIDTH = FORM_LAYOUT.value_width

    def __init__(self, page, label, value, *, validate, minimum, maximum,
                 integer=True, slider=False, on_change, on_submit=None):
        self.page, self.validate, self.on_change = page, validate, on_change
        self.minimum, self.maximum, self.integer = minimum, maximum, integer
        self.step = 1 if integer else .1
        self.entry = ft.TextField(value=str(value), width=self.VALUE_WIDTH,
            text_align=ft.TextAlign.RIGHT, on_change=self.changed,
            on_submit=on_submit, **input_style(FORM_LAYOUT.row_height))
        self.slider = ft.Slider(min=minimum, max=maximum, value=value,
            divisions=round(maximum - minimum) if integer else None,
            width=FORM_LAYOUT.slider_width, height=FORM_LAYOUT.row_height,
            on_change=self.slid, on_change_end=self.slid) if slider else None
        self.less = ft.IconButton(ft.Icons.REMOVE, tooltip='Diminuir', on_click=lambda e: self.adjust(-1),
            width=FORM_LAYOUT.row_height, height=FORM_LAYOUT.row_height)
        self.more = ft.IconButton(ft.Icons.ADD, tooltip='Aumentar', on_click=lambda e: self.adjust(1),
            width=FORM_LAYOUT.row_height, height=FORM_LAYOUT.row_height)
        editor = [self.slider, self.entry] if self.slider else [self.less, self.entry, self.more]
        self.content = form_row(label, *editor)
        self.sync_bounds(value)

    @property
    def value(self):
        return self.entry.value

    @value.setter
    def value(self, value):
        number = self.validate(value)
        self.entry.value = str(number)
        self.entry.error_text = None
        self.sync_bounds(number)

    @property
    def error_text(self):
        return self.entry.error_text

    @error_text.setter
    def error_text(self, value):
        self.entry.error_text = value

    def sync_bounds(self, number):
        self.less.disabled, self.more.disabled = number <= self.minimum, number >= self.maximum
        if self.slider:
            self.slider.value = number

    def changed(self, e=None):
        try:
            self.sync_bounds(self.validate(self.value))
        except ValueError:
            pass
        self.on_change(e)

    @explicit_updates
    def adjust(self, direction):
        try:
            number = self.validate(self.value)
        except ValueError:
            return
        self.value = min(self.maximum, max(self.minimum, round(number + direction * self.step, 6)))
        self.on_change(None)

    @explicit_updates
    def slid(self, e):
        self.value = round(e.control.value) if self.integer else round(e.control.value, 2)
        self.on_change(e)

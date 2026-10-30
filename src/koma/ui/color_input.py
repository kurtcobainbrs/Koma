"""Compact color field sharing the application's picker and validation contract."""
import flet as ft
from koma.ui.color_picker import ColorPicker
from koma.ui.design import BORDER, RADIUS, input_style
from koma.ui.form_layout import FORM_LAYOUT, form_row


class ColorInput:
    SWATCH_WIDTH = FORM_LAYOUT.swatch_width
    CODE_WIDTH = FORM_LAYOUT.value_width

    def __init__(self, page, label, value, *, validate, on_change, on_submit=None):
        self.page, self.label = page, label
        self.validate, self.on_change = validate, on_change
        self.confirmed = value
        self.picker = None
        self.code = ft.TextField(value=value, width=self.CODE_WIDTH,
            tooltip='Código hexadecimal · #RRGGBB', on_change=self.changed,
            on_submit=on_submit, **input_style(FORM_LAYOUT.row_height))
        self.swatch = ft.Container(width=self.SWATCH_WIDTH, height=FORM_LAYOUT.row_height,
            bgcolor=value, border_radius=RADIUS, border=ft.Border.all(1, BORDER),
            tooltip=f'Escolher cor · {label}', on_click=self.open,
            content=ft.Container())
        self.content = form_row(label, self.swatch, self.code)

    @property
    def value(self):
        return self.code.value

    @value.setter
    def value(self, value):
        self.confirmed = self.validate(value)
        self.code.value = self.confirmed
        self.swatch.bgcolor = self.confirmed
        self.code.error_text = None

    @property
    def error_text(self):
        return self.code.error_text

    @error_text.setter
    def error_text(self, value):
        self.code.error_text = value

    def changed(self, e=None):
        try:
            self.confirmed = self.validate(self.value)
            self.swatch.bgcolor = self.confirmed
        except ValueError:
            pass  # The owning form displays validation and prevents saving.
        self.on_change(e)

    def apply(self, color):
        self.value = color
        self.on_change(None)

    def open(self, e=None):
        self.picker = ColorPicker(self.page, self.label, self.confirmed, self.apply)
        self.picker.open()

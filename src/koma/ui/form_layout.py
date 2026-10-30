"""Shared density and alignment for compact settings forms."""
from dataclasses import dataclass
import flet as ft
from koma.ui.design import APP_PADDING, COMPACT_CONTROL_HEIGHT
from koma.ui.typography import TEXT_BODY


@dataclass(frozen=True)
class FormLayout:
    row_height: int = COMPACT_CONTROL_HEIGHT
    spacing: int = APP_PADDING
    value_width: int = COMPACT_CONTROL_HEIGHT * 3
    text_width: int = COMPACT_CONTROL_HEIGHT * 7
    slider_width: int = COMPACT_CONTROL_HEIGHT * 5
    swatch_width: int = COMPACT_CONTROL_HEIGHT * 1.5
    sample_height: int = COMPACT_CONTROL_HEIGHT * 2


FORM_LAYOUT = FormLayout()


def form_row(label, *controls):
    return ft.Row([ft.Text(label, size=TEXT_BODY, expand=True), *controls],
        spacing=FORM_LAYOUT.spacing, vertical_alignment=ft.CrossAxisAlignment.CENTER)

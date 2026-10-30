"""Compact choice field using the shared desktop menu, without Material field overflow."""
import flet as ft
from koma.ui.design import APP_PADDING, BORDER, RADIUS
from koma.ui.form_layout import FORM_LAYOUT, form_row
from koma.ui.menus import menu_item, popup_menu, MENU_ICON_SIZE
from koma.ui.typography import TEXT_BODY


class ChoiceInput:
    def __init__(self, label, value, choices, *, on_change):
        self._value, self.on_change = value, on_change
        self.error_text = None
        self.text = ft.Text(str(value), size=TEXT_BODY, expand=True, max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS)
        def choose(option):
            def selected(e):
                self.value = option
                self.on_change(e)
            return selected
        self.button = popup_menu(tooltip=label, width=FORM_LAYOUT.text_width,
            height=FORM_LAYOUT.row_height, padding=0,
            content=ft.Container(height=FORM_LAYOUT.row_height,
                padding=ft.Padding.symmetric(horizontal=APP_PADDING * 2),
                border=ft.Border.all(1, BORDER), border_radius=RADIUS,
                content=ft.Row([self.text, ft.Icon(ft.Icons.EXPAND_MORE, size=MENU_ICON_SIZE)],
                    spacing=APP_PADDING)),
            items=[menu_item(str(option), on_click=choose(option)) for option in choices])
        self.content = form_row(label, self.button)

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self._value = value
        self.text.value = str(value)

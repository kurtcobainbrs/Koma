"""Compact disclosure section with immediate visibility changes."""

import flet as ft

from koma.ui.design import BORDER, COMPACT_CONTROL_HEIGHT
from koma.ui.menus import menu_button_style
from koma.ui.typography import FONT_HEADING, TEXT_BODY


class CollapsibleSection:
    def __init__(self, page, title, controls, *, expanded=True, on_change=None):
        self.page, self.expanded, self.on_change = page, expanded, on_change
        self.body = ft.Column(controls, spacing=6, visible=expanded,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        self.button = ft.TextButton(title, icon=self._icon(), height=COMPACT_CONTROL_HEIGHT,
            style=menu_button_style().copy(text_style=ft.TextStyle(
                size=TEXT_BODY, font_family=FONT_HEADING), alignment=ft.Alignment.CENTER_LEFT),
            on_click=self.toggle)
        self.content = ft.Column([ft.Divider(height=1, color=BORDER), self.button, self.body],
            spacing=4, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

    def _icon(self):
        return ft.Icons.EXPAND_MORE if self.expanded else ft.Icons.CHEVRON_RIGHT

    def toggle(self, e=None):
        self.expanded = not self.expanded
        self.body.visible = self.expanded
        self.button.icon = self._icon()
        if self.on_change:
            self.on_change(self.expanded)
        self.page.update(self.content)

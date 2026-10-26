"""Hierarquia e agrupamento dos controles do player, sem lógica de edição."""

import flet as ft

from koma.ui.design import APP_PADDING


class PlayerToolbar:
    def __init__(self, caption, duration, transport, clock, fps, history, zoom):
        self.commands = ft.Row([transport, clock, ft.Container(content=caption, expand=True),
            duration, fps, history, zoom], spacing=APP_PADDING * 2,
            vertical_alignment=ft.CrossAxisAlignment.CENTER)

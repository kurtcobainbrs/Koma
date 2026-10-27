"""Hierarquia e agrupamento dos controles do player, sem lógica de edição."""

import flet as ft

from koma.ui.design import APP_PADDING


class PlayerToolbar:
    def __init__(self, duration, transport, clock, fps, history, zoom, toggles, marker_tools):
        playback = ft.Row([transport, *toggles], tight=True, spacing=APP_PADDING)
        self.tools = ft.Row([history, zoom, marker_tools], wrap=True,
            spacing=APP_PADDING * 2, run_spacing=APP_PADDING)
        editing = ft.Row([clock, duration, fps], wrap=True,
            alignment=ft.MainAxisAlignment.END, spacing=APP_PADDING,
            run_spacing=APP_PADDING)
        # Equal flexible sides keep playback centered, even with unequal labels.
        self.commands = ft.Row([ft.Container(content=self.tools, expand=True), playback,
            ft.Container(content=editing, expand=True)], spacing=APP_PADDING * 2,
            vertical_alignment=ft.CrossAxisAlignment.CENTER)

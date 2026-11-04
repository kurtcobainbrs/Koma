"""Hierarquia e agrupamento dos controles do player, sem lógica de edição."""

import flet as ft

from koma.ui.design import APP_PADDING

PLAYBACK_SIZE = 24
PLAYBACK_ICON_SIZE = 16


class PlayerToolbar:
    def __init__(self, duration, transport, clock, fps, history, zoom, toggles, marker_tools, *, animation=None):
        def separator():
            return ft.Container(width=1, height=PLAYBACK_ICON_SIZE, bgcolor=ft.Colors.OUTLINE_VARIANT,
                margin=ft.Margin.symmetric(horizontal=APP_PADDING))
        for button in [*transport.controls, *toggles, *(animation.controls if animation else [])]:
            button.height = PLAYBACK_SIZE
            if isinstance(button, ft.IconButton):
                button.width, button.icon_size = PLAYBACK_SIZE, PLAYBACK_ICON_SIZE
                button.style = ft.ButtonStyle(animation_duration=0, padding=0, enable_feedback=False,
                    shape=ft.RoundedRectangleBorder(radius=2))
        self.playback = ft.Row([*([animation, separator()] if animation else []), transport, separator(), *toggles],
            tight=True, spacing=0, height=PLAYBACK_SIZE)
        self.tools = ft.Row([history, zoom, marker_tools], wrap=True,
            spacing=APP_PADDING * 2, run_spacing=APP_PADDING)
        editing = ft.Row([clock, duration, fps], wrap=True,
            alignment=ft.MainAxisAlignment.END, spacing=APP_PADDING,
            run_spacing=APP_PADDING)
        # Equal flexible sides keep playback centered, even with unequal labels.
        self.commands = ft.Row([ft.Container(content=self.tools, expand=True), self.playback,
            ft.Container(content=editing, expand=True)], spacing=APP_PADDING * 2,
            vertical_alignment=ft.CrossAxisAlignment.CENTER)

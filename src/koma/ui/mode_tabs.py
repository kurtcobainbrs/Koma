"""Compact mode navigation; callers own actions, availability and active state."""
from dataclasses import dataclass
from typing import Callable
import flet as ft
from koma.ui.design import COMPACT_CONTROL_HEIGHT, RADIUS, MUTED
from koma.ui.workspace_style import WORKSPACE_STYLE


@dataclass(frozen=True)
class ModeTab:
    key: str
    label: str
    action: Callable
    tooltip: str = ''


class ModeTabs:
    def __init__(self, tabs):
        self.buttons = {tab.key: ft.TextButton(tab.label, on_click=tab.action,
            tooltip=tab.tooltip, width=WORKSPACE_STYLE.mode_tab_width,
            height=COMPACT_CONTROL_HEIGHT) for tab in tabs}
        self.content = ft.Container(bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
            border_radius=RADIUS, height=COMPACT_CONTROL_HEIGHT,
            content=ft.Row(list(self.buttons.values()), spacing=0, tight=True))

    def select(self, active):
        for key, button in self.buttons.items():
            button.style = ft.ButtonStyle(animation_duration=0, enable_feedback=False,
                padding=ft.Padding.symmetric(horizontal=8),
                shape=ft.RoundedRectangleBorder(radius=RADIUS),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH if key == active else ft.Colors.TRANSPARENT,
                color=ft.Colors.ON_SURFACE if key == active else MUTED,
                overlay_color=ft.Colors.TRANSPARENT,
                side=ft.BorderSide(0, ft.Colors.TRANSPARENT))

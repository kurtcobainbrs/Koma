"""Composição visual compartilhada; sem estado de ferramentas ou acesso a disco."""

import flet as ft

from koma.ui.design import BORDER, CONTROL_HEIGHT, COMPACT_CONTROL_HEIGHT, ICON_SIZE, MUTED, PANEL_PADDING, RADIUS, SURFACE, SELECTION
from koma.ui.typography import FONT_HEADING, TEXT_BODY, TEXT_SMALL, TEXT_TITLE
from koma.ui.design import EDITOR_SURFACE_BORDER, EDITOR_SURFACE_PADDING


def drag_feedback(content: ft.Control) -> ft.Card:
    """Give drag overlays the theme's Material text defaults, without a border or shadow."""
    return ft.Card(content=content, margin=0, elevation=0, bgcolor=SURFACE,
        shape=ft.RoundedRectangleBorder(radius=0))


def toggle_icon(icon, selected_icon, on_click, *, selected=False):
    """Compact on/off button with instant, theme-aware selected feedback."""
    return ft.IconButton(icon=icon, selected_icon=selected_icon, selected=selected,
        icon_color=MUTED, selected_icon_color=ft.Colors.PRIMARY,
        width=COMPACT_CONTROL_HEIGHT, height=COMPACT_CONTROL_HEIGHT, icon_size=ICON_SIZE,
        style=ft.ButtonStyle(animation_duration=0,
            bgcolor={ft.ControlState.SELECTED: SELECTION}), on_click=on_click)


def list_surface(controls: list[ft.Control], *, expand=True) -> ft.Container:
    """Delimita a região rolável, com contraste neutro e tokens do tema ativo."""
    return ft.Container(expand=expand, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
        border=ft.Border.all(EDITOR_SURFACE_BORDER, BORDER), border_radius=RADIUS, padding=EDITOR_SURFACE_PADDING,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        content=ft.Column(controls, expand=expand, spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH))

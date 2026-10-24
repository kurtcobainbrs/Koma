"""Composição visual compartilhada; sem estado de ferramentas ou acesso a disco."""

import flet as ft

from koma.ui.design import BORDER, CONTROL_HEIGHT, MUTED, PANEL_PADDING, RADIUS, SURFACE
from koma.ui.typography import FONT_HEADING, TEXT_BODY, TEXT_SMALL, TEXT_TITLE


def list_surface(controls: list[ft.Control], *, expand=True) -> ft.Container:
    """Delimita a região rolável, com contraste neutro e tokens do tema ativo."""
    return ft.Container(expand=expand, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
        border=ft.Border.all(1, BORDER), border_radius=RADIUS, padding=6,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        content=ft.Column(controls, expand=expand, spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH))

"""Shared desktop menu density and motion policy."""

from dataclasses import field

import flet as ft
from flet.controls.base_control import control

from koma.ui.design import BORDER, SURFACE
from koma.ui.typography import TEXT_BODY

MENU_ITEM_HEIGHT = 26
MENU_ICON_SIZE = 16
MENU_HORIZONTAL_PADDING = 8
MENU_VERTICAL_PADDING = 2
MENU_RADIUS = 2


def menu_item(content=None, **kwargs):
    defaults = dict(height=MENU_ITEM_HEIGHT,
        padding=ft.Padding.symmetric(horizontal=MENU_HORIZONTAL_PADDING),
        label_text_style=ft.TextStyle(size=TEXT_BODY))
    return ft.PopupMenuItem(content, **(defaults | kwargs))


def popup_menu(**kwargs):
    defaults = dict(popup_animation_style=ft.AnimationStyle.no_animation(),
        menu_padding=ft.Padding.symmetric(vertical=MENU_VERTICAL_PADDING),
        shape=ft.RoundedRectangleBorder(radius=MENU_RADIUS), elevation=0,
        bgcolor=SURFACE, icon_size=MENU_ICON_SIZE)
    return ft.PopupMenuButton(**(defaults | kwargs))


def menu_button_style():
    return ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=MENU_HORIZONTAL_PADDING),
        text_style=ft.TextStyle(size=TEXT_BODY), animation_duration=0,
        visual_density=ft.VisualDensity.COMPACT,
        shape=ft.RoundedRectangleBorder(radius=MENU_RADIUS))


def menu_panel_style():
    return ft.MenuStyle(bgcolor=SURFACE, elevation=0,
        padding=ft.Padding.symmetric(vertical=MENU_VERTICAL_PADDING),
        side=ft.BorderSide(1, BORDER),
        shape=ft.RoundedRectangleBorder(radius=MENU_RADIUS))


@control('koma_context_menu')
class DesktopContextMenu(ft.ContextMenu):
    """Native positioned popup with the same explicit motion policy as buttons.

    Flet 1.0.5 exposes popup animation style only on PopupMenuButton.
    The bundled Flutter adapter provides that policy for ContextMenu as well.
    """

    menu_padding: ft.PaddingValue = field(default_factory=lambda:
        ft.Padding.symmetric(vertical=MENU_VERTICAL_PADDING))
    bgcolor: str = SURFACE
    shape: ft.OutlinedBorder = field(default_factory=lambda:
        ft.RoundedRectangleBorder(radius=MENU_RADIUS))

    async def close(self):
        await self._invoke_method('close')

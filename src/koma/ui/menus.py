"""Shared desktop menu density and motion policy."""

from dataclasses import dataclass, field
from inspect import isawaitable
from collections.abc import Callable

import flet as ft
from flet.controls.base_control import control

from koma.ui.design import BORDER, SURFACE, COMPACT_CONTROL_HEIGHT
from koma.ui.typography import TEXT_BODY

MENU_ITEM_HEIGHT = 26
MENU_ICON_SIZE = 16
MENU_HORIZONTAL_PADDING = 8
MENU_VERTICAL_PADDING = 2
MENU_RADIUS = 2


@dataclass(frozen=True)
class MenuGroup:
    items: tuple = ()
    load: Callable | None = None
    key: Callable | None = None


@dataclass(frozen=True)
class MenuSeparator:
    pass


def submenu(label, items=(), *, load=None, key=None, icon=None):
    return menu_item(label, icon=icon, data=MenuGroup(tuple(items), load, key))


def menu_separator():
    return menu_item('', data=MenuSeparator())


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


def icon_menu(options, on_select, *, icon, tooltip, size=COMPACT_CONTROL_HEIGHT, icon_size=MENU_ICON_SIZE):
    """Icon-only choices use a content-sized menu instead of Material's text width."""
    def choose(value):
        async def selected(e):
            result = on_select(value)
            if isawaitable(result):
                await result
        return selected
    width = size + MENU_HORIZONTAL_PADDING * 2
    return popup_menu(icon=icon, tooltip=tooltip, width=size, height=size, padding=0,
        size_constraints=ft.BoxConstraints(min_width=width, max_width=width),
        items=[menu_item(content=ft.Container(width=size, alignment=ft.Alignment.CENTER,
            content=ft.Icon(choice_icon, size=icon_size)), tooltip=label, on_click=choose(value), height=size)
            for value, label, choice_icon in options])


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
    size_constraints: ft.BoxConstraints | None = None
    open_at_pointer: bool = False

    async def close(self):
        await self._invoke_method('close')


class ShortcutToolMenu:
    """Keyboard-opened icon list; tools dispatch to their existing commands."""
    def __init__(self, page, content, options, on_select, *, on_closed):
        self.page, self.on_closed = page, on_closed
        self.opened = False
        width = MENU_ICON_SIZE + MENU_HORIZONTAL_PADDING * 2
        def choose(value):
            async def selected(e):
                self.dismiss(refocus=False)
                result = on_select(value)
                if isawaitable(result):
                    await result
            return selected
        self.content = DesktopContextMenu(content=content,
            secondary_trigger=None, tertiary_trigger=None,
            open_at_pointer=True,
            size_constraints=ft.BoxConstraints(min_width=width, max_width=width),
            items=[menu_item(content=ft.Container(alignment=ft.Alignment.CENTER,
                content=icon), tooltip=label, on_click=choose(value))
                for value, label, icon in options],
            on_select=self.dismiss, on_dismiss=self.dismiss)

    async def show(self):
        if self.opened:
            return
        self.opened = True
        try:
            await self.content.open()
        except Exception:
            self.opened = False
            raise

    def dismiss(self, e=None, *, refocus=True):
        if not self.opened:
            return
        self.opened = False
        if refocus:
            self.on_closed()

    def close(self):
        if self.opened:
            self.dismiss()
            self.page.run_task(self.content.close)

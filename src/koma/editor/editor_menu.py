"""Barra de menus desktop compartilhada: troca direta e abertura sem transição."""

import flet as ft

from koma.ui.design import COMPACT_CONTROL_HEIGHT, MUTED, BORDER
from koma.ui.typography import TEXT_BODY
from koma.ui.menus import MENU_ITEM_HEIGHT, MENU_ICON_SIZE, MENU_VERTICAL_PADDING, MenuGroup, MenuSeparator, menu_button_style, menu_panel_style


class _MenuEntry:
    """Bind a command tree to native entries, including lazily refreshed lists."""
    def __init__(self, command):
        self.command = command
        self.children = []
        self.key = object()
        self.check = None
        leading = ft.Icon(command.icon, size=MENU_ICON_SIZE) if command.icon else None
        if isinstance(command.data, MenuSeparator):
            self.control = ft.Divider(height=MENU_VERTICAL_PADDING * 2, thickness=1, color=BORDER)
        elif isinstance(command.data, MenuGroup):
            self.control = ft.SubmenuButton(content=ft.Text(command.content, size=TEXT_BODY),
                leading=leading, height=MENU_ITEM_HEIGHT, style=menu_button_style(),
                menu_style=menu_panel_style(), on_open=self.opened)
        else:
            self.check = ft.Icon(ft.Icons.CHECK, size=MENU_ICON_SIZE, color=MUTED)
            self.control = ft.MenuItemButton(content=ft.Text(command.content, size=TEXT_BODY),
                leading=leading, trailing=self.check, height=MENU_ITEM_HEIGHT,
                style=menu_button_style(), on_click=command.on_click)
        self.sync()

    def sync(self, *, force=False):
        command = self.command
        if isinstance(command.data, MenuSeparator):
            return
        self.control.content.value = command.content
        self.control.disabled = bool(command.disabled)
        self.control.tooltip = command.tooltip
        if self.check is not None:
            self.check.visible = bool(command.checked)
            return
        group = command.data
        key = group.key() if group.key else None
        if force or key != self.key:
            self.key = key
            commands = group.load() if group.load else group.items
            self.children = [_MenuEntry(child) for child in commands]
            self.control.controls = [child.control for child in self.children]
        for child in self.children:
            child.sync()

    def opened(self, e=None):
        self.sync(force=True)
        if e is not None:
            e.control.page.update(e.control)


class EditorMenuBar:
    def __init__(self, sources):
        self.entries = []
        self.menus = []
        for source, is_file in sources:
            entries = [_MenuEntry(command) for command in source.items]
            self.entries.extend(entries)
            target = ft.SubmenuButton(content=ft.Text(source.content.content.value, size=TEXT_BODY),
                controls=[entry.control for entry in entries], height=COMPACT_CONTROL_HEIGHT,
                style=menu_button_style(), menu_style=menu_panel_style())
            self.menus.append((source, target, is_file))
        # MenuBar mantém os menus no mesmo grupo de navegação, sem rota modal
        # que consumiria o primeiro clique em outro título.
        self.content = ft.MenuBar(controls=[target for _, target, _ in self.menus],
            style=ft.MenuStyle(bgcolor=ft.Colors.TRANSPARENT, elevation=0, padding=0))

    def sync(self, toolbar_disabled=False):
        for source, target, is_file in self.menus:
            target.disabled = bool(source.disabled or (toolbar_disabled and not is_file))
        for entry in self.entries:
            entry.sync()

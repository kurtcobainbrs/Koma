"""Barra de menus desktop compartilhada: troca direta e abertura sem transição."""

import flet as ft

from koma.ui.design import COMPACT_CONTROL_HEIGHT, MUTED
from koma.ui.typography import TEXT_BODY
from koma.ui.menus import MENU_ITEM_HEIGHT, MENU_ICON_SIZE, menu_button_style, menu_panel_style


class EditorMenuBar:
    def __init__(self, sources):
        self.entries = []
        self.menus = []
        button_style = menu_button_style()
        menu_style = menu_panel_style()
        for source, is_file in sources:
            entries = []
            for command in source.items:
                check = ft.Icon(ft.Icons.CHECK, size=MENU_ICON_SIZE, color=MUTED, visible=bool(command.checked))
                entry = ft.MenuItemButton(content=ft.Text(command.content, size=TEXT_BODY),
                    leading=ft.Icon(command.icon, size=MENU_ICON_SIZE) if command.icon else None,
                    trailing=check, height=MENU_ITEM_HEIGHT, style=button_style, on_click=command.on_click)
                entries.append(entry)
                self.entries.append((command, entry, check))
            target = ft.SubmenuButton(content=ft.Text(source.content.content.value, size=TEXT_BODY),
                controls=entries, height=COMPACT_CONTROL_HEIGHT,
                style=button_style, menu_style=menu_style)
            self.menus.append((source, target, is_file))
        # MenuBar mantém os menus no mesmo grupo de navegação, sem rota modal
        # que consumiria o primeiro clique em outro título.
        self.content = ft.MenuBar(controls=[target for _, target, _ in self.menus],
            style=ft.MenuStyle(bgcolor=ft.Colors.TRANSPARENT, elevation=0, padding=0))

    def sync(self, toolbar_disabled=False):
        for source, target, is_file in self.menus:
            target.disabled = bool(source.disabled or (toolbar_disabled and not is_file))
        for command, entry, check in self.entries:
            entry.content.value = command.content
            entry.disabled = bool(command.disabled)
            check.visible = bool(command.checked)

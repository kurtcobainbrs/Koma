"""Menus e barras do editor; não contém regras de nodes ou persistência."""

import flet as ft

from koma.ui.design import BORDER, COMPACT_CONTROL_HEIGHT, RADIUS, SURFACE, dialog, input_style
from koma.ui.typography import TEXT_BODY
from koma.editor.editor_menu import EditorMenuBar
from koma.editor.node_types import NODE_TYPES
from koma.editor.shortcuts import Action


def item(label, handler, icon=None):
    return ft.PopupMenuItem(label, icon=icon, on_click=handler, height=32,
        label_text_style=ft.TextStyle(size=TEXT_BODY))


def menu(label, items):
    return ft.PopupMenuButton(content=menu_label(label), items=items,
        padding=ft.Padding.symmetric(horizontal=8, vertical=4), height=COMPACT_CONTROL_HEIGHT,
        menu_position=ft.PopupMenuPosition.UNDER)


def menu_label(label):
    return ft.Container(content=ft.Text(label, size=TEXT_BODY),
        padding=ft.Padding.symmetric(horizontal=8, vertical=4))


class StoryboardChrome:
    def __init__(self, view):
        self.view, self.page = view, view.page
        self.nav, self.workspace = view.workspace.navigation, view.workspace
        self.shortcut_items = []
        self.wide = True
        self.compact = False
        self.edit_items = [self.shortcut_item('Desfazer', Action.UNDO, view.graph.undo, ft.Icons.UNDO),
            self.shortcut_item('Refazer', Action.REDO, view.graph.redo, ft.Icons.REDO),
            self.shortcut_item('Colar imagem', Action.PASTE, view.image_input.paste, ft.Icons.CONTENT_PASTE),
            self.shortcut_item('Duplicar', Action.DUPLICATE, self.nav.duplicate_selected, ft.Icons.CONTENT_COPY),
            self.shortcut_item('Excluir', Action.DELETE, self.nav.delete_selected, ft.Icons.DELETE_OUTLINE),
            self.shortcut_item('Mover', Action.MOVE, self.workspace.grab.start, ft.Icons.OPEN_WITH)]
        self.edit_menu = menu('Editar', self.edit_items)
        self.snap_item = item('Ajustar à grade', self.workspace.toggle_snap, ft.Icons.GRID_ON)
        self.tools_item = item('Ferramentas', self.toggle_tools)
        self.props_item = self.shortcut_item('Propriedades', Action.PROPERTIES, view.properties.toggle, ft.Icons.TUNE)
        self.view_menu = menu('Exibir', [self.shortcut_item('Enquadrar tudo', Action.FIT, self.workspace.fit, ft.Icons.FIT_SCREEN),
            self.shortcut_item('Enquadrar seleção', Action.FOCUS, self.nav.focus_selected, ft.Icons.CENTER_FOCUS_STRONG),
            item('Zoom 100%', self.workspace.reset, ft.Icons.ZOOM_IN), self.snap_item, self.tools_item, self.props_item])
        self.selection_menu = menu('Seleção', [self.shortcut_item('Todos', Action.ALL, self.select_all),
            self.shortcut_item('Nenhum', Action.NONE, self.select_none), item('Inverter', self.invert)])
        self.add_menu = menu('Inserir', [
            *[item(spec.label, view.node_handler(spec.kind),
                ft.Icons.MOVIE_OUTLINED if spec.starts_scene else ft.Icons.ADD)
              for spec in NODE_TYPES.values()],
            item('Importar imagens…', view.pick_images, ft.Icons.ADD_PHOTO_ALTERNATE_OUTLINED)])
        self.shortcut_items.append((view.graph.menu.items[0], 'Criar moldura', Action.GROUP))
        self.node_menu = view.graph.menu
        self.node_menu.icon = None
        self.node_menu.content = menu_label('Fluxo')
        self.node_menu.height = COMPACT_CONTROL_HEIGHT
        self.node_menu.padding = ft.Padding.symmetric(horizontal=8, vertical=4)
        self.node_menu.menu_position = ft.PopupMenuPosition.UNDER
        self.node_menu.items.append(item('Organizar fluxo', view.graph.organize, ft.Icons.ACCOUNT_TREE_OUTLINED))
        for entry in self.node_menu.items:
            entry.height = 32
            entry.label_text_style = ft.TextStyle(size=TEXT_BODY)
        self.toolbar = ft.Row([self.edit_menu, self.view_menu, self.selection_menu, self.add_menu, self.node_menu],
            tight=True, spacing=0)
        files = view.files.menu
        files.content = menu_label('Arquivo')
        files.height = COMPACT_CONTROL_HEIGHT
        files.padding = ft.Padding.symmetric(horizontal=8, vertical=4)
        files.menu_position = ft.PopupMenuPosition.UNDER
        files.items.insert(0, item('Renomear…', self.rename, ft.Icons.EDIT_OUTLINED))
        for entry in files.items:
            entry.height = 32
            entry.label_text_style = ft.TextStyle(size=TEXT_BODY)
        self.menus = EditorMenuBar([(files, True),
            *[(source, False) for source in self.toolbar.controls]])
        self.play = ft.IconButton(icon=ft.Icons.PLAY_ARROW, icon_size=20,
            tooltip='Abrir animatic da cena ativa', width=COMPACT_CONTROL_HEIGHT, height=COMPACT_CONTROL_HEIGHT,
            on_click=view.player.open)
        view.properties.toggle_button.width = view.properties.toggle_button.height = COMPACT_CONTROL_HEIGHT
        self.content = ft.Container(bgcolor=SURFACE, border=ft.Border.all(1, BORDER), border_radius=RADIUS,
            padding=ft.Padding.symmetric(horizontal=4, vertical=2), on_size_change=self.resized,
            content=ft.Row([
                ft.Row([self.menus.content], expand=True, scroll=ft.ScrollMode.AUTO, spacing=0),
                self.play, view.properties.toggle_button,
            ], spacing=4, height=COMPACT_CONTROL_HEIGHT))
        # A seleção ocupa o rodapé; ações de edição ficam nos menus.
        selection = self.nav.selection_bar
        selection.left = selection.bottom = selection.top = None
        selection.width = 145
        selection.padding = 0
        selection.border = selection.bgcolor = None
        selection.content = ft.Row([self.nav.selection_count], tight=True)
        view.count.width, view.count.max_lines = 195, 1
        view.count.overflow = ft.TextOverflow.ELLIPSIS
        self.nav.tools.content.controls = list(self.nav.buttons.values())
        self.nav.focus_button.width = self.nav.focus_button.height = COMPACT_CONTROL_HEIGHT
        self.workspace.controls.controls.insert(0, self.nav.focus_button)
        # Barra independente de navegação, extensível com novas ferramentas do canvas.
        self.right_tools = ft.Container(right=10, top=10, padding=4, bgcolor=SURFACE,
            border=ft.Border.all(1, BORDER), border_radius=RADIUS,
            content=ft.Column([self.workspace.snap], tight=True, spacing=2))
        view.board_area.controls.append(self.right_tools)
        view.feedback.content.expand = True
        view.feedback.content.padding = 2
        view.feedback.content.border = None
        self.progress_slot = view.feedback.content.content.controls[-1]
        self.status = ft.Container(bgcolor=SURFACE, border=ft.Border.all(1, BORDER), border_radius=RADIUS,
            padding=ft.Padding.symmetric(horizontal=6, vertical=1), content=ft.Row([
                view.feedback.content, view.count, selection, self.workspace.controls,
            ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER))
        self.refresh_shortcuts()
        self.sync()

    def shortcut_item(self, title, action, handler, icon=None):
        entry = item(self.view.keymap.describe(title, action), handler, icon)
        self.shortcut_items.append((entry, title, action))
        return entry

    def refresh_shortcuts(self):
        for entry, title, action in self.shortcut_items:
            entry.content = self.view.keymap.describe(title, action)
        self.view.graph.undo_button.tooltip = self.view.keymap.describe('Desfazer', Action.UNDO)
        self.view.graph.redo_button.tooltip = self.view.keymap.describe('Refazer', Action.REDO)
        self.view.properties.toggle_button.tooltip = self.view.keymap.describe('Propriedades', Action.PROPERTIES)

    def sync(self):
        if self.view.loaded and not self.view.closing and self.view.on_state:
            self.view.on_state(self.view)
        self.edit_items[0].disabled = self.view.graph.undo_button.disabled
        self.edit_items[1].disabled = self.view.graph.redo_button.disabled
        selected = bool(self.nav.selection.ids)
        for entry in self.edit_items[2:]:
            entry.disabled = not selected
        active = next((frame for frame in self.view.board.frames if frame.id == self.nav.selected), None)
        self.edit_items[2].disabled = not active or not active.node_type.image
        for entry in self.node_menu.items[:3]:
            entry.disabled = not selected
        self.snap_item.checked = self.workspace.snap_enabled
        self.tools_item.checked = self.nav.tools.visible
        self.props_item.checked = self.view.properties.opened
        self.view.count.visible = self.wide and not selected
        self.nav.selection_bar.visible = selected
        self.play.disabled = not self.view.editable() or not self.view.board.frames
        self.menus.sync(self.toolbar.disabled)
        self.sync_status()

    def sync_status(self):
        self.progress_slot.visible = self.view.feedback.progress.visible

    def lock(self, busy):
        locked = busy or bool(self.view.load_error)
        self.toolbar.disabled = self.right_tools.disabled = locked
        self.play.disabled = locked or not self.view.board.frames
        self.view.properties.toggle_button.disabled = locked
        self.view.files.menu.disabled = busy
        self.menus.sync(self.toolbar.disabled)

    def resized(self, e):
        if e.width <= 0 or self.view.closing:
            return
        wide, compact = e.width >= 850, e.width < 600
        if wide != self.wide or compact != self.compact:
            self.wide = wide
            self.compact = compact
            self.nav.selection_bar.width = 110 if compact else 145
            self.nav.focus_button.visible = not compact
            for button in (self.workspace.zoom_out_button, self.workspace.zoom_in_button, self.workspace.fit_button):
                button.visible = not compact
            self.sync()
            self.page.update(self.content, self.status)

    def rename(self, e=None):
        if not self.view.editable():
            return
        field = ft.TextField(value=self.view.board.title, label='Nome do projeto', max_length=200,
            counter=ft.Container(width=0, height=0), **input_style())
        async def save(e):
            self.page.pop_dialog()
            self.view.title.value = field.value or ''
            await self.view.edit_title(None)
        self.page.show_dialog(dialog(title=ft.Text('Renomear projeto'), content=ft.Container(width=380, content=field),
            actions=[ft.TextButton('Cancelar', on_click=lambda e: self.page.pop_dialog()), ft.FilledButton('Salvar', on_click=save)]))

    def toggle_tools(self, e=None):
        self.nav.tools.visible = not self.nav.tools.visible
        self.sync()
        self.page.update(self.nav.tools, self.content)

    def select_all(self, e=None):
        self.nav.apply_selection(set(self.view.cards))
        self.nav.focus_keyboard()

    def select_none(self, e=None):
        self.nav.apply_selection(set())
        self.nav.focus_keyboard()

    def invert(self, e=None):
        self.nav.apply_selection(set(self.view.cards)-self.nav.selection.ids)
        self.nav.focus_keyboard()

"""Menus e barras do editor; não contém regras de nodes ou persistência."""
from koma.ui.event_updates import explicit_updates

import flet as ft

from koma.ui.design import BORDER, COMPACT_CONTROL_HEIGHT, RADIUS, SURFACE, dialog, input_style
from koma.ui.typography import TEXT_BODY
from koma.ui.menus import menu_item, popup_menu, submenu, menu_separator, MENU_ITEM_HEIGHT
from koma.editor.editor_menu import EditorMenuBar
from koma.editor.node_types import NODE_TYPES
from koma.editor.shortcuts import Action
from koma.ui.node_icons import node_icon
from koma.ui.workspace_style import WORKSPACE_STYLE
from inspect import isawaitable
from koma.ui.mode_tabs import ModeTab, ModeTabs
from koma.ui.filter_selector import FilterSelector


def item(label, handler, icon=None):
    return menu_item(label, icon=icon, on_click=handler)


def menu(label, items):
    return popup_menu(content=menu_label(label), items=items,
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
        self.edit_commands = {action: self.shortcut_item(label, action, self.edit_handler(action, handler), icon)
            for action, label, handler, icon in (
                (Action.UNDO, 'Desfazer', view.graph.undo, ft.Icons.UNDO),
                (Action.REDO, 'Refazer', view.graph.redo, ft.Icons.REDO),
                (Action.CUT_NODES, 'Recortar', self.cut_nodes, ft.Icons.CONTENT_CUT),
                (Action.COPY, 'Copiar', self.copy_nodes, ft.Icons.CONTENT_COPY),
                (Action.PASTE, 'Colar', self.paste_nodes, ft.Icons.CONTENT_PASTE),
                (Action.DUPLICATE, 'Duplicar', self.nav.duplicate_selected, ft.Icons.CONTROL_POINT_DUPLICATE),
                (Action.MOVE, 'Mover', self.workspace.grab.start, ft.Icons.OPEN_WITH),
                (Action.DELETE, 'Excluir', self.nav.delete_selected, ft.Icons.DELETE_OUTLINE))}
        edit = self.edit_commands
        self.edit_menu = menu('Editar', [edit[Action.UNDO], edit[Action.REDO], menu_separator(),
            edit[Action.CUT_NODES], edit[Action.COPY], edit[Action.PASTE], menu_separator(),
            edit[Action.DUPLICATE], edit[Action.MOVE], menu_separator(), edit[Action.DELETE],
            menu_separator(), item('Preferências…', self.open_preferences, ft.Icons.TUNE)])
        self.snap_item = item('Ajustar à grade', self.workspace.toggle_snap, ft.Icons.GRID_ON)
        self.tools_item = item('Ferramentas', self.toggle_tools, ft.Icons.BUILD_OUTLINED)
        self.props_item = self.shortcut_item('Propriedades', Action.PROPERTIES, view.properties.toggle, ft.Icons.TUNE)
        self.fit_all = self.shortcut_item('Enquadrar tudo', Action.FIT, self.fit_active, ft.Icons.FIT_SCREEN)
        self.fit_selection = self.shortcut_item('Enquadrar seleção', Action.FOCUS, self.nav.focus_selected, ft.Icons.CENTER_FOCUS_STRONG)
        self.reset_zoom = item('Zoom 100%', self.workspace.reset, ft.Icons.ZOOM_IN)
        self.canvas_view_commands = (self.fit_selection, self.reset_zoom, self.snap_item, self.tools_item)
        self.view_menu = menu('Exibir', [self.fit_all, self.fit_selection,
            self.reset_zoom, menu_separator(),
            self.snap_item, menu_separator(),
            submenu('Painéis', [self.props_item, self.tools_item,
                item('Mídias…', self.open_media, ft.Icons.PERM_MEDIA_OUTLINED)], icon=ft.Icons.VIEW_SIDEBAR_OUTLINED),
            self.shortcut_item('Localizar…', Action.SEARCH, lambda e: view.document_tools.search(), ft.Icons.SEARCH),
        ])
        self.selection_menu = menu('Seleção', [self.shortcut_item('Todos', Action.ALL, self.select_all, ft.Icons.SELECT_ALL),
            self.shortcut_item('Nenhum', Action.NONE, self.select_none, ft.Icons.DESELECT),
            item('Inverter', self.invert, ft.Icons.FLIP_TO_BACK)])
        self.import_items = [
            self.shortcut_item('Imagens…', Action.IMPORT_IMAGES, view.pick_images, ft.Icons.ADD_PHOTO_ALTERNATE_OUTLINED),
            item('Áudio…', self.import_audio, ft.Icons.AUDIO_FILE_OUTLINED),
            item('Projeto…', self.import_project, ft.Icons.FILE_OPEN_OUTLINED)]
        self.add_menu = menu('Inserir', [
            *[item(spec.label, view.node_handler(spec.kind), node_icon(spec))
              for spec in NODE_TYPES.values()],
            menu_separator(), submenu('Importar', self.import_items, icon=ft.Icons.FILE_DOWNLOAD_OUTLINED)])
        self.track_shortcut(view.graph.commands['group'], 'Criar moldura…', Action.GROUP)
        self.track_shortcut(view.graph.commands['sequence'], 'Criar sequência', Action.SEQUENCE)
        self.node_menu = view.graph.menu
        self.node_menu.icon = None
        self.node_menu.content = menu_label('Fluxo')
        self.node_menu.height = COMPACT_CONTROL_HEIGHT
        self.node_menu.padding = ft.Padding.symmetric(horizontal=8, vertical=4)
        self.node_menu.menu_position = ft.PopupMenuPosition.UNDER
        for entry in self.node_menu.items:
            entry.height = MENU_ITEM_HEIGHT
            entry.label_text_style = ft.TextStyle(size=TEXT_BODY)
        self.toolbar = ft.Row([self.edit_menu, self.view_menu, self.selection_menu, self.add_menu, self.node_menu],
            tight=True, spacing=0)
        files = view.files.menu
        files.content = menu_label('Arquivo')
        files.height = COMPACT_CONTROL_HEIGHT
        files.padding = ft.Padding.symmetric(horizontal=8, vertical=4)
        files.menu_position = ft.PopupMenuPosition.UNDER
        commands = view.files.commands
        self.recent_menu = submenu('Recentes', load=self.recent_items, key=self.recent_key, icon=ft.Icons.HISTORY)
        files.items = [
            self.track_shortcut(commands['new'], 'Novo', Action.NEW),
            self.track_shortcut(commands['open'], 'Abrir…', Action.OPEN), self.recent_menu, commands['recover'],
            menu_separator(),
            self.track_shortcut(commands['save'], 'Salvar', Action.SAVE),
            self.track_shortcut(commands['save_as'], 'Salvar como…', Action.SAVE_AS),
            item('Renomear…', self.rename, ft.Icons.EDIT_OUTLINED),
            self.shortcut_item('Fechar', Action.CLOSE_TAB, self.close_tab, ft.Icons.CLOSE),
            menu_separator(),
            submenu('Importar', self.import_items, icon=ft.Icons.FILE_DOWNLOAD_OUTLINED),
            submenu('Exportar', [commands['pdf'], commands['mp4']], icon=ft.Icons.FILE_UPLOAD_OUTLINED),
            menu_separator(),
            item('Projeto…', view.project_properties.open, ft.Icons.SETTINGS_OUTLINED)]
        for entry in files.items:
            entry.height = MENU_ITEM_HEIGHT
            entry.label_text_style = ft.TextStyle(size=TEXT_BODY)
        self.menus = EditorMenuBar([(files, True),
            *[(source, False) for source in self.toolbar.controls]])
        self.mode_tabs = ModeTabs((
            ModeTab('canvas', 'Canvas', lambda e: view.work_modes.show_canvas(), 'Modo Canvas'),
            ModeTab('animatic', 'Animatic', view.player.open, 'Abrir animatic da cena ativa'),
            ModeTab('references', 'Refs', lambda e: view.work_modes.show_references(), 'Canvas de referências')))
        self.canvas_mode = self.mode_tabs.buttons['canvas']
        self.play = self.mode_tabs.buttons['animatic']
        self.reference_mode = self.mode_tabs.buttons['references']
        self.modes = self.mode_tabs.content
        self.filter_selector = FilterSelector(view)
        view.properties.toggle_button.width = view.properties.toggle_button.height = COMPACT_CONTROL_HEIGHT
        view.properties.toggle_button.visible = False
        self.content = ft.Container(bgcolor=SURFACE, border=ft.Border(bottom=ft.BorderSide(1, BORDER)),
            padding=ft.Padding.symmetric(horizontal=4, vertical=2), on_size_change=self.resized,
            content=ft.Row([
                ft.Container(expand=True, content=ft.Row([self.menus.content],
                    scroll=ft.ScrollMode.AUTO, spacing=0)),
                self.modes,
                ft.Container(expand=True, content=ft.Row([self.filter_selector.content, view.properties.toggle_button],
                    alignment=ft.MainAxisAlignment.END, spacing=0)),
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
        return self.track_shortcut(item(title, handler, icon), title, action)

    def edit_handler(self, action, fallback):
        async def execute(e=None):
            if self.view.references.active:
                await self.view.references.execute(action)
            else:
                result = fallback(e)
                if isawaitable(result):
                    await result
        return execute

    def track_shortcut(self, entry, title, action):
        entry.content = self.view.keymap.describe(title, action)
        self.shortcut_items.append((entry, title, action))
        return entry

    def recent_items(self):
        tools = getattr(self.view, 'document_tools', None)
        return tools.recent_items() if tools else [menu_item('Nenhum arquivo', disabled=True)]

    def recent_key(self):
        tools = getattr(self.view, 'document_tools', None)
        return tuple(tools.app.recent.paths) if tools else ()

    async def paste_nodes(self, e=None):
        if hasattr(self.view, 'node_clipboard'):
            await self.view.node_clipboard.paste(self.view)
        else:
            await self.view.image_input.paste()

    async def copy_nodes(self, e=None):
        await self.view.node_clipboard.copy(self.view)

    async def cut_nodes(self, e=None):
        await self.view.node_clipboard.copy(self.view, cut=True)

    async def import_project(self, e=None):
        await self.view.document_tools.import_project()

    async def open_preferences(self, e=None):
        from koma.ui.preferences_panel import PreferencesPanel
        await PreferencesPanel(self.view).open(e)

    async def open_media(self, e=None):
        await self.view.document_tools.media()

    async def import_audio(self, e=None):
        if not self.view.player.opened:
            self.view.player.open()
        if self.view.player.opened:
            await self.view.player.media.pick_audio()

    async def close_tab(self, e=None):
        await self.view.close_project()

    def refresh_shortcuts(self):
        for key, title, action in (('canvas', 'Canvas', Action.MODE_CANVAS),
                ('animatic', 'Animatic', Action.MODE_ANIMATIC), ('references', 'Refs', Action.MODE_REFS)):
            self.mode_tabs.buttons[key].tooltip = self.view.keymap.describe(title, action)
        for entry, title, action in self.shortcut_items:
            entry.content = self.view.keymap.describe(title, action)
        self.view.graph.undo_button.tooltip = self.view.keymap.describe('Desfazer', Action.UNDO)
        self.view.graph.redo_button.tooltip = self.view.keymap.describe('Refazer', Action.REDO)
        self.view.properties.toggle_button.tooltip = self.view.keymap.describe('Propriedades', Action.PROPERTIES)

    async def fit_active(self, e=None):
        if self.view.references.active:
            await self.view.references.fit()
        elif self.view.player.opened:
            self.view.player.strip.fit()
        else:
            await self.workspace.fit(e)

    def sync(self):
        self.filter_selector.sync()
        if self.view.loaded and not self.view.closing and self.view.on_state:
            self.view.on_state(self.view)
        edit = self.edit_commands
        edit[Action.UNDO].disabled = self.view.graph.undo_button.disabled or self.view.player.editing
        edit[Action.REDO].disabled = self.view.graph.redo_button.disabled or self.view.player.editing
        edit[Action.UNDO].content = self.view.keymap.describe(self.view.history.undo_description, Action.UNDO)
        edit[Action.REDO].content = self.view.keymap.describe(self.view.history.redo_description, Action.REDO)
        selected = bool(self.view.edit_selection.ids)
        self.nav.selection_count.value = f'{len(self.view.edit_selection.ids)} selecionados'
        for action in (Action.CUT_NODES, Action.COPY, Action.DUPLICATE, Action.MOVE, Action.DELETE):
            edit[action].disabled = not selected
        edit[Action.PASTE].disabled = False
        for command in ('group', 'disconnect', 'remove_preserving'):
            self.view.graph.commands[command].disabled = not selected
        self.snap_item.checked = self.workspace.snap_enabled
        self.tools_item.checked = self.nav.tools.visible
        self.props_item.checked = self.view.properties.opened
        self.view.count.visible = self.wide and not selected
        self.nav.selection_bar.visible = selected
        self.play.disabled = not self.view.editable() or not self.view.board.frames
        self.canvas_mode.disabled = not self.view.editable()
        self.reference_mode.disabled = not self.view.editable()
        self.mode_tabs.select('references' if self.view.references.active else
            'animatic' if self.view.player.opened else 'canvas')
        self.workspace.controls.visible = not self.view.player.opened and not self.view.references.active
        for command in self.canvas_view_commands:
            command.disabled = self.view.player.opened or self.view.references.active
        self.props_item.disabled = self.view.references.active
        self.fit_all.content = self.view.keymap.describe(
            'Enquadrar timeline' if self.view.player.opened else 'Enquadrar tudo',
            Action.FOCUS if self.view.player.opened else Action.FIT)
        if self.view.player.opened:
            for action in (Action.CUT_NODES, Action.COPY, Action.PASTE, Action.DUPLICATE, Action.MOVE, Action.DELETE):
                edit[action].disabled = True
        for source in (self.selection_menu, self.add_menu, self.node_menu):
            source.disabled = self.view.player.opened or self.toolbar.disabled
        if self.view.references.active:
            self.node_menu.disabled = self.add_menu.disabled = True
            for action in (Action.COPY, Action.CUT_NODES, Action.MOVE):
                edit[action].disabled = True
        self.menus.sync(self.toolbar.disabled)
        self.sync_status()

    def sync_status(self):
        self.progress_slot.visible = self.view.feedback.progress.visible

    def lock(self, busy):
        locked = busy or bool(self.view.load_error)
        self.toolbar.disabled = self.right_tools.disabled = locked
        self.play.disabled = locked or not self.view.board.frames
        self.canvas_mode.disabled = locked
        self.view.properties.toggle_button.disabled = locked
        self.view.files.menu.disabled = busy
        self.menus.sync(self.toolbar.disabled)

    @explicit_updates
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
        self.page.show_dialog(dialog(title=ft.Text('Renomear projeto'), on_confirm=save,
            content=ft.Container(width=380, content=field),
            actions=[ft.TextButton('Cancelar', on_click=lambda e: self.page.pop_dialog()), ft.FilledButton('Salvar', on_click=save)]))

    def toggle_tools(self, e=None):
        self.nav.tools.visible = not self.nav.tools.visible
        self.sync()
        self.page.update(self.nav.tools, self.content)

    def select_all(self, e=None):
        if self.view.references.active:
            self.page.run_task(self.view.references.execute, Action.ALL)
            return
        self.nav.apply_selection({key for key, card in self.view.cards.items() if card.content.visible})
        self.nav.focus_keyboard()

    def select_none(self, e=None):
        if self.view.references.active:
            self.view.references.clear()
            return
        self.nav.apply_selection(set())
        self.nav.focus_keyboard()

    def invert(self, e=None):
        if self.view.references.active:
            canvas = self.view.references
            canvas.selection.replace({item.id for item in self.view.board.references} - canvas.selection.ids)
            canvas.paint()
            canvas.publish_cards(canvas.cards)
            canvas.selection_changed()
            return
        self.nav.apply_selection({key for key, card in self.view.cards.items() if card.content.visible} - self.nav.selection.ids)
        self.nav.focus_keyboard()

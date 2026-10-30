"""Card visual; edição e persistência são delegadas ao controlador do storyboard."""

import flet as ft
from dataclasses import replace

from koma.ui.menus import menu_item, popup_menu

from koma.ui.design import BORDER, COMPACT_CONTROL_HEIGHT, DRAG_INTERVAL_MS, MUTED, RADIUS, SURFACE
from koma.ui.typography import FONT_HEADING, TEXT_BODY, TEXT_SMALL
from koma.editor.geometry import NODE_WIDTH
from koma.editor.framing import ImageViewport
from koma.editor.shortcuts import Action
from koma.ui.node_layout import NODE_LAYOUT
from koma.ui.retained_container import RetainedContainer, RetainedColumn, retain_children
from koma.ui.sequence_body import SequenceBody


class StoryCard:
    @property
    def width(self):
        return NODE_LAYOUT.scene_width if self.viewport.frame.node_type.starts_scene else NODE_WIDTH

    @property
    def layout(self):
        border = self.box.border.bottom.width
        if self._layout is None or self._layout.border != border:
            self._layout = replace(NODE_LAYOUT, border=border)
        return self._layout

    def __init__(self, view, frame):
        self.view, self.identifier = view, frame.id
        self.sync_key = None
        self._layout = None
        self.number = ft.Text(size=TEXT_BODY, font_family=FONT_HEADING)
        self.title = ft.Text(frame.title or 'Sem título', size=TEXT_SMALL, expand=True, max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS)
        self.active_marker = ft.Icon(ft.Icons.RADIO_BUTTON_CHECKED, size=11,
            color=ft.Colors.SECONDARY, visible=False, tooltip='Quadro ativo no painel de propriedades')
        self.mute_marker = ft.Icon(ft.Icons.VISIBILITY_OFF, size=14, visible=False,
            tooltip='Mutado: ignorado no animatic')
        self.flow_warning = ft.Icon(ft.Icons.WARNING_AMBER_OUTLINED, size=14, color=MUTED, visible=False,
            tooltip='Sem caminho completo de Entrada até Saída. Ignorada no animatic e na exportação.')
        self.handle = self.move_handle(ft.Container(height=COMPACT_CONTROL_HEIGHT,
                content=ft.Row([ft.Icon(ft.Icons.DRAG_INDICATOR, size=16, color=MUTED), self.number,
                    self.title, self.mute_marker, self.flow_warning], spacing=6)), expand=True)
        self.sequence = popup_menu(icon=ft.Icons.MORE_HORIZ, tooltip='Opções do quadro e conexões',
            items=[menu_item('Anterior na sequência', icon=ft.Icons.ARROW_BACK,
                on_click=self.shift(-1)),
                menu_item('Próximo na sequência', icon=ft.Icons.ARROW_FORWARD,
                    on_click=self.shift(1)),
                menu_item('Desconectar entrada', on_click=view.graph.disconnect_port(frame.id, False)),
                menu_item('Desconectar saída', on_click=view.graph.disconnect_port(frame.id, True)),
                menu_item('Remover preservando fluxo',
                    on_click=lambda e: view.confirm_remove_frames({frame.id}, preserve_flow=True))])
        self.mute_item = menu_item('Mutar', icon=ft.Icons.VISIBILITY_OFF,
            on_click=self.toggle_muted)
        self.sequence.items.append(self.mute_item)
        self.sequence.items.append(menu_item('Editar propriedades', icon=ft.Icons.TUNE,
            on_click=self.edit_properties))
        self.sequence.items.extend([
            menu_item('Duplicar', icon=ft.Icons.CONTENT_COPY, on_click=self.duplicate),
            menu_item('Excluir', icon=ft.Icons.DELETE_OUTLINE, on_click=lambda e: view.confirm_remove(frame.id))])
        self.duration = ft.Text(f'{frame.duration:g} s', size=TEXT_SMALL, color=MUTED)
        self.viewport = ImageViewport(view, frame.id)
        self.image = ft.Container(content=self.viewport.content, alignment=ft.Alignment.CENTER)
        self.viewport.set_frame(frame)
        self.scene_title = ft.Text(frame.title, size=TEXT_BODY, font_family=FONT_HEADING, max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS)
        self.scene_code = ft.Text(size=TEXT_SMALL, color=MUTED)
        self.main_body = ft.Container(height=NODE_LAYOUT.scene_body_height, padding=8,
            content=self.move_handle(ft.Row([ft.Icon(ft.Icons.MOVIE_OUTLINED, size=22, color=ft.Colors.TERTIARY),
                ft.Column([self.scene_code, self.scene_title], expand=True, tight=True, spacing=0,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH)], spacing=8)))
        self.composite_body = SequenceBody(view, frame.id) if frame.node_type.contains_frames else None
        if self.composite_body:
            self.sequence.items.append(menu_item('Dissolver sequência',
                on_click=lambda e: view.sequences.dissolve(frame.id)))
        self.image_name = frame.image
        self.input_socket = ft.Container(left=0, width=NODE_LAYOUT.socket_size, height=NODE_LAYOUT.socket_size,
            content=view.workspace.links.socket(frame.id, False))
        self.output_socket = ft.Container(right=0, width=NODE_LAYOUT.socket_size, height=NODE_LAYOUT.socket_size,
            content=view.workspace.links.socket(frame.id, True))
        self.body_content = ft.Container(left=NODE_LAYOUT.socket_size / 2, right=NODE_LAYOUT.socket_size / 2,
            top=0, bottom=0, content=self.image if frame.node_type.image else self.main_body)
        self.body = ft.Stack(height=self.viewport.height if frame.node_type.image else self.main_body.height,
            controls=[self.body_content, self.input_socket, self.output_socket])
        self.header = ft.Row([self.handle, self.sequence], spacing=2, height=NODE_LAYOUT.header_height)
        self.footer = ft.Row([self.duration], height=NODE_LAYOUT.footer_height)
        hold_body = lambda: view.workspace.drag is not None
        self.box = RetainedContainer(hold_updates=hold_body,
            bgcolor=SURFACE, border=ft.Border.all(NODE_LAYOUT.border, BORDER),
            border_radius=RADIUS, padding=NODE_LAYOUT.padding,
            on_size_change=lambda e: view.workspace.node_resized(frame.id, e),
            content=RetainedColumn(hold_updates=hold_body, controls=[
                self.header, self.body, self.footer,
            ], tight=True, spacing=NODE_LAYOUT.spacing, horizontal_alignment=ft.CrossAxisAlignment.STRETCH))
        self.content = RetainedContainer(hold_updates=hold_body, content=view.external_drop.node(self.box, frame.id),
            left=frame.x or 0, top=frame.y or 0, width=self.width)

    def move_handle(self, content, *, expand=None):
        workspace = self.view.workspace
        return ft.GestureDetector(content=content, expand=expand, mouse_cursor=ft.MouseCursor.MOVE,
            drag_interval=DRAG_INTERVAL_MS, tooltip='Arraste para mover',
            on_double_tap=self.open_contents if self.composite_capable else None,
            on_tap_down=lambda e: workspace.navigation.node_click(self.identifier),
            on_pan_start=lambda e: workspace.begin_drag(self.identifier, e),
            on_pan_update=lambda e: workspace.update_drag(self.identifier, e),
            on_pan_end=self.end_drag, on_pan_cancel=lambda e: workspace.cancel_drag(self.identifier, e))

    @property
    def composite_capable(self):
        return self.view.sequences.index.nodes[self.identifier].node_type.contains_frames

    async def open_contents(self, e=None):
        await self.view.workspace.scope.show(self.identifier)

    async def end_drag(self, e):
        await self.view.workspace.end_drag(self.identifier, e)

    def shift(self, delta):
        async def changed(e):
            await self.view.shift_frame(self.identifier, delta)
        return changed

    async def pick_image(self, e):
        await self.view.pick_image(self.identifier)

    def edit_properties(self, e=None):
        if not self.view.editable():
            return
        navigation = self.view.workspace.navigation
        if navigation.effective_mode != 'select':
            navigation.set_mode('select')
        navigation.select_node(self.identifier, focus=True)
        if not self.view.properties.opened:
            self.view.properties.toggle()

    async def duplicate(self, e):
        await self.view.duplicate(self.identifier)

    async def toggle_muted(self, e=None):
        await self.view.toggle_muted({self.identifier})

    def set_image(self, name):
        self.image_name = name
        frame = next(frame for frame in self.view.board.frames if frame.id == self.identifier)
        self.viewport.set_frame(frame)

    def refresh_shortcuts(self):
        move = self.view.keymap.describe('Mover', Action.MOVE)
        detach = self.view.keymap.label(Action.DETACH)
        self.handle.tooltip = move + (f' · {detach} + arraste solta do fluxo' if detach else '')

    def sync(self, frame):
        nav = self.view.workspace.navigation
        key = (id(frame), self.view.board.fps, self.view.board.frame_format,
            self.view.production.code(frame.id),
            id(self.view.thumbnails.get(frame.image)), bool(self.view.board.links),
            self.identifier in nav.selection.ids, self.identifier == nav.selected,
            id(self.view.board) if frame.node_type.contains_frames else None)
        if key == self.sync_key:
            return
        self.sync_key = key
        self.refresh_shortcuts()
        self.frame = frame
        leaves = self.view.sequences.index.leaves((frame.id,)) if frame.node_type.contains_frames else ()
        muted = bool(leaves) and all(item.muted for item in leaves) if frame.node_type.contains_frames else frame.muted
        self.mute_item.content = self.view.keymap.describe('Desmutar' if muted else 'Mutar', Action.MUTE)
        self.mute_marker.visible = muted
        self.flow_warning.visible = bool(frame.sequence and not self.view.sequences.index.connected_path(frame.id))
        self.box.opacity = .5 if muted else 1
        self.title.value = frame.title or 'Sem título'
        self.input_socket.visible = frame.node_type.accepts_input
        self.output_socket.visible = True
        self.duration.visible = frame.node_type.timed or frame.node_type.contains_frames
        self.scene_title.value = frame.title or 'Cena'
        self.scene_code.value = self.view.production.code(frame.id)
        self.viewport.set_frame(frame)
        body = self.image if frame.node_type.image else self.main_body
        if self.composite_body:
            self.composite_body.sync(frame)
            body = self.composite_body.content
        self.body_content.content = body
        self.body.height = self.composite_body.content.height if self.composite_body else (
            self.viewport.height if frame.node_type.image else self.main_body.height)
        self.input_socket.top = self.output_socket.top = (self.body.height - NODE_LAYOUT.socket_size) / 2
        self.header.visible = not frame.node_type.starts_scene
        self.footer.visible = frame.node_type.timed or frame.node_type.contains_frames
        self.sync_duration(frame)
        self.image_name = frame.image
        for item in self.sequence.items[:2]:
            item.disabled = bool(self.view.board.links)
            item.visible = not frame.node_type.contains_frames
        self.paint(self.identifier in self.view.workspace.navigation.selection.ids,
            self.identifier == self.view.workspace.navigation.selected)

    def sync_duration(self, frame):
        seconds = self.view.sequences.index.total(frame.id) if frame.node_type.contains_frames else frame.duration
        self.duration.value = f'{seconds * self.view.board.fps:.6g} f'
        self.duration.tooltip = f'{seconds:.6g} s · {self.view.board.fps} FPS'

    def paint(self, active, is_active=False):
        frame = self.viewport.frame
        accent = frame.scene_color or ft.Colors.TERTIARY
        base = accent if frame.node_type.starts_scene else BORDER
        color = self.view.settings.configuration.values['appearance']['selection'] if active else base
        self.box.border = ft.Border.all(NODE_LAYOUT.border, color)
        self.box.bgcolor = SURFACE
        self.main_body.bgcolor = None
        self.number.color = ft.Colors.ON_SURFACE
        self.active_marker.visible = bool(active and is_active)

    def highlight(self, active, *, is_active=False, update=True):
        if not self.view.closing:
            self.paint(active, is_active)
            if update:
                with retain_children(self.box.content):
                    self.view.page.update(self.box)


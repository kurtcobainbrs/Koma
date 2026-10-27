"""Card visual; edição e persistência são delegadas ao controlador do storyboard."""

import flet as ft
from dataclasses import replace

from koma.ui.menus import menu_item, popup_menu

from koma.ui.design import BORDER, COMPACT_CONTROL_HEIGHT, DRAG_INTERVAL_MS, MUTED, RADIUS, SELECTION, SURFACE
from koma.ui.typography import FONT_HEADING, TEXT_BODY, TEXT_SMALL
from koma.editor.geometry import NODE_WIDTH
from koma.editor.framing import ImageViewport
from koma.editor.shortcuts import Action
from koma.ui.node_layout import NODE_LAYOUT


class StoryCard:
    @property
    def layout(self):
        return replace(NODE_LAYOUT, border=self.box.border.bottom.width)

    def __init__(self, view, frame):
        self.view, self.identifier = view, frame.id
        self.number = ft.Text(size=TEXT_BODY, font_family=FONT_HEADING)
        self.active_marker = ft.Icon(ft.Icons.RADIO_BUTTON_CHECKED, size=11,
            color=ft.Colors.SECONDARY, visible=False, tooltip='Quadro ativo no painel de propriedades')
        self.mute_marker = ft.Icon(ft.Icons.VISIBILITY_OFF, size=14, visible=False,
            tooltip='Mutado: ignorado no animatic')
        self.handle = ft.GestureDetector(expand=True, mouse_cursor=ft.MouseCursor.MOVE, drag_interval=DRAG_INTERVAL_MS,
            tooltip='Arraste o cabeçalho para mover o quadro',
            on_tap_down=lambda e: view.workspace.navigation.node_click(frame.id),
            on_pan_start=lambda e: view.workspace.begin_drag(frame.id, e),
            on_pan_update=lambda e: view.workspace.update_drag(frame.id, e),
            on_pan_end=self.end_drag, on_pan_cancel=lambda e: view.workspace.cancel_drag(frame.id, e),
            content=ft.Container(height=COMPACT_CONTROL_HEIGHT,
                content=ft.Row([ft.Icon(ft.Icons.DRAG_INDICATOR, size=18, color=MUTED), self.number,
                    self.active_marker, self.mute_marker], spacing=6)))
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
        self.title = ft.Text(frame.title or 'Sem título', size=TEXT_SMALL, expand=True, max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS)
        self.duration = ft.Text(f'{frame.duration:g} s', size=TEXT_SMALL, color=MUTED)
        self.viewport = ImageViewport(view, frame.id)
        self.image = ft.Container(content=self.viewport.content, alignment=ft.Alignment.CENTER)
        self.viewport.set_frame(frame)
        self.main_body = ft.Container(height=72, padding=8, on_click=lambda e: view.workspace.navigation.node_click(frame.id),
            content=ft.Column([ft.Row([ft.Icon(ft.Icons.MOVIE_OUTLINED, size=20),
                ft.Text(frame.title, size=TEXT_BODY, font_family=FONT_HEADING, max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS, expand=True)], spacing=8),
                ft.Text('Início de cena · conecte os quadros à saída', size=TEXT_SMALL, color=MUTED)], spacing=4))
        self.image_name = frame.image
        self.sockets = ft.Row([view.workspace.links.socket(frame.id, False), self.title, self.duration,
            view.workspace.links.socket(frame.id, True)], height=NODE_LAYOUT.footer_height, spacing=6)
        self.box = ft.Container(bgcolor=SURFACE, border=ft.Border.all(NODE_LAYOUT.border, BORDER),
            border_radius=RADIUS, padding=NODE_LAYOUT.padding,
            on_size_change=lambda e: view.workspace.node_resized(frame.id, e),
            content=ft.Column([
                ft.Row([self.handle, self.sequence,
                    ft.IconButton(icon=ft.Icons.CONTENT_COPY, tooltip='Duplicar quadro', icon_size=16,
                        width=COMPACT_CONTROL_HEIGHT, height=COMPACT_CONTROL_HEIGHT,
                        on_click=self.duplicate),
                    ft.IconButton(icon=ft.Icons.CLOSE, tooltip='Excluir quadro', icon_size=17,
                        width=COMPACT_CONTROL_HEIGHT, height=COMPACT_CONTROL_HEIGHT,
                        on_click=lambda e: view.confirm_remove(frame.id))], spacing=2, height=NODE_LAYOUT.header_height),
                self.image if frame.node_type.image else self.main_body, self.sockets,
            ], tight=True, spacing=NODE_LAYOUT.spacing, horizontal_alignment=ft.CrossAxisAlignment.STRETCH))
        self.content = ft.Container(content=view.external_drop.node(self.box, frame.id),
            left=frame.x or 0, top=frame.y or 0, width=NODE_WIDTH)

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
        self.refresh_shortcuts()
        self.frame = frame
        self.mute_item.content = self.view.keymap.describe('Desmutar' if frame.muted else 'Mutar', Action.MUTE)
        self.mute_marker.visible = frame.muted
        self.box.opacity = .5 if frame.muted else 1
        self.title.value = 'Saída da cena' if frame.node_type.starts_scene else frame.title or 'Sem título'
        self.sockets.controls[0].visible = frame.node_type.accepts_input
        self.duration.visible = frame.node_type.timed
        self.main_body.content.controls[0].controls[1].value = frame.title or 'Cena'
        self.box.content.controls[1] = self.image if frame.node_type.image else self.main_body
        self.sync_duration(frame)
        self.image_name = frame.image
        self.viewport.set_frame(frame)
        for item in self.sequence.items[:2]:
            item.disabled = bool(self.view.board.links)
        self.paint(self.identifier in self.view.workspace.navigation.selection.ids,
            self.identifier == self.view.workspace.navigation.selected)

    def sync_duration(self, frame):
        self.duration.value = f'{frame.duration * self.view.board.fps:.6g} f · {frame.duration:.6g} s'
        self.duration.tooltip = f'Duração a {self.view.board.fps} FPS'

    def paint(self, active, is_active=False):
        frame = self.viewport.frame
        accent = frame.scene_color or ft.Colors.TERTIARY
        base = accent if frame.node_type.starts_scene else BORDER
        color = ft.Colors.ON_SURFACE if is_active and active else ft.Colors.SECONDARY if active else base
        self.box.border = ft.Border.all(2 if active or frame.node_type.starts_scene else 1, color)
        self.box.bgcolor = (ft.Colors.with_opacity(.24, ft.Colors.SECONDARY)
            if active and is_active else SELECTION if active else SURFACE)
        self.main_body.bgcolor = ft.Colors.with_opacity(.14, accent)
        self.number.color = ft.Colors.ON_PRIMARY_CONTAINER if active else None
        self.active_marker.visible = bool(active and is_active)

    def highlight(self, active, *, is_active=False):
        if not self.view.closing:
            self.paint(active, is_active)
            self.view.page.update(self.box)


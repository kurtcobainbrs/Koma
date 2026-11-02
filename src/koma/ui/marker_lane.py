"""Faixa fina de marcadores: seleção, arraste e nome editável no próprio local."""
from koma.ui.event_updates import explicit_updates

import flet as ft

from koma.ui.design import BORDER, MUTED, SURFACE, CONTROL_HEIGHT, DRAG_INTERVAL_MS, input_style
from koma.ui.typography import TEXT_SMALL


class MarkerFlag:
    def __init__(self, lane, identifier):
        self.lane, self.identifier = lane, identifier
        self.token = None
        self.pointer_x = None
        self.icon = ft.Icon(ft.Icons.FLAG, size=TEXT_SMALL)
        self.guide = ft.Container(top=0, bottom=0, width=lane.strip.style.marker_line_width)
        self.title = ft.Text(size=TEXT_SMALL, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True)
        self.box = ft.Container(top=0, width=lane.strip.style.marker_height,
            height=lane.strip.style.marker_height,
            content=ft.GestureDetector(content=ft.Row([self.icon, self.title], spacing=2),
                on_tap=self.select, on_double_tap=self.rename,
                on_pan_down=self.pointer_down, on_pan_start=self.begin, on_pan_update=self.move,
                on_pan_end=self.finish, on_pan_cancel=self.cancel, drag_interval=DRAG_INTERVAL_MS,
                mouse_cursor=ft.MouseCursor.MOVE))

    def select(self, e=None):
        self.lane.editor.select(self.identifier)

    def rename(self, e=None):
        self.select()
        self.lane.rename()

    @explicit_updates
    def pointer_down(self, e):
        self.pointer_x = e.global_position.x

    @explicit_updates
    def begin(self, e):
        if self.lane.renaming is not None:
            self.lane.cancel_rename()
        if self.lane.strip.scale:
            origin = e.global_position.x if self.pointer_x is None else self.pointer_x
            self.token = self.lane.editor.begin(self.identifier, origin, self.lane.strip.scale)
            self.lane.editor.move(self.token, e.global_position.x)

    @explicit_updates
    def move(self, e):
        self.lane.editor.move(self.token, e.global_position.x)

    @explicit_updates
    async def finish(self, e):
        if e is not None and getattr(e, 'global_position', None) is not None:
            self.move(e)
        token, self.token = self.token, None
        self.pointer_x = None
        await self.lane.editor.finish(token)

    @explicit_updates
    def cancel(self, e=None):
        if self.token is not None and self.token is self.lane.editor.drag:
            self.lane.editor.cancel()
        self.token = None
        self.pointer_x = None


class MarkerLane:
    def __init__(self, strip):
        self.strip, self.player = strip, strip.player
        self.editor = self.player.marker_editor
        self.flags = {}
        self.renaming = None
        self.rename_target = None
        self.saving = False
        self.field = ft.TextField(max_length=200, counter=ft.Container(width=0, height=0),
            on_submit=self.save_name, on_blur=self.cancel_rename,
            tooltip='Enter confirma o nome; Esc cancela.', **input_style(height=strip.style.marker_height))
        self.rename_box = ft.Container(top=0, width=CONTROL_HEIGHT * 6, content=self.field,
            bgcolor=SURFACE, visible=False)
        self.background = ft.Container(left=0, right=0, top=0, bottom=0, bgcolor=SURFACE,
            border=ft.Border(bottom=ft.BorderSide(1, BORDER)))
        self.empty = ft.Container()
        self.content = ft.Stack(left=0, top=strip.style.marker_top, height=strip.style.marker_height)
        self.guides = ft.Container(left=0, right=0, top=strip.style.marker_top, bottom=0,
            ignore_interactions=True, content=ft.Stack(fit=ft.StackFit.EXPAND,
                clip_behavior=ft.ClipBehavior.HARD_EDGE))

    def sync(self):
        strip, editor = self.strip, self.editor
        if not strip.scale or not strip.width or not self.player.timeline:
            return
        markers = self.player.timeline.markers
        identifiers = {marker.id for marker in markers}
        self.flags = {marker.id: self.flags.get(marker.id) or MarkerFlag(self, marker.id) for marker in markers}
        if editor.selected not in identifiers:
            editor.selected = None
        if self.renaming not in identifiers:
            self.renaming = self.rename_target = None
        controls = [self.background]
        guides = []
        if not markers:
            self.empty.left = strip.offset + 8
            controls.append(self.empty)
        for index, marker in enumerate(markers):
            position = editor.position if editor.drag and editor.drag.marker.id == marker.id else marker.position
            x = strip.scale.pixels(position)
            if strip.offset - strip.style.marker_height <= x <= strip.offset + strip.width:
                flag = self.flags[marker.id]
                next_x = strip.scale.pixels(markers[index + 1].position) if index + 1 < len(markers) else strip.track.width
                self.place(flag, position, next_x)
                flag.title.value = marker.title
                flag.box.visible = self.renaming != marker.id
                colors = strip.player.view.settings.configuration.values['appearance']
                flag.icon.color = colors['selection'] if editor.selected == marker.id else colors['marker']
                opacity = (strip.style.selected_marker_line_opacity if editor.selected == marker.id
                    else strip.style.marker_line_opacity)
                flag.guide.bgcolor = ft.Colors.with_opacity(opacity, flag.icon.color)
                guides.append(flag.guide)
                flag.box.tooltip = f'{marker.title} · {position * self.player.view.board.fps:.6g} f · arraste para mover; duplo clique ou F2 para renomear'
                controls.append(flag.box)
            if self.renaming == marker.id:
                self.rename_box.width = min(CONTROL_HEIGHT * 6, strip.width)
                self.rename_box.left = max(strip.offset, min(strip.offset + strip.width - self.rename_box.width, x))
        self.rename_box.visible = self.renaming is not None
        controls.append(self.rename_box)
        self.content.width = strip.track.width
        self.content.controls = controls
        self.guides.content.controls = guides

    def place(self, flag, position, next_x):
        strip = self.strip
        x = strip.scale.pixels(position)
        flag.box.left = max(0, min(strip.track.width - strip.style.marker_height, x - strip.style.marker_height / 2))
        flag.box.width = min(strip.style.marker_label_width,
            max(strip.style.marker_height, next_x - x), strip.track.width - flag.box.left)
        flag.guide.left = max(0, min(strip.track.width - flag.guide.width, x))

    def preview(self, identifier):
        flag = self.flags.get(identifier)
        if flag is None or self.editor.position is None or not self.strip.scale:
            return
        position = self.editor.position
        next_position = min((marker.position for marker in self.player.timeline.markers
            if marker.id != identifier and marker.position > position), default=self.player.timeline.total)
        self.place(flag, position, self.strip.scale.pixels(next_position))
        self.player.view.page.update(flag.box, flag.guide)

    def rename(self, e=None):
        if self.player.editing or not self.player.view.editable():
            return
        if not self.player.timeline.local_editing:
            self.player.view.notify('Abra a cena para renomear marcadores.', 'info')
            return
        marker = next((item for item in self.player.timeline.markers if item.id == self.editor.selected), None)
        if marker:
            self.player.playing = False
            self.renaming = marker.id
            self.rename_target = (self.player.view.board, self.player.view.session)
            self.field.value = marker.title
            self.field.error_text = None
            self.player.render()
            self.player.view.page.run_task(self.field.focus)

    async def save_name(self, e=None):
        identifier, target = self.renaming, self.rename_target
        if identifier is None or target is None or self.saving:
            return
        self.saving = True
        try:
            await self.player.media.rename_marker(identifier, self.field.value or '', *target)
            self.cancel_rename()
            self.player.focus_timeline()
        except ValueError as exc:
            self.field.error_text = str(exc)
            self.player.view.page.update(self.field)
        finally:
            self.saving = False

    def cancel_rename(self, e=None):
        if e is not None and self.saving:
            return
        self.renaming = self.rename_target = None
        self.field.error_text = None
        self.rename_box.visible = False
        for flag in self.flags.values():
            flag.box.visible = True
        if self.player.opened:
            self.player.view.page.update(self.content)

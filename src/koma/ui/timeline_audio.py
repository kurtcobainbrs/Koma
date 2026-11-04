"""Trilha de waveform e controles de áudio/marcadores do animatic."""

import flet as ft
import flet.canvas as cv
from dataclasses import replace
from koma.editor.audio_drag import AudioDrag
from koma.editor.audio_volume import AudioVolume
from koma.editor.media_models import MAX_AUDIO_VOLUME
from koma.ui.workspace_style import WORKSPACE_STYLE
from koma.ui.retained_container import RetainedCanvas
from koma.ui.choice_input import ChoiceInput
from koma.ui.menus import menu_button_style
from koma.ui.vector_icons import magnet_icon

from koma.editor.timing import duration_text
from koma.editor.shortcuts import Action
from koma.expressions import MAX_EXPRESSION_LENGTH
from koma.ui.design import APP_PADDING, BORDER, MUTED, SURFACE, CONTROL_HEIGHT, COMPACT_CONTROL_HEIGHT, DRAG_INTERVAL_MS, RADIUS, input_style
from koma.ui.typography import TEXT_SMALL


class AudioLane:
    def __init__(self, strip):
        self.strip = strip
        self.key = None
        self.canvas = RetainedCanvas(hold_updates=lambda: False, shapes=[])
        self.drag = AudioDrag(strip.player)
        self.viewport = ft.Container(top=0, bottom=0, content=self.canvas)
        self.background = ft.Container(left=0, right=0, top=0, bottom=0, bgcolor=SURFACE,
            border=ft.Border.all(1, BORDER), border_radius=RADIUS)
        self.content = ft.Container(left=0, height=strip.style.audio_height,
            content=ft.GestureDetector(on_pan_start=self.drag.begin, on_pan_update=self.drag.move,
                on_pan_end=self.drag.end, on_pan_cancel=self.drag.cancel,
                mouse_cursor=ft.MouseCursor.MOVE, drag_interval=DRAG_INTERVAL_MS,
                content=ft.Stack([self.background, self.viewport], fit=ft.StackFit.EXPAND)))

    def sync(self):
        strip, player = self.strip, self.strip.player
        from koma.editor.media_models import MAX_AUDIO_TRACKS
        player.media.waveform_limit = MAX_AUDIO_TRACKS
        if player.timeline is None:
            return
        width = strip.width or 0
        available = player.timeline.audio_tracks
        if self.drag.start is not None and player.media.track:
            from koma.editor.project_time import project_audio_tracks
            selected = player.media.track
            board = replace(player.view.board, audio_tracks=tuple(replace(track, start=self.drag.start)
                if track.id == selected.id else track for track in player.view.board.audio_tracks))
            available = project_audio_tracks(board, getattr(player.timeline, 'scene_offsets', {}),
                getattr(player.timeline, 'scene_ends', {}))
        tracks = tuple(track for track in available if strip.scale
            and strip.scale.pixels(track.start + track.duration) >= strip.offset
            and strip.scale.pixels(track.start) <= strip.offset + width)
        waves = tuple(player.media.waveform(track) for track in tracks)
        key = (tracks, tuple(id(wave) for wave in waves), strip.scale, strip.offset, width)
        if key == self.key:
            return
        self.key = key
        self.content.top, self.content.width = strip.audio_top, strip.track.width
        self.viewport.left, self.viewport.width = strip.offset, width
        middle = strip.style.audio_height / 2
        self.canvas.shapes = [cv.Line(0, middle, width, middle, paint=ft.Paint(color=BORDER, stroke_width=1))]
        for track, wave in zip(tracks, waves):
            if wave is None:
                continue
            elements = []
            for x, low, high in wave.visible_peaks(strip.scale, track.start - getattr(track, 'source_offset', 0), strip.offset, width):
                if max(0, strip.scale.pixels(track.start) - strip.offset) <= x <= min(width, strip.scale.pixels(track.start + track.duration) - strip.offset):
                    elements.extend((cv.Path.MoveTo(x, middle - high * (middle - APP_PADDING)),
                        cv.Path.LineTo(x, middle - low * (middle - APP_PADDING))))
            self.canvas.shapes.append(cv.Path(elements, paint=ft.Paint(
                color=MUTED if track.muted else ft.Colors.TERTIARY,
                stroke_width=1, style=ft.PaintingStyle.STROKE)))


class AudioControls:
    def __init__(self, player):
        self.player = player
        self.focused = False
        self.target = None
        self.gain = AudioVolume(player)
        self.scope = ChoiceInput('Trilha de áudio', 'project', ('project', 'scene'),
            labels={'project': 'Projeto', 'scene': 'Cena'}, on_change=self.choose_scope)
        self.scope.button.width = WORKSPACE_STYLE.audio_scope_width
        self.scope.button.height = self.scope.button.content.height = COMPACT_CONTROL_HEIGHT
        self.file_name = ft.Text('Adicionar áudio', size=TEXT_SMALL, max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS, expand=True)
        self.import_button = ft.TextButton(content=ft.Row([
            ft.Icon(ft.Icons.AUDIO_FILE_OUTLINED, size=TEXT_SMALL), self.file_name], spacing=APP_PADDING),
            height=COMPACT_CONTROL_HEIGHT, width=WORKSPACE_STYLE.audio_file_width,
            style=menu_button_style(), on_click=player.media.pick_audio)
        self.mute = self.button(ft.Icons.VOLUME_UP, 'Mutar áudio', self.toggle_mute)
        self.remove = self.button(ft.Icons.DELETE_OUTLINE, 'Remover áudio', player.media.remove_audio)
        self.volume = ft.Slider(min=0, max=MAX_AUDIO_VOLUME, value=1,
            width=WORKSPACE_STYLE.slider_width, height=COMPACT_CONTROL_HEIGHT,
            tooltip='Volume', on_change_start=self.gain.begin, on_change_end=self.gain.finish,
            on_blur=lambda e: self.gain.cancel() if self.gain.snapshot is not None else None)
        self.start = ft.TextField(width=CONTROL_HEIGHT * 2.5, suffix=ft.Text('f'),
            tooltip='Início em frames · negativo avança no arquivo · aceita expressões', max_length=MAX_EXPRESSION_LENGTH,
            counter=ft.Container(width=0, height=0), on_focus=self.focus, on_blur=self.blur,
            on_change=self.changed, on_submit=self.submit_start, **input_style(height=COMPACT_CONTROL_HEIGHT))
        self.add_marker = self.button(ft.Icons.ADD_LOCATION_ALT_OUTLINED,
            player.view.keymap.describe('Criar marcador', Action.ADD_MARKER), player.media.add_marker)
        self.snap_icons = {value: magnet_icon(TEXT_SMALL + APP_PADDING, color)
            for value, color in ((True, ft.Colors.PRIMARY), (False, MUTED))}
        self.snap = self.button(self.snap_icons[True],
            player.view.keymap.describe('Snap da timeline', Action.SNAP), self.toggle_snap)
        self.tools = ft.Row([self.add_marker, self.snap], spacing=0, tight=True)
        self.level_group = ft.Row([self.mute, self.volume], spacing=0, tight=True)
        self.start_group = ft.Row([ft.Text('Início', size=TEXT_SMALL, color=MUTED), self.start],
            spacing=APP_PADDING, tight=True)
        self.edit_group = ft.Row([self.separator(), self.level_group, self.separator(),
            self.start_group, self.separator(), self.remove], spacing=APP_PADDING, tight=True)
        self.content = ft.Row([self.scope.button, self.import_button, self.edit_group],
            spacing=APP_PADDING, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    @staticmethod
    def separator():
        return ft.Container(width=1, height=COMPACT_CONTROL_HEIGHT - APP_PADDING * 2, bgcolor=BORDER)

    def choose_scope(self, e=None):
        if self.player.editing:
            return
        scope = self.scope.value
        self.blur()
        self.player.media.audio_scene = scope == 'scene' and self.player.scene_anchor is not None
        self.sync()
        self.player.strip.audio_lane.sync()
        self.player.view.page.update(self.content, self.player.strip.audio_lane.content)

    def toggle_snap(self, e=None):
        self.player.marker_editor.snap_enabled = not self.player.marker_editor.snap_enabled
        self.sync()
        self.player.view.page.update(self.content, self.tools)
        self.player.focus_timeline()

    @staticmethod
    def button(icon, tooltip, handler):
        return ft.IconButton(icon=icon, tooltip=tooltip, on_click=handler,
            width=COMPACT_CONTROL_HEIGHT, height=COMPACT_CONTROL_HEIGHT)

    def focus(self, e=None):
        track = self.player.media.track
        if track:
            self.player.playing = False
            self.focused = True
            self.target = (track.id, self.player.view.board, self.player.view.session)
            self.player.render()

    def blur(self, e=None):
        self.focused = False
        self.target = None
        self.sync()
        if self.player.opened:
            self.player.view.page.update(self.content)

    def changed(self, e=None):
        if not self.focused:
            self.focus()

    async def submit_start(self, e=None):
        try:
            track = self.player.media.track
            if not track or self.target != (track.id, self.player.view.board, self.player.view.session):
                raise ValueError('A trilha mudou. Selecione o campo novamente.')
            await self.player.media.set_start(self.start.value or '')
            self.blur()
            self.player.focus_timeline()
        except ValueError as exc:
            self.player.view.notify(str(exc), 'warning')

    async def toggle_mute(self, e=None):
        track = self.player.media.track
        if track:
            await self.player.media.change_track(muted=not track.muted)

    def sync(self):
        player = self.player
        track = player.media.track
        if self.target and (not track or self.target[0] != track.id or self.target[2] is not player.view.session):
            self.focused = False
            self.target = None
        locked = not player.presenting or not player.view.editable() or player.editing
        self.scope.button.disabled = locked
        self.scope.button.items[1].disabled = player.scene_anchor is None
        self.scope.value = 'scene' if player.media.audio_scene and player.scene_anchor else 'project'
        self.file_name.value = track.title or 'Áudio' if track else 'Adicionar áudio'
        self.edit_group.visible = track is not None
        self.import_button.disabled = locked
        self.add_marker.disabled = locked
        for button in (self.start, self.mute, self.remove):
            button.disabled = locked or track is None
        self.volume.disabled = (locked and self.gain.snapshot is None) or track is None
        if self.gain.snapshot is None:
            self.volume.value = track.volume if track else 1
        self.volume.tooltip = f'Volume · {self.volume.value * 100:.0f}%'
        if not self.focused:
            self.start.value = duration_text(track.start, player.view.board.fps, frames=True) if track else ''
        self.mute.icon = ft.Icons.VOLUME_OFF if track and track.muted else ft.Icons.VOLUME_UP
        self.mute.tooltip = 'Ativar áudio' if track and track.muted else 'Mutar áudio'
        action = 'Substituir áudio' if track else 'Adicionar áudio'
        self.import_button.tooltip = (track.title + '\n' if track and track.title else '') + player.view.keymap.describe(action, Action.IMPORT_AUDIO)
        self.add_marker.tooltip = player.view.keymap.describe('Criar marcador na agulha', Action.ADD_MARKER)
        self.snap.tooltip = player.view.keymap.describe('Snap ligado' if player.marker_editor.snap_enabled else 'Snap desligado', Action.SNAP)
        self.snap.tooltip += '\nQuadros, cenas, keyframes e marcadores'
        self.snap.icon = self.snap_icons[player.marker_editor.snap_enabled]
        self.snap.bgcolor = ft.Colors.PRIMARY_CONTAINER if player.marker_editor.snap_enabled else None
        self.snap.disabled = locked

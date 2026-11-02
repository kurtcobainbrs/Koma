"""Trilha de waveform e controles de áudio/marcadores do animatic."""

import flet as ft
import flet.canvas as cv
from dataclasses import replace
from koma.editor.audio_drag import AudioDrag
from koma.editor.audio_volume import AudioVolume
from koma.editor.media_models import MAX_AUDIO_VOLUME
from koma.ui.workspace_style import WORKSPACE_STYLE
from koma.ui.retained_container import RetainedCanvas

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
        self.name = ft.Text(size=TEXT_SMALL, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
        self.label = ft.Container(top=APP_PADDING, left=APP_PADDING, padding=ft.Padding.symmetric(horizontal=APP_PADDING),
            bgcolor=SURFACE, content=self.name, ignore_interactions=True)
        self.content = ft.Container(left=0, height=strip.style.audio_height,
            content=ft.GestureDetector(on_pan_start=self.drag.begin, on_pan_update=self.drag.move,
                on_pan_end=self.drag.end, on_pan_cancel=self.drag.cancel,
                mouse_cursor=ft.MouseCursor.MOVE, drag_interval=DRAG_INTERVAL_MS,
                content=ft.Stack([self.background, self.viewport, self.label], fit=ft.StackFit.EXPAND)))

    def sync(self):
        strip = self.strip
        if strip.player.timeline and not strip.player.timeline.local_editing:
            self.sync_project()
            return
        track = strip.player.media.track
        if track and self.drag.start is not None:
            track = replace(track, start=self.drag.start)
        waveform = strip.player.media.waveform(track) if track else None
        self.content.top = strip.frames_top + strip.style.track_height
        self.content.width = strip.track.width
        key = (track, id(waveform), strip.scale, strip.offset, strip.width)
        if key == self.key:
            return
        self.key = key
        self.viewport.left = strip.offset
        self.viewport.width = strip.width or 0
        self.label.left = strip.offset + APP_PADDING
        self.label.width = min(CONTROL_HEIGHT * 6, max(0, (strip.width or 0) - APP_PADDING * 2))
        self.label.visible = bool(track)
        self.name.value = track.title if track else ''
        self.name.tooltip = f'{track.title} · {track.duration:.2f} s' if track else None
        width = strip.width or 0
        middle = strip.style.audio_height / 2
        color = MUTED if not track or track.muted else ft.Colors.TERTIARY
        self.canvas.shapes = [cv.Line(0, middle, width, middle, paint=ft.Paint(color=BORDER, stroke_width=1))]
        if track and waveform and strip.scale:
            elements = []
            for x, low, high in waveform.visible_peaks(strip.scale, track.start, strip.offset, width):
                if 0 <= x <= width:
                    elements.extend((cv.Path.MoveTo(x, middle - high * (middle - 4)),
                        cv.Path.LineTo(x, middle - low * (middle - 4))))
            self.canvas.shapes.append(cv.Path(elements, paint=ft.Paint(color=color, stroke_width=1, style=ft.PaintingStyle.STROKE)))

    def sync_project(self):
        strip, player = self.strip, self.strip.player
        from koma.editor.media_models import MAX_AUDIO_TRACKS
        player.media.waveform_limit = MAX_AUDIO_TRACKS
        width = strip.width or 0
        tracks = tuple(track for track in player.timeline.audio_tracks if strip.scale
            and strip.scale.pixels(track.start + track.duration) >= strip.offset
            and strip.scale.pixels(track.start) <= strip.offset + width)
        waves = tuple(player.media.waveform(track) for track in tracks)
        key = (tracks, tuple(id(wave) for wave in waves), strip.scale, strip.offset, width)
        if key == self.key:
            return
        self.key = key
        self.content.top, self.content.width = strip.frames_top + strip.style.track_height, strip.track.width
        self.viewport.left, self.viewport.width = strip.offset, width
        self.label.visible = False
        middle = strip.style.audio_height / 2
        self.canvas.shapes = [cv.Line(0, middle, width, middle, paint=ft.Paint(color=BORDER, stroke_width=1))]
        for track, wave in zip(tracks, waves):
            if wave is None:
                continue
            elements = []
            for x, low, high in wave.visible_peaks(strip.scale, track.start, strip.offset, width):
                if 0 <= x <= width:
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
        self.import_button = self.button(ft.Icons.FILE_UPLOAD_OUTLINED, 'Importar áudio', player.media.pick_audio)
        self.mute = self.button(ft.Icons.VOLUME_UP, 'Mutar áudio', self.toggle_mute)
        self.remove = self.button(ft.Icons.DELETE_OUTLINE, 'Remover áudio', player.media.remove_audio)
        self.volume = ft.Slider(min=0, max=MAX_AUDIO_VOLUME, value=1,
            width=WORKSPACE_STYLE.slider_width, height=COMPACT_CONTROL_HEIGHT,
            tooltip='Volume', on_change_start=self.gain.begin, on_change_end=self.gain.finish,
            on_blur=lambda e: self.gain.cancel() if self.gain.snapshot is not None else None)
        self.start = ft.TextField(width=CONTROL_HEIGHT * 2.5, suffix=ft.Text('f'),
            tooltip='Início do áudio em frames · aceita expressões', max_length=MAX_EXPRESSION_LENGTH,
            counter=ft.Container(width=0, height=0), on_focus=self.focus, on_blur=self.blur,
            on_change=self.changed, on_submit=self.submit_start, **input_style(height=COMPACT_CONTROL_HEIGHT))
        self.add_marker = self.button(ft.Icons.ADD_LOCATION_ALT_OUTLINED,
            player.view.keymap.describe('Criar marcador', Action.ADD_MARKER), player.media.add_marker)
        self.snap = self.button(ft.Icons.GRID_ON,
            player.view.keymap.describe('Snap dos marcadores', Action.SNAP), self.toggle_snap)
        self.tools = ft.Row([self.add_marker, self.snap], spacing=0, tight=True)
        self.content = ft.Row([self.import_button, self.mute, self.volume, self.start, self.remove],
            spacing=APP_PADDING, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER)

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
        locked = not player.view.editable() or player.editing
        self.import_button.disabled = self.add_marker.disabled = locked or not player.timeline.local_editing
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
        self.import_button.tooltip = player.view.keymap.describe('Importar ou substituir áudio', Action.IMPORT_AUDIO)
        self.add_marker.tooltip = player.view.keymap.describe('Criar marcador na agulha', Action.ADD_MARKER)
        self.snap.tooltip = player.view.keymap.describe('Snap ligado' if player.marker_editor.snap_enabled else 'Snap desligado', Action.SNAP)
        self.snap.bgcolor = ft.Colors.PRIMARY_CONTAINER if player.marker_editor.snap_enabled else None
        self.snap.disabled = locked

"""Apresentação reutilizável da sequência; não altera o documento diretamente."""

from dataclasses import dataclass
import math

import flet as ft

from koma.editor.timeline import TimeScale
from koma.editor.timing import duration_text
from koma.editor.timeline_navigation import TimelineNavigator, ruler_ticks
from koma.ui.duration_input import DurationInput
from koma.editor.shortcuts import Action
from koma.ui.timeline_audio import AudioLane, AudioControls
from koma.ui.marker_lane import MarkerLane
from koma.ui.design import APP_PADDING, BORDER, CONTROL_HEIGHT, COMPACT_CONTROL_HEIGHT, DRAG_INTERVAL_MS, MUTED, PAGE_PADDING, RADIUS, SURFACE
from koma.ui.typography import TEXT_SMALL
from koma.editor.timeline_order import reorder
from koma.ui.components import drag_feedback
from koma.ui.timeline_thumbnail import TimelineThumbnail


@dataclass(frozen=True)
class TimelineStyle:
    track_height: float = CONTROL_HEIGHT + PAGE_PADDING
    handle_width: float = PAGE_PADDING
    zoom_factor: float = 2
    ruler_height: float = TEXT_SMALL + APP_PADDING * 2
    label_spacing: float = CONTROL_HEIGHT * 3
    wheel_zoom_distance: float = 240
    marker_height: float = TEXT_SMALL + APP_PADDING * 2
    audio_height: float = CONTROL_HEIGHT
    snap_distance: float = PAGE_PADDING
    marker_label_width: float = CONTROL_HEIGHT * 4
    marker_line_width: float = 1
    marker_line_opacity: float = .3
    selected_marker_line_opacity: float = .55
    thumbnail_label_minimum: float = CONTROL_HEIGHT * 2


class TimelineBlock:
    def __init__(self, strip, identifier):
        self.strip, self.identifier = strip, identifier
        self.token = None
        self.duration_pointer_x = None
        self.title = ft.Text(size=TEXT_SMALL, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
        self.duration = ft.Text(size=TEXT_SMALL, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
        self.thumbnail = TimelineThumbnail()
        self.labels = ft.Column([self.title, self.duration], spacing=2, tight=True, expand=True)
        self.reorder_target = None
        body = ft.GestureDetector(on_tap_down=self.seek, mouse_cursor=ft.MouseCursor.CLICK,
            content=ft.Container(padding=APP_PADDING,
                content=ft.Row([self.thumbnail.content, self.labels], spacing=APP_PADDING)))
        self.handle = ft.GestureDetector(on_pan_down=self.duration_pointer_down,
            on_pan_start=self.begin, on_pan_update=self.move,
            on_pan_end=self.finish, on_pan_cancel=self.cancel, drag_interval=DRAG_INTERVAL_MS,
            mouse_cursor=ft.MouseCursor.RESIZE_LEFT_RIGHT,
            tooltip='Arraste para ajustar a duração em frames',
            content=ft.Container(width=strip.style.handle_width, height=strip.style.track_height,
                bgcolor=ft.Colors.PRIMARY_CONTAINER,
                alignment=ft.Alignment.CENTER, content=ft.Icon(ft.Icons.DRAG_INDICATOR, size=TEXT_SMALL)))
        body = ft.DragTarget(group=strip.drag_group, on_accept=self.reorder_drop,
            content=ft.Draggable(group=strip.drag_group, data=identifier,
                on_drag_start=self.reorder_start, max_simultaneous_drags=1,
                content_feedback=drag_feedback(ft.Container(width=CONTROL_HEIGHT * 3,
                    height=strip.style.track_height, content=ft.Icon(ft.Icons.VIEW_TIMELINE_OUTLINED))), content=body))
        self.box = ft.Container(top=strip.style.marker_height + strip.style.ruler_height, height=strip.style.track_height,
            bgcolor=SURFACE, border=ft.Border.all(1, BORDER), border_radius=RADIUS,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            content=ft.Stack([ft.Container(left=0, top=0, right=0, bottom=0, content=body),
                ft.Container(right=0, top=0, bottom=0, content=self.handle)]))

    def seek(self, e):
        if self.strip.player.editing:
            return
        player = self.strip.player
        index = next((i for i, frame in enumerate(player.timeline.frames) if frame.id == self.identifier), None)
        if index is not None:
            player.playing = False
            player.position = player.timeline.starts[index]
            player.render()

    def reorder_start(self, e=None):
        self.strip.reorder_snapshot = None
        if not self.strip.player.view.editable() or self.strip.player.editing:
            return
        self.strip.duration_input.cancel()
        self.strip.audio_controls.blur()
        self.strip.marker_lane.cancel_rename()
        self.strip.player.playing = False
        self.strip.player.focus_timeline()
        self.strip.reorder_snapshot = (self.strip.player.view.board, self.strip.player.view.session)

    async def reorder_drop(self, e):
        snapshot, self.strip.reorder_snapshot = self.strip.reorder_snapshot, None
        source = getattr(e, 'src', None)
        if source is not None and source.group == self.strip.drag_group and snapshot is not None:
            await reorder(self.strip.player, e.src.data, self.identifier,
                after=e.local_position.x > self.box.width / 2, expected=snapshot)

    def duration_pointer_down(self, e):
        self.duration_pointer_x = e.global_position.x

    def begin(self, e):
        if self.strip.scale:
            origin = e.global_position.x if self.duration_pointer_x is None else self.duration_pointer_x
            self.token = self.strip.editor.begin(self.identifier, origin, self.strip.scale)
            self.strip.editor.move(self.token, e.global_position.x)

    def move(self, e):
        self.strip.editor.move(self.token, e.global_position.x)

    async def finish(self, e):
        if e is not None and getattr(e, 'global_position', None) is not None:
            self.move(e)
        token, self.token = self.token, None
        self.duration_pointer_x = None
        await self.strip.editor.finish(token)

    def cancel(self, e=None):
        if self.token is not None and self.token is self.strip.editor.drag:
            self.strip.editor.cancel()
        self.token = None
        self.duration_pointer_x = None


class TimelineStrip:
    def __init__(self, player, editor, style=None):
        self.player, self.editor = player, editor
        self.drag_group = f'timeline-{player.view.session.directory.name}'
        self.reorder_snapshot = None
        self.navigator = TimelineNavigator(player)
        self.duration_input = DurationInput(player)
        self.style = style or TimelineStyle()
        self.width = None
        self.scale = None
        self.fit_requested = True
        self.blocks = {}
        self.geometry_key = None
        self.active = None
        self.offset = 0
        self.ruler_key = None
        self.ruler_marks = ft.Stack(fit=ft.StackFit.EXPAND)
        self.marker_lane = MarkerLane(self)
        self.marker_layer = self.marker_lane.content
        self.ruler = ft.Container(left=0, top=self.style.marker_height, height=self.style.ruler_height,
            content=ft.GestureDetector(content=ft.Container(bgcolor=SURFACE, content=self.ruler_marks),
                on_tap_down=self.ruler_seek, on_pan_start=self.ruler_begin,
                on_pan_update=self.scrub_move, on_pan_end=self.navigator.end,
                on_pan_cancel=self.navigator.end, drag_interval=DRAG_INTERVAL_MS,
                mouse_cursor=ft.MouseCursor.CLICK))
        self.playhead = ft.Container(top=0, bottom=0, width=2, bgcolor=ft.Colors.PRIMARY, ignore_interactions=True)
        self.needle = ft.Container(top=self.style.marker_height, width=self.style.handle_width, height=self.style.ruler_height,
            content=ft.GestureDetector(on_pan_start=self.needle_begin, on_pan_update=self.scrub_move,
                on_pan_end=self.navigator.end, on_pan_cancel=self.navigator.end,
                drag_interval=DRAG_INTERVAL_MS, mouse_cursor=ft.MouseCursor.RESIZE_LEFT_RIGHT,
                tooltip='Arraste a agulha para percorrer os frames',
                content=ft.Container(bgcolor=ft.Colors.PRIMARY, border_radius=RADIUS)))
        self.track = ft.Stack(height=self.style.marker_height + self.style.track_height + self.style.ruler_height + self.style.audio_height,
            width=0, clip_behavior=ft.ClipBehavior.HARD_EDGE)
        self.audio_lane = AudioLane(self)
        self.audio_controls = AudioControls(player)
        self.scroller = ft.Row([self.track], scroll=ft.ScrollMode.ALWAYS, spacing=0, on_scroll=self.scrolled)
        self.fps = ft.Text(size=TEXT_SMALL, color=MUTED)
        self.undo = ft.IconButton(icon=ft.Icons.UNDO, tooltip='Desfazer edição', on_click=self.undo_edit,
            width=COMPACT_CONTROL_HEIGHT, height=COMPACT_CONTROL_HEIGHT)
        self.redo = ft.IconButton(icon=ft.Icons.REDO, tooltip='Refazer edição', on_click=self.redo_edit,
            width=COMPACT_CONTROL_HEIGHT, height=COMPACT_CONTROL_HEIGHT)
        self.fit_button = ft.IconButton(icon=ft.Icons.FIT_SCREEN,
            tooltip=player.view.keymap.describe('Enquadrar toda a timeline', Action.FOCUS), on_click=self.fit,
            width=COMPACT_CONTROL_HEIGHT, height=COMPACT_CONTROL_HEIGHT)
        self.zoom_out = ft.IconButton(icon=ft.Icons.REMOVE, tooltip='Diminuir zoom da timeline',
            on_click=lambda e: self.zoom(1 / self.style.zoom_factor),
            width=COMPACT_CONTROL_HEIGHT, height=COMPACT_CONTROL_HEIGHT)
        self.zoom_in = ft.IconButton(icon=ft.Icons.ADD, tooltip='Aumentar zoom da timeline',
            on_click=lambda e: self.zoom(self.style.zoom_factor),
            width=COMPACT_CONTROL_HEIGHT, height=COMPACT_CONTROL_HEIGHT)
        self.history_tools = ft.Row([self.undo, self.redo], spacing=0, tight=True)
        self.zoom_tools = ft.Row([self.fit_button, self.zoom_out, self.zoom_in], spacing=0, tight=True)
        self.footer_context = ft.Container(expand=True, alignment=ft.Alignment.CENTER_RIGHT)
        footer = ft.Row([self.audio_controls.content, self.footer_context],
            spacing=APP_PADDING * 2, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        self.content = ft.Container(on_size_change=self.resized,
            content=ft.Column([ft.GestureDetector(content=self.scroller, on_scroll=self.wheel_zoom), footer],
                spacing=APP_PADDING, tight=True))

    def reset(self):
        self.reorder_snapshot = None
        self.audio_lane.drag.cancel(update=False)
        self.player.marker_editor.cancel(update=False)
        self.marker_lane.cancel_rename()
        self.navigator.end()
        self.duration_input.cancel()
        self.offset = 0
        self.ruler_key = None
        self.fit_requested = True
        self.scale = None
        self.geometry_key = None
        self.sync()

    def ruler_seek(self, e):
        if self.scale:
            self.navigator.seek(self.scale.seconds(e.local_position.x))

    def ruler_begin(self, e):
        if self.scale:
            self.navigator.begin(e.global_position.x, self.scale, self.scale.seconds(e.local_position.x))

    def needle_begin(self, e):
        if self.scale:
            self.navigator.begin(e.global_position.x, self.scale)

    def scrub_move(self, e):
        self.navigator.move(e.global_position.x)

    def scrolled(self, e):
        self.offset = max(0, e.pixels)
        self.sync_ruler()
        self.audio_lane.sync()
        self.sync_markers()
        self.player.view.page.update(self.ruler_marks, self.audio_lane.content,
            self.marker_layer, self.marker_lane.guides)

    def sync_markers(self):
        self.marker_lane.sync()

    def sync_ruler(self):
        if not self.scale or not self.width or not self.player.timeline:
            return
        timeline = self.player.timeline
        fps = self.player.view.board.fps
        ticks = ruler_ticks(self.scale, self.offset, self.width, timeline.total, fps, self.style.label_spacing)
        key = (ticks, fps)
        if key == self.ruler_key:
            return
        self.ruler_key = key
        self.ruler_marks.controls = [ft.Container(left=x, top=0,
            content=ft.Text(f'{seconds:.2f} s', size=TEXT_SMALL, color=MUTED),
            border=ft.Border(left=ft.BorderSide(1, BORDER)), padding=ft.Padding.only(left=4))
            for seconds, x in ticks]

    def resized(self, e):
        if e.width > 0 and e.width != self.width:
            self.width = e.width
            if self.editor.drag is None:
                if self.fit_requested:
                    self.fit()
                else:
                    self.sync()
                    self.player.view.page.update(self.content)

    def fit(self, e=None):
        if self.player.editing or self.navigator.gesture or self.duration_input.focused:
            return
        self.fit_requested = True
        timeline = self.player.timeline
        if timeline and timeline.total > 0 and self.width:
            self.offset = 0
            self.scale = TimeScale.fit(self.width, timeline.total)
            self.geometry_key = None
            self.sync()
            if self.player.opened:
                self.player.view.page.update(self.content)
                self.player.view.page.run_task(self.scroll_to, 0)

    async def scroll_to(self, offset):
        if self.player.opened:
            await self.scroller.scroll_to(offset=offset)

    def wheel_zoom(self, e):
        delta = e.scroll_delta.y
        if not math.isfinite(delta) or delta == 0:
            return
        factor = self.style.zoom_factor ** max(-1, min(1, -delta / self.style.wheel_zoom_distance))
        self.zoom(factor, anchor_x=e.local_position.x)

    def zoom(self, factor, *, anchor_x=None):
        timeline = self.player.timeline
        if self.player.editing or self.navigator.gesture or self.duration_input.focused or self.scale is None or not timeline or timeline.total <= 0 or not self.width:
            return
        if not math.isfinite(factor) or factor <= 0:
            return
        anchor = self.width / 2 if anchor_x is None else max(0, min(self.width, anchor_x))
        center = self.scale.seconds(self.offset + anchor)
        minimum = TimeScale.fit(self.width, timeline.total).pixels_per_second
        maximum = self.width * self.player.view.board.fps
        self.scale = TimeScale(max(minimum, min(maximum, self.scale.pixels_per_second * factor)))
        self.offset = max(0, min(self.scale.pixels(timeline.total) - self.width,
            self.scale.pixels(center) - anchor))
        self.fit_requested = False
        self.geometry_key = None
        self.sync()
        self.player.view.page.update(self.content)
        self.player.view.page.run_task(self.scroll_to, self.offset)

    def sync(self):
        player, view = self.player, self.player.view
        timeline = player.timeline
        if timeline is None:
            return
        if self.scale is None and self.width and timeline.total > 0:
            self.scale = TimeScale.fit(self.width, timeline.total)
        identifiers = tuple(frame.id for frame in timeline.frames)
        if tuple(self.blocks) != identifiers:
            self.blocks = {key: self.blocks.get(key) or TimelineBlock(self, key) for key in identifiers}
            self.track.controls = [self.marker_layer, self.ruler, *(block.box for block in self.blocks.values()),
                self.audio_lane.content, self.marker_lane.guides, self.playhead, self.needle]
            self.geometry_key = None
        fps = view.board.fps
        self.fps.value = f'{fps} FPS'
        key = (id(timeline), self.scale)
        if self.scale and key != self.geometry_key:
            for index, frame in enumerate(timeline.frames):
                block = self.blocks[frame.id]
                block.box.left = self.scale.pixels(timeline.starts[index])
                block.box.width = self.scale.pixels(frame.duration)
                available = max(0, block.box.width - self.style.handle_width - APP_PADDING * 2)
                height = max(0, self.style.track_height - APP_PADDING * 2)
                natural_width = height * view.board.frame_format.aspect_ratio
                block.labels.visible = available >= natural_width + APP_PADDING + self.style.thumbnail_label_minimum
                width = min(natural_width, available)
                block.thumbnail.sync(frame, view.thumbnails, width, height)
                block.title.value = f'{index + 1:02d} · {frame.title or "Sem título"}'
                block.duration.value = f'{duration_text(frame.duration, fps, frames=True)} f'
                block.box.tooltip = f'{block.title.value} · {block.duration.value} · {duration_text(frame.duration, fps)} s'
            self.track.width = max(self.width or 0, self.scale.pixels(timeline.total))
            self.ruler.width = self.track.width
            self.geometry_key = key
        current = timeline.frames[player.current].id if 0 <= player.current < len(timeline.frames) else None
        for identifier in {self.active, current} - {None}:
            if identifier in self.blocks:
                self.blocks[identifier].box.bgcolor = ft.Colors.PRIMARY_CONTAINER if identifier == current else SURFACE
        self.active = current
        self.sync_cursor()
        self.sync_ruler()
        self.audio_lane.sync()
        self.audio_controls.sync()
        self.sync_markers()
        self.duration_input.sync()
        editing = player.editing
        self.undo.disabled = editing or not view.editable() or not view.history.past
        self.redo.disabled = editing or not view.editable() or not view.history.future
        self.undo.tooltip = view.keymap.describe(view.history.undo_description, Action.UNDO)
        self.redo.tooltip = view.keymap.describe(view.history.redo_description, Action.REDO)
        for control in (self.fit_button, self.zoom_out, self.zoom_in):
            control.disabled = editing or not timeline.frames

    def sync_cursor(self):
        """Playback changes only these positions, not track geometry or waveform."""
        self.playhead.visible = bool(self.player.timeline.frames and self.scale)
        self.needle.visible = self.playhead.visible
        if self.scale:
            self.playhead.left = max(0, min(self.track.width - self.playhead.width, self.scale.pixels(self.player.position)))
            self.needle.left = max(0, min(self.track.width - self.style.handle_width,
                self.scale.pixels(self.player.position) - self.style.handle_width / 2))

    async def undo_edit(self, e=None):
        if not self.undo.disabled:
            self.player.playing = False
            await self.player.view.graph.undo()
            self.player.rebuild_timeline()
            self.player.render()

    async def redo_edit(self, e=None):
        if not self.redo.disabled:
            self.player.playing = False
            await self.player.view.graph.redo()
            self.player.rebuild_timeline()
            self.player.render()

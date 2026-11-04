"""Apresentação reutilizável da sequência; não altera o documento diretamente."""

from dataclasses import dataclass
import math

import flet as ft
from koma.ui.event_updates import explicit_updates

from koma.editor.timeline import TimeScale
from koma.editor.timing import duration_text
from koma.editor.timeline_navigation import TimelineNavigator, ruler_ticks
from koma.editor.time_display import time_text
from koma.ui.duration_input import DurationInput
from koma.editor.shortcuts import Action
from koma.editor.modifier_state import pressed_modifiers
from koma.ui.timeline_audio import AudioLane, AudioControls
from koma.ui.marker_lane import MarkerLane
from koma.ui.design import APP_PADDING, BORDER, CONTROL_HEIGHT, COMPACT_CONTROL_HEIGHT, DRAG_INTERVAL_MS, MUTED, PAGE_PADDING, RADIUS, SURFACE
from koma.ui.typography import TEXT_SMALL
from koma.editor.timeline_order import reorder
from koma.ui.components import drag_feedback
from koma.ui.timeline_thumbnail import TimelineThumbnail
from koma.ui.image_source import thumbnail_source
from koma.ui.workspace_style import WORKSPACE_STYLE
from koma.ui.sequence_lane import SequenceLane
from koma.ui.navigation_view import NativeNavigation
from koma.ui import drop_runtime
from koma.ui.retained_container import RetainedStack, retain_children
from koma.editor.scroll_requests import ScrollRequests
from koma.editor import timeline_viewport


@dataclass(frozen=True)
class TimelineStyle:
    track_height: float = WORKSPACE_STYLE.picture_height
    handle_width: float = PAGE_PADDING
    zoom_factor: float = 2
    ruler_height: float = WORKSPACE_STYLE.ruler_height
    label_spacing: float = CONTROL_HEIGHT * 3
    wheel_zoom_distance: float = 240
    marker_height: float = WORKSPACE_STYLE.marker_height
    sequence_height: float = WORKSPACE_STYLE.sequence_height
    audio_height: float = WORKSPACE_STYLE.audio_height
    snap_distance: float = PAGE_PADDING
    marker_label_width: float = CONTROL_HEIGHT * 4
    marker_line_width: float = 1
    marker_line_opacity: float = .3
    selected_marker_line_opacity: float = .55
    thumbnail_label_minimum: float = CONTROL_HEIGHT * 2
    caption_height: float = WORKSPACE_STYLE.picture_caption_height

    @property
    def marker_top(self):
        return self.ruler_height

    @property
    def frames_top(self):
        return self.ruler_height + self.marker_height


class TimelineBlock:
    def __init__(self, strip, identifier):
        self.strip, self.identifier = strip, identifier
        self.token = None
        self.duration_pointer_x = None
        self.title = ft.Text(size=TEXT_SMALL, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
        self.duration = ft.Text(size=TEXT_SMALL, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
        self.thumbnail = TimelineThumbnail()
        self.title.expand = True
        self.labels = ft.Row([self.title, self.duration], spacing=APP_PADDING, height=strip.style.caption_height)
        self.reorder_target = None
        body = ft.GestureDetector(on_tap_down=self.seek, mouse_cursor=ft.MouseCursor.CLICK,
            content=ft.Stack([self.thumbnail.content,
                ft.Container(left=APP_PADDING, right=strip.style.handle_width + APP_PADDING,
                    bottom=0, height=strip.style.caption_height, content=self.labels)]))
        self.handle = ft.GestureDetector(on_pan_down=self.duration_pointer_down,
            on_pan_start=self.begin, on_pan_update=self.move,
            on_pan_end=self.finish, on_pan_cancel=self.cancel, drag_interval=DRAG_INTERVAL_MS,
            mouse_cursor=ft.MouseCursor.RESIZE_LEFT_RIGHT,
            tooltip=self.duration_hint(),
            content=ft.Container(width=strip.style.handle_width, height=strip.style.track_height,
                bgcolor=ft.Colors.TRANSPARENT,
                alignment=ft.Alignment.CENTER, content=ft.Icon(ft.Icons.DRAG_INDICATOR, size=TEXT_SMALL, color=MUTED)))
        body = ft.DragTarget(group=strip.drag_group, on_accept=self.reorder_drop,
            content=ft.Draggable(group=strip.drag_group, data=identifier,
                on_drag_start=self.reorder_start, max_simultaneous_drags=1,
                content_feedback=drag_feedback(ft.Container(width=CONTROL_HEIGHT * 3,
                    height=strip.style.track_height, content=ft.Icon(ft.Icons.VIEW_TIMELINE_OUTLINED))), content=body))
        self.box = ft.Container(top=strip.frames_top, height=strip.style.track_height,
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
            player.select_node(self.identifier, seek=True)

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

    @explicit_updates
    def duration_pointer_down(self, e):
        self.duration_pointer_x = e.global_position.x

    def duration_hint(self):
        key = self.strip.player.view.keymap.label(Action.RIPPLE_DURATION)
        return 'Ajustar corte' + (f' · {key}: empurrar' if key else '')

    def begin(self, e):
        if self.strip.scale:
            self.strip.player.view.properties.release_field_focus()
            self.strip.player.select_node(self.identifier)
            origin = e.global_position.x if self.duration_pointer_x is None else self.duration_pointer_x
            physical = pressed_modifiers()
            modifiers = self.strip.player.modifiers if physical is None else physical
            ripple = self.strip.player.view.keymap.modifier_active(Action.RIPPLE_DURATION, modifiers)
            self.token = self.strip.editor.begin(self.identifier, origin, self.strip.scale, ripple=ripple)
            self.strip.editor.move(self.token, e.global_position.x)

    @explicit_updates
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
        self.sequence_lane = SequenceLane(self)
        self.width = None
        self.scale = None
        self.fit_requested = True
        self.initial_requested = True
        self.blocks = {}
        self.geometry_key = None
        self.active = None
        self.selected = None
        self.offset = 0
        self.generation = 0
        self.scroll_requests = ScrollRequests(self)
        self.ruler_key = None
        self.ruler_marks = ft.Stack(fit=ft.StackFit.EXPAND)
        self.marker_lane = MarkerLane(self)
        self.marker_layer = self.marker_lane.content
        self.ruler = ft.Container(left=0, top=0, height=self.style.ruler_height,
            content=ft.GestureDetector(content=ft.Container(bgcolor=SURFACE, content=self.ruler_marks),
                on_tap_down=self.ruler_seek, on_pan_start=self.ruler_begin,
                on_pan_update=self.scrub_move, on_pan_end=self.navigator.end,
                on_pan_cancel=self.navigator.end, drag_interval=DRAG_INTERVAL_MS,
                mouse_cursor=ft.MouseCursor.CLICK))
        self.playhead = ft.Container(top=0, bottom=0, width=1, bgcolor=ft.Colors.ON_SURFACE, ignore_interactions=True)
        self.needle = ft.Container(top=0, width=self.style.handle_width, height=self.style.ruler_height,
            content=ft.GestureDetector(on_pan_start=self.needle_begin, on_pan_update=self.scrub_move,
                on_pan_end=self.navigator.end, on_pan_cancel=self.navigator.end,
                drag_interval=DRAG_INTERVAL_MS, mouse_cursor=ft.MouseCursor.RESIZE_LEFT_RIGHT,
                tooltip='Arraste a agulha para percorrer os frames',
                content=ft.Container(alignment=ft.Alignment.BOTTOM_CENTER,
                    content=ft.Icon(ft.Icons.ARROW_DROP_DOWN, size=18, color=ft.Colors.ON_SURFACE))))
        self.track = RetainedStack(hold_updates=lambda: False, height=self.style.marker_height + self.style.track_height + self.style.ruler_height + self.style.audio_height,
            width=0, clip_behavior=ft.ClipBehavior.HARD_EDGE)
        self.audio_lane = AudioLane(self)
        self.audio_controls = AudioControls(player)
        self.native_navigation = NativeNavigation(mode='timeline', content=self.track,
            content_coordinates=True, on_zoom=self.native_zoom, on_activate=self.activate_navigation,
            on_engage=self.engage_navigation) if drop_runtime.supports('navigation_v1') else None
        self.scroller = ft.Row([self.native_navigation or self.track], scroll=ft.ScrollMode.ALWAYS,
            scroll_interval=DRAG_INTERVAL_MS, spacing=0, on_scroll=self.scrolled)
        self.configure_navigation()
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
        self.zoom_slider = ft.Slider(min=0, max=1, value=0, tooltip='Zoom da timeline',
            width=WORKSPACE_STYLE.slider_width, height=COMPACT_CONTROL_HEIGHT,
            on_change=self.slide_zoom)
        self.history_tools = ft.Row([self.undo, self.redo], spacing=0, tight=True)
        self.zoom_tools = ft.Row([self.fit_button, self.zoom_out, self.zoom_slider, self.zoom_in], spacing=0, tight=True)
        self.footer_context = ft.Container(expand=True, alignment=ft.Alignment.CENTER_RIGHT)
        footer = ft.Row([self.audio_controls.content, self.footer_context],
            spacing=APP_PADDING * 2, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        self.track_host = ft.Container(expand=True, on_size_change=self.resized,
            content=self.scroller if self.native_navigation else
                ft.GestureDetector(content=self.scroller, on_scroll=self.wheel_zoom))
        self.sequence_label = self.track_label('Sequências', 0)
        self.sequence_label.visible = False
        self.track_labels = ft.Column([self.track_label('', self.style.ruler_height),
            self.track_label('Marcas', self.style.marker_height), self.sequence_label, self.track_label('Quadros', self.style.track_height),
            self.track_label('Áudio', self.style.audio_height)], spacing=0)
        self.content = ft.Container(
            content=ft.Column([ft.Row([self.track_labels, self.track_host], spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.START), footer],
                spacing=APP_PADDING, tight=True))

    @staticmethod
    def track_label(text, height):
        return ft.Container(width=WORKSPACE_STYLE.track_label_width, height=height,
            alignment=ft.Alignment.CENTER_LEFT, padding=ft.Padding.only(left=APP_PADDING * 2),
            border=ft.Border(right=ft.BorderSide(1, BORDER), bottom=ft.BorderSide(1, BORDER)),
            content=ft.Text(text, size=TEXT_SMALL, color=MUTED))

    @property
    def frames_top(self):
        return self.style.frames_top + self.sequence_lane.height

    def reset(self):
        self.generation += 1
        self.scroll_requests.pending = None
        if self.native_navigation:
            self.native_navigation.generation = self.generation
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
        self.initial_requested = True
        self.geometry_key = None
        self.sync()
        self.prepare_scroll()
        if self.native_navigation is None and self.player.presenting:
            self.scroll_requests.request(0)

    def ruler_seek(self, e):
        if self.scale:
            self.navigator.seek(self.scale.seconds(e.local_position.x))

    def ruler_begin(self, e):
        if self.scale:
            self.navigator.begin(e.global_position.x, self.scale, self.scale.seconds(e.local_position.x))

    def needle_begin(self, e):
        if self.scale:
            self.navigator.begin(e.global_position.x, self.scale)

    @explicit_updates
    def scrub_move(self, e):
        self.navigator.move(e.global_position.x)

    @explicit_updates
    def scrolled(self, e):
        if not self.player.presenting:
            return
        if self.native_navigation is None and self.scroll_requests.pending is not None:
            return
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
        extent = self.scale.seconds(self.track.width) if self.track.width else timeline.total
        ticks = ruler_ticks(self.scale, self.offset, self.width, max(timeline.total, extent), fps, self.style.label_spacing)
        key = (ticks, fps)
        if key == self.ruler_key:
            return
        self.ruler_key = key
        self.ruler_marks.controls = [ft.Container(left=x, top=0,
            content=ft.Text(time_text(seconds, fps, self.player.view.settings.configuration.values['timeline']), size=TEXT_SMALL, color=MUTED),
            border=ft.Border(left=ft.BorderSide(1, BORDER)), padding=ft.Padding.only(left=4))
            for seconds, x in ticks]

    @explicit_updates
    def resized(self, e):
        if not self.player.presenting:
            return
        if e.width > 0 and e.width != self.width:
            self.width = e.width
            if self.editor.drag is None:
                if self.initial_requested:
                    self.scale = None
                    self.geometry_key = None
                    self.sync()
                    self.prepare_scroll()
                    self.publish_geometry()
                elif self.fit_requested:
                    self.fit()
                else:
                    self.sync()
                    self.player.view.page.update(self.content)

    def fit(self, e=None):
        if self.player.editing or self.navigator.gesture or self.duration_input.focused:
            return
        self.fit_requested = True
        self.initial_requested = False
        timeline = self.player.timeline
        if timeline and timeline.total > 0 and self.width:
            self.offset = 0
            self.scale = TimeScale.fit(self.width, timeline.total)
            self.geometry_key = None
            self.sync()
            self.prepare_scroll()
            if self.player.opened:
                self.publish_geometry()

    async def scroll_to(self, offset):
        self.scroll_requests.request(offset)

    def configure_navigation(self):
        self.geometry_key = self.ruler_key = None
        if self.scale and self.width and self.player.timeline and self.player.timeline.total > 0:
            self.scale, self.offset = timeline_viewport.zoom_at(self.scale, self.offset, self.width,
                self.player.timeline.total, self.player.view.board.fps, 1, self.width / 2,
                self.player.view.settings.configuration.values['animatic'])
            self.prepare_scroll()
        if self.native_navigation:
            options = self.player.view.settings.configuration.values['animatic']
            self.native_navigation.zoom_modifiers = list(self.player.view.keymap.bindings(Action.DRAG_ZOOM))
            self.native_navigation.wheel_sensitivity = options['timeline_wheel_sensitivity']
            self.native_navigation.pan_speed = options['timeline_pan_speed']

    @explicit_updates
    def activate_navigation(self, e=None):
        self.player.navigation_target = 'timeline'

    @explicit_updates
    def engage_navigation(self, e=None):
        if self.player.presenting:
            self.activate_navigation()
            if self.duration_input.focused:
                self.duration_input.cancel()
            self.player.view.properties.release_field_focus()
            self.player.focus_timeline()

    @explicit_updates
    def native_zoom(self, e):
        native = self.native_navigation
        if native is None or e.generation != self.generation:
            return
        native.revision += 1
        if self.player.presenting and not self.player.editing and math.isfinite(e.pixels):
            self.offset = max(0, e.pixels)
            if self.zoom(e.factor, anchor_x=e.anchor_x):
                return
        if self.player.presenting:
            with retain_children(self.track):
                self.player.view.page.update(native)

    def prepare_scroll(self):
        if self.native_navigation:
            self.native_navigation.scroll_offset = self.offset
            self.native_navigation.scroll_request += 1

    def publish_geometry(self):
        with retain_children(*(block.thumbnail.canvas for block in self.blocks.values())):
            self.player.view.page.update(self.content)
        if self.native_navigation is None:
            self.scroll_requests.request(self.offset)

    def wheel_zoom(self, e):
        if not self.player.presenting:
            return
        delta = e.scroll_delta.y
        if not math.isfinite(delta) or delta == 0:
            return
        sensitivity = self.player.view.settings.configuration.values['animatic']['timeline_wheel_sensitivity']
        factor = self.style.zoom_factor ** max(-1, min(1, -delta * sensitivity / self.style.wheel_zoom_distance))
        self.zoom(factor, anchor_x=e.local_position.x)

    def zoom(self, factor, *, anchor_x=None):
        timeline = self.player.timeline
        if self.player.editing or self.navigator.gesture or self.duration_input.focused or self.scale is None or not timeline or timeline.total <= 0 or not self.width:
            return
        if not math.isfinite(factor) or factor <= 0:
            return
        if anchor_x is not None and not math.isfinite(anchor_x):
            return
        anchor = self.width / 2 if anchor_x is None else max(0, min(self.width, anchor_x))
        self.scale, self.offset = timeline_viewport.zoom_at(self.scale, self.offset, self.width,
            timeline.total, self.player.view.board.fps, factor, anchor,
            self.player.view.settings.configuration.values['animatic'])
        self.fit_requested = False
        self.initial_requested = False
        self.geometry_key = None
        self.sync()
        self.prepare_scroll()
        self.publish_geometry()
        return True

    def zoom_limits(self):
        timeline = self.player.timeline
        if not timeline or timeline.total <= 0 or not self.width:
            return None
        return timeline_viewport.zoom_limits(self.width, timeline.total, self.player.view.board.fps,
            self.player.view.settings.configuration.values['animatic'])

    def slide_zoom(self, e):
        limits = self.zoom_limits()
        if limits and self.scale:
            minimum, maximum = limits
            target = minimum * (maximum / minimum) ** max(0, min(1, e.control.value))
            self.zoom(target / self.scale.pixels_per_second)

    def sync(self):
        player, view = self.player, self.player.view
        timeline = player.timeline
        if timeline is None:
            return
        if self.scale is None and self.width and timeline.total > 0:
            self.scale = timeline_viewport.initial_scale(self.width, timeline.total, view.board.fps,
                view.settings.configuration.values['animatic'])
        identifiers = tuple(frame.id for frame in timeline.frames)
        self.sequence_lane.sync(identifiers)
        self.sequence_label.height = self.sequence_lane.height
        self.sequence_label.visible = bool(self.sequence_lane.height)
        height = self.frames_top + self.style.track_height + self.style.audio_height
        if self.track.height != height:
            self.track.height = height
            if hasattr(player, 'layout'):
                player.layout.sync_height()
        if tuple(self.blocks) != identifiers or not self.track.controls:
            self.blocks = {key: self.blocks.get(key) or TimelineBlock(self, key) for key in identifiers}
            self.track.controls = [self.marker_layer, self.ruler, self.sequence_lane.content, *(block.box for block in self.blocks.values()),
                self.audio_lane.content, self.marker_lane.guides, self.playhead, self.needle]
            self.geometry_key = None
        fps = view.board.fps
        self.fps.value = f'{fps} FPS'
        key = (id(timeline), self.scale)
        if self.scale and key != self.geometry_key:
            for index, frame in enumerate(timeline.frames):
                block = self.blocks[frame.id]
                block.box.top = self.frames_top
                block.handle.tooltip = block.duration_hint()
                block.box.left = self.scale.pixels(timeline.starts[index])
                span = timeline.durations[index] if hasattr(timeline, 'durations') else frame.duration
                block.box.width = self.scale.pixels(span)
                block.handle.disabled = not timeline.local_editing
                width = max(0, block.box.width - 2)
                height = max(0, self.style.track_height - self.style.caption_height)
                block.labels.visible = width >= self.style.thumbnail_label_minimum
                block.thumbnail.sync(frame, view.thumbnails, width, height,
                    image_source=thumbnail_source(view, frame.image), frame_format=view.board.frame_format, view=view)
                block.title.value = view.production.label(frame.id)
                block.duration.value = f'{duration_text(frame.duration, fps, frames=True)} f'
                block.box.tooltip = f'{block.title.value} · {block.duration.value} · {duration_text(frame.duration, fps)} s'
            self.track.width = timeline_viewport.content_width(self.scale, self.width or 0, timeline.total,
                self.player.view.settings.configuration.values['animatic'])
            self.ruler.width = self.track.width
            self.geometry_key = key
        self.sequence_lane.content.width = self.track.width
        if self.native_navigation:
            self.native_navigation.width, self.native_navigation.height = self.track.width, self.track.height
            self.native_navigation.navigation_enabled = not player.editing
        current = timeline.frames[player.current].id if 0 <= player.current < len(timeline.frames) else None
        for identifier in {self.active, current} - {None}:
            if identifier in self.blocks:
                self.blocks[identifier].box.bgcolor = ft.Colors.SURFACE_CONTAINER_HIGH if identifier == current else SURFACE
        self.active = current
        self.sync_selection()
        self.sync_cursor()
        self.sync_ruler()
        self.audio_lane.sync()
        self.audio_controls.sync()
        self.sync_markers()
        self.duration_input.sync()
        self.player.reference_presentation.sync()
        editing = player.editing
        self.undo.disabled = editing or not view.editable() or not view.history.past
        self.redo.disabled = editing or not view.editable() or not view.history.future
        self.undo.tooltip = view.keymap.describe(view.history.undo_description, Action.UNDO)
        self.redo.tooltip = view.keymap.describe(view.history.redo_description, Action.REDO)
        limits = self.zoom_limits()
        if limits and self.scale and limits[1] > limits[0]:
            self.zoom_slider.value = max(0, min(1, math.log(self.scale.pixels_per_second / limits[0]) /
                math.log(limits[1] / limits[0])))
        for control in (self.fit_button, self.zoom_out, self.zoom_in, self.zoom_slider):
            control.disabled = editing or not timeline.frames

    def sync_selection(self):
        selected = self.player.selection.active
        if selected == self.selected:
            return []
        controls = []
        for identifier in {self.selected, selected} - {None}:
            if identifier in self.blocks:
                self.blocks[identifier].box.border = ft.Border.all(1,
                    ft.Colors.PRIMARY if identifier == selected else BORDER)
                controls.append(self.blocks[identifier].box)
        self.selected = selected
        return controls

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

    async def redo_edit(self, e=None):
        if not self.redo.disabled:
            self.player.playing = False
            await self.player.view.graph.redo()

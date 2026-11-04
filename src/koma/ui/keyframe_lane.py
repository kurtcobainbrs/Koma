"""Thin retained lane for the current media's node-owned keyframes."""
import flet as ft
from koma.editor.keyframe_edit import KeyframeEditor
from koma.ui.design import DRAG_INTERVAL_MS, BORDER, MUTED, COMPACT_CONTROL_HEIGHT
from koma.ui.event_updates import explicit_updates

KEYFRAME_HIT_SIZE = COMPACT_CONTROL_HEIGHT


class KeyframePoint:
    def __init__(self, lane, time):
        self.lane, self.time = lane, time
        self.pointer = None
        self.icon = ft.Icon(ft.Icons.CIRCLE, size=9)
        self.content = ft.Container(top=0, width=KEYFRAME_HIT_SIZE, height=lane.strip.style.keyframe_height,
            content=ft.GestureDetector(on_tap=lambda e: lane.editor.select(self.time),
                on_pan_down=self.press, on_pan_start=self.begin, on_pan_update=self.move,
                on_pan_end=self.finish, on_pan_cancel=lambda e: lane.editor.cancel(),
                drag_interval=DRAG_INTERVAL_MS, mouse_cursor=ft.MouseCursor.RESIZE_LEFT_RIGHT,
                content=ft.Container(alignment=ft.Alignment.CENTER, content=self.icon)))

    @explicit_updates
    def press(self, e):
        self.pointer = e.global_position.x

    @explicit_updates
    def begin(self, e):
        self.lane.editor.begin(self.time, self.pointer if self.pointer is not None else e.global_position.x)
        self.lane.editor.move(e.global_position.x)

    @explicit_updates
    def move(self, e):
        self.lane.editor.move(e.global_position.x)

    @explicit_updates
    async def finish(self, e):
        if e is not None and getattr(e, 'global_position', None) is not None:
            self.lane.editor.move(e.global_position.x)
        await self.lane.editor.finish()


class KeyframeLane:
    def __init__(self, strip):
        self.strip = strip
        self.editor = KeyframeEditor(self)
        self.owner = None
        self.points = {}
        self.height = 0
        self.end = 0.0
        self.content = ft.Container(left=0, height=0, visible=False,
            border=ft.Border(bottom=ft.BorderSide(1, BORDER)), content=ft.Stack(clip_behavior=ft.ClipBehavior.HARD_EDGE))

    def frame(self):
        player = self.strip.player
        selected = player.selection.active
        return next((frame for frame in player.timeline.frames if frame.id == selected), None) if player.timeline else None

    def start(self):
        frame = self.frame()
        timeline = self.strip.player.timeline
        return next((start for item, start in zip(timeline.frames, timeline.starts) if frame and item.id == frame.id), 0) if timeline else 0

    def sync(self):
        player = self.strip.player
        frame = self.frame()
        transform = frame.active_media.transform if frame and frame.active_media else None
        self.end = self.start() + max((key.time for key in transform.keyframes), default=0) if transform else 0
        owner = (frame.id, frame.active_media.id) if transform else None
        if owner != self.owner:
            self.editor.selected = None
            self.points = {}
            self.owner = owner
        visible = bool(transform and (transform.keyframes or player.media_transform.panel_open))
        self.height = self.strip.style.keyframe_height if visible else 0
        self.content.height, self.content.visible = self.height, visible
        self.content.top = self.strip.frames_top + self.strip.style.track_height
        self.content.width = self.strip.track.width
        if not visible or not self.strip.scale:
            self.content.content.controls = []
            return
        keys = transform.keyframes
        times = {key.time for key in keys}
        if self.editor.selected not in times:
            self.editor.selected = None
        self.points = {key.time: self.points.get(key.time) or KeyframePoint(self, key.time) for key in keys}
        color = player.view.settings.configuration.values['appearance']['selection']
        for key in keys:
            point = self.points[key.time]
            point.icon.color = color if self.editor.selected == key.time else MUTED if key.time >= frame.duration else ft.Colors.ON_SURFACE
            point.content.left = self.x(key.time)
            point.content.tooltip = f'{round(key.time * player.view.board.fps) + 1:04d} f' + (
                ' · fora do quadro' if key.time >= frame.duration else '') + ' · arraste para mover; Delete para excluir'
        self.content.content.controls = [point.content for point in self.points.values()]

    def x(self, time):
        return self.strip.scale.pixels(self.start() + time) - KEYFRAME_HIT_SIZE / 2

    def preview(self, old_time, time):
        point = self.points.get(old_time)
        if point:
            point.content.left = self.x(time)
            point.icon.color = self.strip.player.view.settings.configuration.values['appearance']['selection']
            self.strip.player.view.page.update(point.content)

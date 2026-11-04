"""Enquadramento proporcional e arraste em memória; salva somente ao soltar."""

import struct
from dataclasses import replace

import flet as ft
from koma.ui.event_updates import explicit_updates

from koma.ui.design import DRAG_INTERVAL_MS, MUTED, RADIUS
from koma.editor.geometry import NODE_WIDTH
from koma.editor.shortcuts import Action
from koma.editor.frame_format import FrameFormat
from koma.ui.drawing_overlay import DrawingOverlay
from koma.ui.image_source import thumbnail_source
from koma.ui.node_layout import NODE_LAYOUT
from koma.ui.retained_container import RetainedContainer
from koma.ui.media_filter import media_filter
from koma.editor.media_geometry import placement
from koma.editor.media_geometry import image_geometry
from koma.ui import drop_runtime
from koma.ui.media_pose import MediaPoseControl
from koma.editor.media_animation import MIN_SCALE, MAX_SCALE, MAX_TRANSLATION, MAX_ROTATION


def png_size(data):
    if data and data[:8] == b'\x89PNG\r\n\x1a\n' and len(data) >= 24:
        return struct.unpack('>II', data[16:24])
    return FrameFormat().size


class ImageViewport:
    @property
    def presentation_key(self):
        frame = self.frame
        return (self.format, self.width, self.height, id(self.image_data),
            (frame.active_media, id(frame.drawing)) if frame else None)

    def __init__(self, view, identifier=None, height=180, *, show_drawing=True):
        self.view, self.identifier = view, identifier
        self.width, self.height = NODE_LAYOUT.image_width(NODE_WIDTH), height
        self.format = None
        self.frame = None
        self.source = FrameFormat().size
        self.drag = None
        self.image = None
        self.image_host = None
        self.image_data = None
        self.pose_control = None
        self.seconds = 0
        self.pose = None
        self.override_pose = None
        self.generation = 0
        self.drawing = DrawingOverlay() if show_drawing else None
        self.stack = ft.Stack(expand=True, clip_behavior=ft.ClipBehavior.HARD_EDGE)
        self.gesture = ft.GestureDetector(content=self.stack, drag_interval=DRAG_INTERVAL_MS,
            on_tap_down=self.select, on_pan_start=self.begin, on_pan_update=self.move,
            on_pan_end=self.end, on_pan_cancel=self.cancel)
        self.content = RetainedContainer(hold_updates=lambda: False,
            aspect_ratio=view.board.frame_format.aspect_ratio, content=self.gesture, border_radius=RADIUS,
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOW, clip_behavior=ft.ClipBehavior.HARD_EDGE,
            on_size_change=self.resized)

    def set_frame(self, frame):
        self.content.bgcolor = self.view.settings.configuration.values['appearance']['preview']
        format = self.view.board.frame_format
        if self.format != format:
            self.format = format
            self.content.aspect_ratio = format.aspect_ratio
            if self.identifier is not None:
                self.width, self.height = NODE_LAYOUT.image_size(NODE_WIDTH, format)
                self.content.width, self.content.height = self.width, self.height
        data = self.view.thumbnails.get(frame.image)
        changed_image = self.frame is None or self.frame.image != frame.image or self.image_data is not data
        changed_transform = self.frame is None or self.frame.active_media != frame.active_media
        if changed_transform:
            self.generation += 1
        self.frame = frame
        if changed_image:
            self.image_data = data
            self.source = png_size(data)
            self.image = ft.Image(src=thumbnail_source(self.view, frame.image),
                fit=ft.BoxFit.FILL, gapless_playback=True,
                filter_quality=ft.FilterQuality.HIGH) if data else None
            self.image_host = ft.Container(content=self.image) if data else None
            if data and drop_runtime.supports('media_pose_v1'):
                self.pose_control = MediaPoseControl(content=RetainedContainer(content=media_filter(self.view, self.image), hold_updates=lambda: False),
                    left=0, right=0, top=0, bottom=0, generation=self.generation,
                    min_scale=MIN_SCALE, max_scale=MAX_SCALE, max_translation=MAX_TRANSLATION, max_rotation=MAX_ROTATION)
            else:
                self.pose_control = None
            self.stack.controls = [self.pose_control] if self.pose_control else [media_filter(self.view,
                ft.Stack(controls=[self.image_host], clip_behavior=ft.ClipBehavior.HARD_EDGE),
                left=0, right=0, top=0, bottom=0)] if data else [ft.Container(left=0, top=0,
                width=self.width, height=self.height, alignment=ft.Alignment.CENTER,
                content=ft.Icon(ft.Icons.IMAGE_OUTLINED, size=28, color=MUTED))]
            if self.drawing:
                self.stack.controls.append(self.drawing.content)
        self.layout()
        if self.image is not None:
            from koma.preview_cache import PREVIEW_SIDES
            maximum = PREVIEW_SIDES[self.view.settings.configuration.values['system']['quality']]
            self.image.cache_width = min(maximum, max(1, self.source[0]))

    def layout(self):
        if self.drawing and self.frame:
            self.drawing.sync(self.frame.drawing, self.width, self.height)
        if self.image is None and self.stack.controls:
            self.stack.controls[0].width, self.stack.controls[0].height = self.width, self.height
        if self.image and self.frame:
            transform = self.frame.active_media.transform
            self.image.scale = None if self.pose_control else ft.Scale(
                scale_x=-1 if transform.flip_x else 1, scale_y=-1 if transform.flip_y else 1)
            if self.pose_control:
                self.pose_control.flip_x, self.pose_control.flip_y = transform.flip_x, transform.flip_y
                w, h, left, top = placement(self.source, (self.width, self.height), transform.fit, transform.crop_x, transform.crop_y)
                self.pose_control.rect = [left / self.width, top / self.height, w / self.width, h / self.height]
                self.pose_control.generation = self.generation
                self.pose_control.set_pose(self.override_pose or transform.at(self.seconds))
            else:
                w, h, left, top, angle = image_geometry(self.source, (self.width, self.height), transform, self.seconds, pose=self.override_pose)
                self.image.width, self.image.height = w, h
                self.image_host.width, self.image_host.height, self.image_host.left, self.image_host.top = w, h, left, top
                self.image_host.rotate = ft.Rotate(angle=angle)
        self.gesture.mouse_cursor = ft.MouseCursor.MOVE if self.can_adjust() else ft.MouseCursor.CLICK
        self.gesture.tooltip = self.view.keymap.describe('Arraste para enquadrar; cancelar', Action.CANCEL) if self.can_adjust() else 'Selecionar quadro'

    def set_time(self, seconds, *, pose=None):
        self.seconds = max(0, seconds)
        self.override_pose = pose
        pose = pose or (self.frame.active_media.transform.at(self.seconds) if self.frame and self.frame.active_media else None)
        if pose == self.pose:
            return None
        self.pose = pose
        self.layout()
        return self.pose_control or self.image_host

    def can_adjust(self):
        return bool(self.identifier and self.image and self.frame
            and self.frame.image_fit == 'cover' and self.view.editable())

    @explicit_updates
    def resized(self, e):
        if not self.view.active or self.view.closing or (self.identifier is None and not self.view.player.presenting):
            return
        if e.width > 0 and e.height > 0 and (e.width, e.height) != (self.width, self.height):
            self.width, self.height = e.width, e.height
            self.layout()
            if not self.view.closing:
                self.view.page.update(self.stack)

    @explicit_updates
    def select(self, e):
        if self.identifier:
            self.view.workspace.navigation.node_click(self.identifier)

    @explicit_updates
    def begin(self, e):
        if not self.can_adjust() or self.view.workspace.navigation.effective_mode != 'select':
            return
        self.view.workspace.navigation.select_node(self.identifier, focus=True)
        self.view.properties.adjusting = self.identifier
        self.drag = self.frame, e.global_position.x, e.global_position.y, self.view.workspace.zoom
        self.view.workspace.viewer.scale_enabled = False
        self.view.workspace.update_interaction()

    @explicit_updates
    def move(self, e):
        if not self.drag:
            return
        frame, px, py, zoom = self.drag
        width, height, _, _ = placement(self.source, (self.width, self.height), 'cover')
        dx, dy = (e.global_position.x-px)/zoom, (e.global_position.y-py)/zoom
        x = max(-1, min(1, frame.crop_x-2*dx/(width-self.width))) if width-self.width > .01 else frame.crop_x
        y = max(-1, min(1, frame.crop_y-2*dy/(height-self.height))) if height-self.height > .01 else frame.crop_y
        self.frame = replace(frame, crop_x=x, crop_y=y)
        self.layout()
        self.view.page.update(self.stack)

    async def end(self, e=None):
        if not self.drag:
            return
        self.drag = None
        self.view.properties.adjusting = None
        self.view.workspace.navigation.sync()
        await self.view.set_frame_properties(self.identifier, crop_x=self.frame.crop_x, crop_y=self.frame.crop_y)

    def cancel(self, e=None):
        if self.drag:
            self.view.properties.adjusting = None
            self.frame = self.drag[0]
            self.drag = None
            self.layout()
            self.view.workspace.navigation.sync()
            self.view.page.update(self.stack)

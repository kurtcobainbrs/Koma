"""Passive timeline preview using the editor's cached image and crop geometry."""
import flet as ft

from koma.editor.framing import placement, png_size
from koma.ui.design import MUTED, RADIUS
from koma.ui.drawing_overlay import DrawingOverlay
from koma.editor.frame_format import FrameFormat
from koma.ui.retained_container import RetainedStack
from koma.ui.media_filter import media_filter


class TimelineThumbnail:
    def __init__(self):
        self.key = None
        self.drawing = DrawingOverlay()
        self.stack = ft.Stack(clip_behavior=ft.ClipBehavior.HARD_EDGE)
        self.canvas = RetainedStack(hold_updates=lambda: False, clip_behavior=ft.ClipBehavior.HARD_EDGE)
        self.presentation = ft.Container(left=0, top=0, content=self.canvas)
        self.stack.controls = [self.presentation]
        self.content = ft.Container(content=self.stack, border_radius=RADIUS,
            clip_behavior=ft.ClipBehavior.HARD_EDGE, bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
            ignore_interactions=True)

    def sync(self, frame, thumbnails, width, height, *, image_source=None, frame_format=None, view=None):
        data = thumbnails.get(frame.image)
        format = frame_format or FrameFormat()
        logical_height = max(1, height)
        logical_width = logical_height * format.aspect_ratio
        self.content.width, self.content.height = width, height
        self.content.visible = width > 0 and height > 0
        scale = max(width / logical_width, height / logical_height)
        self.presentation.width, self.presentation.height = logical_width, logical_height
        self.canvas.width, self.canvas.height = logical_width, logical_height
        self.presentation.scale = ft.Scale(scale=max(scale, .001), alignment=ft.Alignment.TOP_LEFT)
        self.presentation.left = (width - logical_width * scale) / 2
        self.presentation.top = (height - logical_height * scale) / 2
        self.drawing.sync(frame.drawing, logical_width, logical_height)
        key = (frame.image, id(data), image_source if isinstance(image_source, str) else None,
            frame.image_fit, frame.crop_x, frame.crop_y, logical_width, logical_height)
        if key == self.key:
            return
        self.key = key
        if data:
            image_width, image_height, left, top = placement(png_size(data), (logical_width, logical_height),
                frame.image_fit, frame.crop_x, frame.crop_y)
            self.canvas.controls = [ft.Image(src=data if image_source is None else image_source, width=image_width, height=image_height,
                left=left, top=top, fit=ft.BoxFit.FILL, gapless_playback=True)]
            if view is not None:
                self.canvas.controls = [media_filter(view, ft.Stack(controls=self.canvas.controls,
                    clip_behavior=ft.ClipBehavior.HARD_EDGE), left=0, right=0, top=0, bottom=0)]
        else:
            self.canvas.controls = [ft.Container(width=logical_width, height=logical_height,
                alignment=ft.Alignment.CENTER, content=ft.Icon(ft.Icons.IMAGE_OUTLINED,
                    size=logical_height, color=MUTED))]
        self.canvas.controls.append(self.drawing.content)

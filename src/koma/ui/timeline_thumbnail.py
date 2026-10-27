"""Passive timeline preview using the editor's cached image and crop geometry."""
import flet as ft

from koma.editor.framing import placement, png_size
from koma.ui.design import MUTED, RADIUS


class TimelineThumbnail:
    def __init__(self):
        self.key = None
        self.stack = ft.Stack(clip_behavior=ft.ClipBehavior.HARD_EDGE)
        self.content = ft.Container(content=self.stack, border_radius=RADIUS,
            clip_behavior=ft.ClipBehavior.HARD_EDGE, bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
            ignore_interactions=True)

    def sync(self, frame, thumbnails, width, height):
        data = thumbnails.get(frame.image)
        key = (id(data), frame.image_fit, frame.crop_x, frame.crop_y, width, height)
        if key == self.key:
            return
        self.key = key
        self.content.width, self.content.height = width, height
        self.content.visible = width > 0 and height > 0
        if data and self.content.visible:
            image_width, image_height, left, top = placement(png_size(data), (width, height),
                frame.image_fit, frame.crop_x, frame.crop_y)
            self.stack.controls = [ft.Image(src=data, width=image_width, height=image_height,
                left=left, top=top, fit=ft.BoxFit.FILL, gapless_playback=True)]
        else:
            self.stack.controls = [ft.Container(width=width, height=height,
                alignment=ft.Alignment.CENTER, content=ft.Icon(ft.Icons.IMAGE_OUTLINED,
                    size=min(width, height), color=MUTED))]

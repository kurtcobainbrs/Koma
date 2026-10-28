"""Passive vector display shared by preview, nodes and timeline thumbnails."""
import flet as ft
import flet.canvas as cv


class DrawingOverlay:
    def __init__(self):
        self.key = None
        self.layer = None
        self.shapes = {}
        self.canvas = cv.Canvas(shapes=[])
        self.content = ft.Container(left=0, right=0, top=0, bottom=0,
            bgcolor=ft.Colors.TRANSPARENT, ignore_interactions=True, content=self.canvas)

    def sync(self, layer, width, height):
        key = (id(layer), width, height)
        if self.key == key:
            return
        self.key = key
        self.layer = layer
        self.canvas.width, self.canvas.height = width, height
        self.content.visible = layer.visible
        shapes = []
        cached = {}
        if layer.visible and width > 0 and height > 0:
            for stroke in layer.strokes:
                stroke_key = (id(stroke), width, height)
                existing = self.shapes.get(stroke_key)
                if existing is not None:
                    shapes.append(existing[1])
                    cached[stroke_key] = existing
                    continue
                size = stroke.width * min(width, height)
                points = [(x * width, y * height) for x, y in stroke.points]
                if len(points) == 1:
                    shapes.append(cv.Circle(points[0][0], points[0][1], size / 2,
                        paint=ft.Paint(color=stroke.color)))
                else:
                    elements = [cv.Path.MoveTo(*points[0]), *(cv.Path.LineTo(*p) for p in points[1:])]
                    shapes.append(cv.Path(elements, paint=ft.Paint(color=stroke.color, stroke_width=size,
                        stroke_cap=ft.StrokeCap.ROUND, stroke_join=ft.StrokeJoin.ROUND, style=ft.PaintingStyle.STROKE)))
                cached[stroke_key] = (stroke, shapes[-1])
        self.shapes = cached
        self.canvas.shapes = shapes

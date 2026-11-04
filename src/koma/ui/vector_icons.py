"""Small code-native icons missing from the bundled Material icon catalog."""
import flet as ft
import flet.canvas as cv
from math import cos, sin, pi


def magnet_icon(size, color):
    """Solid horseshoe with separated pole tips, tilted like a conventional magnet."""
    scale = size / 24
    angle = pi / 4
    def point(x, y):
        return ((12 + (x - 12) * cos(angle) - (y - 12) * sin(angle)) * scale,
            (12 + (x - 12) * sin(angle) + (y - 12) * cos(angle)) * scale)
    def shape(points):
        vertices = [point(x, y) for x, y in points]
        return cv.Path([cv.Path.MoveTo(*vertices[0]),
            *(cv.Path.LineTo(*vertex) for vertex in vertices[1:]),
            cv.Path.LineTo(*vertices[0])], paint=ft.Paint(color=color, style=ft.PaintingStyle.FILL))
    steps = 16
    outer = [(12 + 8 * cos(pi - i * pi / steps), 12 + 8 * sin(pi - i * pi / steps)) for i in range(steps + 1)]
    inner = [(12 + 4 * cos(i * pi / steps), 12 + 4 * sin(i * pi / steps)) for i in range(steps + 1)]
    body = [(4, 8), *outer, (20, 8), (16, 8), *inner, (8, 8)]
    return cv.Canvas(width=size, height=size, shapes=[shape(body),
        shape(((4, 3), (8, 3), (8, 6.5), (4, 6.5))),
        shape(((16, 3), (20, 3), (20, 6.5), (16, 6.5)))])


def eraser_icon(size, color):
    scale = size / 24
    points = ((3, 14), (12, 5), (15, 5), (22, 12), (13, 21), (10, 21), (3, 14))
    elements = [cv.Path.MoveTo(points[0][0] * scale, points[0][1] * scale),
        *(cv.Path.LineTo(x * scale, y * scale) for x, y in points[1:]),
        cv.Path.MoveTo(8 * scale, 9 * scale), cv.Path.LineTo(17 * scale, 17 * scale)]
    return cv.Canvas(width=size, height=size, shapes=[cv.Path(elements,
        paint=ft.Paint(color=color, stroke_width=1.7 * scale, stroke_cap=ft.StrokeCap.ROUND,
            stroke_join=ft.StrokeJoin.ROUND, style=ft.PaintingStyle.STROKE))])

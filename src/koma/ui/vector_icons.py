"""Small code-native icons missing from the bundled Material icon catalog."""
import flet as ft
import flet.canvas as cv


def eraser_icon(size, color):
    scale = size / 24
    points = ((3, 14), (12, 5), (15, 5), (22, 12), (13, 21), (10, 21), (3, 14))
    elements = [cv.Path.MoveTo(points[0][0] * scale, points[0][1] * scale),
        *(cv.Path.LineTo(x * scale, y * scale) for x, y in points[1:]),
        cv.Path.MoveTo(8 * scale, 9 * scale), cv.Path.LineTo(17 * scale, 17 * scale)]
    return cv.Canvas(width=size, height=size, shapes=[cv.Path(elements,
        paint=ft.Paint(color=color, stroke_width=1.7 * scale, stroke_cap=ft.StrokeCap.ROUND,
            stroke_join=ft.StrokeJoin.ROUND, style=ft.PaintingStyle.STROKE))])

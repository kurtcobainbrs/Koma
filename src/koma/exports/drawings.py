"""Vector-layer rendering for image exports and PDF, independent of Flet."""
from PIL import ImageDraw


def paint_image(image, layer):
    if not layer.visible:
        return
    width, height = image.size
    painter = ImageDraw.Draw(image)
    for stroke in layer.strokes:
        points = [(x * width, y * height) for x, y in stroke.points]
        size = max(1, round(stroke.width * min(width, height)))
        if len(points) > 1:
            painter.line(points, fill=stroke.color, width=size, joint='curve')
        radius = size / 2
        for x, y in (points[0], points[-1]):
            painter.ellipse((x - radius, y - radius, x + radius, y + radius), fill=stroke.color)


def paint_pdf(canvas, layer, x, y, width, height):
    if not layer.visible:
        return
    canvas.saveState()
    clip = canvas.beginPath()
    clip.rect(x, y, width, height)
    canvas.clipPath(clip, stroke=0)
    canvas.setLineCap(1)
    canvas.setLineJoin(1)
    for stroke in layer.strokes:
        size = stroke.width * min(width, height)
        canvas.setStrokeColor(stroke.color)
        canvas.setFillColor(stroke.color)
        canvas.setLineWidth(size)
        points = [(x + px * width, y + (1 - py) * height) for px, py in stroke.points]
        if len(points) == 1:
            canvas.circle(*points[0], size / 2, stroke=0, fill=1)
        else:
            path = canvas.beginPath()
            path.moveTo(*points[0])
            for point in points[1:]:
                path.lineTo(*point)
            canvas.drawPath(path)
    canvas.restoreState()

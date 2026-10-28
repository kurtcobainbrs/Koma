"""Shared vector hit testing and bounded translation, independent of the UI."""
from dataclasses import replace
import math


def stroke_bounds(stroke):
    xs, ys = zip(*stroke.points)
    return min(xs), min(ys), max(xs), max(ys)


def segment_distance(point, first, last):
    dx, dy = last[0] - first[0], last[1] - first[1]
    length = dx * dx + dy * dy
    t = max(0, min(1, ((point[0] - first[0]) * dx + (point[1] - first[1]) * dy) / length)) if length else 0
    return math.hypot(point[0] - first[0] - t * dx, point[1] - first[1] - t * dy)


def stroke_hit(stroke, start, end, radius, aspect):
    sx, sy = max(1, aspect), max(1, 1 / aspect)
    a, b = (start[0] * sx, start[1] * sy), (end[0] * sx, end[1] * sy)
    points = [(x * sx, y * sy) for x, y in stroke.points]
    limit = radius + stroke.width / 2
    for first, last in zip(points, points[1:] or points):
        cross = (b[0] - a[0]) * (last[1] - first[1]) - (b[1] - a[1]) * (last[0] - first[0])
        if cross:
            t = ((first[0] - a[0]) * (last[1] - first[1]) - (first[1] - a[1]) * (last[0] - first[0])) / cross
            u = ((first[0] - a[0]) * (b[1] - a[1]) - (first[1] - a[1]) * (b[0] - a[0])) / cross
            if 0 <= t <= 1 and 0 <= u <= 1:
                return True
        if min(segment_distance(first, a, b), segment_distance(last, a, b),
                segment_distance(a, first, last), segment_distance(b, first, last)) <= limit:
            return True
    return False


def inside_closed_stroke(stroke, point):
    points = stroke.points
    if len(points) < 4 or points[0] != points[-1]:
        return False
    x, y = point
    inside = False
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        if (y1 > y) != (y2 > y) and x < x1 + (x2 - x1) * (y - y1) / (y2 - y1):
            inside = not inside
    return inside


def select_stroke(strokes, point, radius, aspect):
    for index in range(len(strokes) - 1, -1, -1):
        stroke = strokes[index]
        if stroke_hit(stroke, point, point, radius, aspect) or inside_closed_stroke(stroke, point):
            return index
    return None


def translate_stroke(stroke, dx, dy):
    left, top, right, bottom = stroke_bounds(stroke)
    dx, dy = max(-left, min(1 - right, dx)), max(-top, min(1 - bottom, dy))
    return replace(stroke, points=tuple((max(0, min(1, x + dx)), max(0, min(1, y + dy)))
        for x, y in stroke.points))

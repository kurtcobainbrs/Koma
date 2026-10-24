"""Curvas e testes de proximidade em coordenadas do canvas, sem acesso à UI."""

from math import hypot

PORT_Y = 233
INPUT_X = 11
OUTPUT_INSET = 11


def curve(start, end):
    bend = max(60, abs(end[0] - start[0]) * .5)
    return start, (start[0] + bend, start[1]), (end[0] - bend, end[1]), end


def rounded_route(points, radius=18):
    """Polilinha com cantos arredondados, em segmentos Bézier contínuos."""
    segments = []
    current = points[0]
    for previous, corner, following in zip(points, points[1:], points[2:]):
        incoming = hypot(corner[0] - previous[0], corner[1] - previous[1])
        outgoing = hypot(following[0] - corner[0], following[1] - corner[1])
        if not incoming or not outgoing:
            continue
        turn = min(radius, incoming / 2, outgoing / 2)
        before = tuple(corner[k] + (previous[k] - corner[k]) * turn / incoming for k in (0, 1))
        after = tuple(corner[k] + (following[k] - corner[k]) * turn / outgoing for k in (0, 1))
        segments.append((current, current, before, before))
        segments.append((before,
            tuple(before[k] + (corner[k] - before[k]) * 2 / 3 for k in (0, 1)),
            tuple(after[k] + (corner[k] - after[k]) * 2 / 3 for k in (0, 1)), after))
        current = after
    segments.append((current, current, points[-1], points[-1]))
    return tuple(segments)


def route(start, end, source, target):
    """Retornos usam o corredor entre as fileiras, sem a grande diagonal."""
    if end[0] - start[0] >= 48:
        return (curve(start, end),)
    clearance = 24
    right = max(source[2], start[0]) + clearance
    left = min(target[0], end[0]) - clearance
    if target[1] - source[3] >= clearance * 2:
        lane = (source[3] + target[1]) / 2
    elif source[1] - target[3] >= clearance * 2:
        lane = (target[3] + source[1]) / 2
    else:
        lane = max(source[3], target[3], start[1], end[1]) + clearance
    return rounded_route((start, (right, start[1]), (right, lane),
                          (left, lane), (left, end[1]), end))


def sample_route(segments):
    result = []
    for segment in segments:
        a, b, c, d = segment
        points = [a, d] if a == b and c == d else sample(segment, 8 if len(segments) > 1 else 24)
        result.extend(points[bool(result):])
    return result


def sample(points, steps=24):
    a, b, c, d = points
    result = []
    for index in range(steps + 1):
        t = index / steps
        result.append(tuple((1-t)**3*a[k] + 3*(1-t)**2*t*b[k] + 3*(1-t)*t*t*c[k] + t**3*d[k] for k in (0, 1)))
    return result


def distance(point, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    if not dx and not dy:
        return hypot(point[0]-a[0], point[1]-a[1])
    t = max(0, min(1, ((point[0]-a[0])*dx + (point[1]-a[1])*dy)/(dx*dx + dy*dy)))
    return hypot(point[0]-a[0]-t*dx, point[1]-a[1]-t*dy)


def crossing(a, b, c, d):
    if max(a[0], b[0]) < min(c[0], d[0]) or max(c[0], d[0]) < min(a[0], b[0]) or \
       max(a[1], b[1]) < min(c[1], d[1]) or max(c[1], d[1]) < min(a[1], b[1]):
        return False
    def turn(p, q, r):
        return (q[0]-p[0])*(r[1]-p[1]) - (q[1]-p[1])*(r[0]-p[0])
    return turn(a, b, c)*turn(a, b, d) <= 0 and turn(c, d, a)*turn(c, d, b) <= 0


def curve_hits_rectangle(points, rect):
    left, top, right, bottom = rect
    corners = ((left, top), (right, top), (right, bottom), (left, bottom), (left, top))
    return any(left <= x <= right and top <= y <= bottom for x, y in points) or any(
        crossing(a, b, c, d) for a, b in zip(points, points[1:]) for c, d in zip(corners, corners[1:]))

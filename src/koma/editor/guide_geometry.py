"""Normalized guide/camera geometry shared by live preview and MP4."""
import math
from koma.editor.drawing_models import DrawingLayer, DrawingStroke
from koma.editor.camera_models import CAMERA_PRESETS

MAX_CUSTOM_GUIDES = 16


def guide_positions(text):
    if not text.strip():
        return ()
    parts = text.split(';')
    if len(parts) > MAX_CUSTOM_GUIDES:
        raise ValueError(f'Use até {MAX_CUSTOM_GUIDES} guias por direção.')
    try:
        values = tuple(float(part.strip().replace(',', '.')) / 100 for part in parts)
    except ValueError:
        raise ValueError('Separe as guias por ponto e vírgula. Exemplo: 25; 50; 75.') from None
    if any(not math.isfinite(value) or not 0 <= value <= 1 for value in values):
        raise ValueError('As guias devem ficar entre 0 e 100%.')
    return tuple(sorted(set(values)))


def guide_layer(options):
    x, y = set(guide_positions(options['vertical'])), set(guide_positions(options['horizontal']))
    if options['thirds']:
        x.update((1/3, 2/3)); y.update((1/3, 2/3))
    if options['center']:
        x.add(.5); y.add(.5)
    if options['grid']:
        x.update(i / options['columns'] for i in range(1, options['columns']))
        y.update(i / options['rows'] for i in range(1, options['rows']))
    lines = [((v, 0), (v, 1)) for v in sorted(x)] + [((0, v), (1, v)) for v in sorted(y)]
    for enabled, margin in (('safe_action', 'action_margin'), ('safe_title', 'title_margin')):
        if options[enabled]:
            m = options[margin] / 100
            lines.append(((m, m), (1-m, m), (1-m, 1-m), (m, 1-m), (m, m)))
    return DrawingLayer(tuple(DrawingStroke(tuple(points), options['color'], options['width'] / 1080) for points in lines))


def camera_layer(camera, options):
    preset = CAMERA_PRESETS[camera.preset]
    lines = []
    def arrow(start, end):
        lines.append((start, end))
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)
        ux, uy = dx / length * .035, dy / length * .035
        lines.append(((end[0]-ux-uy*.6, end[1]-uy+ux*.6), end,
            (end[0]-ux+uy*.6, end[1]-uy-ux*.6)))
    if camera.visible and preset.kind != 'none':
        if preset.kind == 'arrow':
            dx, dy = preset.direction
            arrow((.5 - dx*.15, .5 - dy*.15), (.5 + dx*.15, .5 + dy*.15))
        elif preset.kind in ('in', 'out'):
            for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
                inner, outer = (.5+dx*.1, .5+dy*.1), (.5+dx*.25, .5+dy*.25)
                arrow(outer, inner) if preset.kind == 'in' else arrow(inner, outer)
        elif preset.kind == 'orbit':
            points = tuple((.5 + .2*math.cos(i*math.pi/16), .5 + .12*math.sin(i*math.pi/16)) for i in range(25))
            if preset.direction[0] < 0:
                points = tuple(reversed(points))
            lines.append(points)
            arrow(points[-3], points[-1])
    return DrawingLayer(tuple(DrawingStroke(tuple(points), options['camera_color'], options['width'] * 2 / 1080) for points in lines))

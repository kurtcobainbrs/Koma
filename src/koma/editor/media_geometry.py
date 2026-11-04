"""Shared fit/crop and affine geometry; drawing layers stay in project space."""
from math import cos, sin, radians


def placement(source, viewport, fit, x=0, y=0):
    sw, sh = source
    vw, vh = viewport
    if fit == 'contain':
        x = y = 0
    scale = (max if fit == 'cover' else min)(vw / max(1, sw), vh / max(1, sh))
    width, height = sw * scale, sh * scale
    return width, height, (vw-width)*(x+1)/2, (vh-height)*(y+1)/2


def inverse_affine(source, viewport, transform, seconds=0):
    vw, vh = viewport
    width, _, left, top = placement(source, viewport, transform.fit, transform.crop_x, transform.crop_y)
    pose = transform.at(seconds)
    angle = radians(pose.rotation)
    c, s = cos(angle), sin(angle)
    fit = width / source[0]
    ox, oy = vw * (.5 + pose.x), vh * (.5 + pose.y)
    return (c / (pose.scale * fit), s / (pose.scale * fit),
        (vw / 2 - left - (c * ox + s * oy) / pose.scale) / fit,
        -s / (pose.scale * fit), c / (pose.scale * fit),
        (vh / 2 - top + (s * ox - c * oy) / pose.scale) / fit)


def image_geometry(source, viewport, transform, seconds=0, *, pose=None):
    width, height, left, top = placement(source, viewport, transform.fit, transform.crop_x, transform.crop_y)
    pose = pose or transform.at(seconds)
    vw, vh = viewport
    c, s = cos(radians(pose.rotation)), sin(radians(pose.rotation))
    bx, by = left + width / 2 - vw / 2, top + height / 2 - vh / 2
    cx = vw * (.5 + pose.x) + pose.scale * (c * bx - s * by)
    cy = vh * (.5 + pose.y) + pose.scale * (s * bx + c * by)
    return width * pose.scale, height * pose.scale, cx - width * pose.scale / 2, cy - height * pose.scale / 2, radians(pose.rotation)

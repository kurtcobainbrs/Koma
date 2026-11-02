"""Timing viewport math; never changes playback position or document durations."""
from koma.editor.timeline import TimeScale


def zoom_limits(width, total, fps, options):
    minimum = width / total * options['timeline_min_zoom'] / 100
    return minimum, max(minimum, width * fps / options['timeline_max_frames'])


def content_width(scale, width, total, options):
    return max(width, scale.pixels(total) + width * options['timeline_tail'])


def zoom_at(scale, offset, width, total, fps, factor, anchor, options):
    low, high = zoom_limits(width, total, fps, options)
    result = TimeScale(max(low, min(high, scale.pixels_per_second * factor)))
    time = scale.seconds(offset + anchor)
    position = max(0, min(content_width(result, width, total, options) - width, result.pixels(time) - anchor))
    return result, position

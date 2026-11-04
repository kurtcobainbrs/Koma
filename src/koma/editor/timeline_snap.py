"""Indexed timeline snapping in absolute time; gestures keep a fixed snapshot."""
from bisect import bisect_left
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class SnapTargets:
    positions: tuple = ()
    sources: tuple = ()
    excluded: frozenset = frozenset()
    extra: tuple = ()
    blocked: frozenset = frozenset()

    def nearest(self, seconds, minimum, maximum):
        index = bisect_left(self.positions, seconds)
        choices = [value for value in self.extra if minimum <= value <= maximum and value not in self.blocked]
        for start, step in ((index - 1, -1), (index, 1)):
            while 0 <= start < len(self.positions):
                value = self.positions[start]
                if value < minimum and step < 0 or value > maximum and step > 0:
                    break
                if minimum <= value <= maximum and value not in self.blocked and any(source not in self.excluded and source[:2] not in self.excluded
                        for source in self.sources[start]):
                    choices.append(value)
                    break
                start += step
        return min(choices, key=lambda value: (abs(value - seconds), value), default=None)


class TimelineSnapping:
    def __init__(self, tolerance):
        self.enabled = True
        self.tolerance = tolerance
        self.timeline = None
        self.targets = SnapTargets()

    def prepare(self, timeline):
        if timeline is self.timeline:
            return
        points = {}
        def add(value, source):
            if math.isfinite(value) and value >= 0:
                points.setdefault(value, set()).add(source)
        for value in (0, timeline.total, *getattr(timeline, 'scene_offsets', {}).values(),
                *getattr(timeline, 'scene_ends', {}).values()):
            add(value, ('boundary', value))
        for frame, start in zip(timeline.frames, timeline.starts):
            for value in (start, start + frame.duration):
                add(value, ('boundary', value))
            if frame.active_media:
                for key in frame.active_media.transform.keyframes:
                    add(start + key.time, ('key', frame.id, key.time))
        for marker in timeline.markers:
            add(marker.position, ('marker', marker.id))
        for track in timeline.audio_tracks:
            for value in (track.start, track.start + track.duration):
                add(value, ('audio', track.id))
        positions = tuple(sorted(points))
        self.targets = SnapTargets(positions, tuple(frozenset(points[value]) for value in positions))
        self.timeline = timeline

    def capture(self, timeline, *, exclude=(), playhead=None, blocked=()):
        self.prepare(timeline)
        return SnapTargets(self.targets.positions, self.targets.sources, frozenset(exclude),
            (playhead,) if playhead is not None else (), frozenset(blocked))

    def resolve(self, seconds, scale, targets, *, minimum=0, maximum=math.inf, edges=(0,)):
        seconds = max(minimum, min(maximum, seconds))
        if not self.enabled or not scale:
            return seconds
        choices = []
        for edge in edges:
            target = targets.nearest(seconds + edge, minimum + edge, maximum + edge)
            if target is not None:
                choices.append(target - edge)
        target = min(choices, key=lambda value: (abs(value - seconds), value), default=seconds)
        return target if abs(scale.pixels(target - seconds)) <= self.tolerance else seconds

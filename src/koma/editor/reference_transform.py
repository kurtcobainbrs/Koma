"""Pure selection transforms and indexed edge/center alignment."""
from bisect import bisect_left
from dataclasses import dataclass, replace
from koma.editor.reference_models import MIN_REFERENCE_SIZE, MAX_REFERENCE_SIZE, MAX_REFERENCE_POSITION


def bounds(items):
    return (min(item.x for item in items), min(item.y for item in items),
        max(item.x + item.width for item in items), max(item.y + item.height for item in items))


def scale_limits(items, left, top):
    low = max(MIN_REFERENCE_SIZE / min(item.width, item.height) for item in items)
    high = min(MAX_REFERENCE_SIZE / max(item.width, item.height) for item in items)
    for item in items:
        for offset, origin in ((item.x - left, left), (item.y - top, top)):
            if offset > 0:
                high = min(high, (MAX_REFERENCE_POSITION - origin) / offset)
    return low, high


def scale_selection(items, dx, dy, *, factor=None):
    left, top, right, bottom = bounds(items)
    width, height = right - left, bottom - top
    if factor is None:
        factor = 1 + (dx * width + dy * height) / (width * width + height * height)
    low, high = scale_limits(items, left, top)
    factor = max(low, min(high, factor))
    return tuple(replace(item, x=left + (item.x - left) * factor,
        y=top + (item.y - top) * factor, width=item.width * factor,
        height=item.height * factor) for item in items)


@dataclass(frozen=True)
class AlignmentIndex:
    x: tuple
    y: tuple

    @classmethod
    def from_items(cls, items):
        items = tuple(items)
        return cls(tuple(sorted({value for item in items for value in
            (item.x, item.x + item.width / 2, item.x + item.width)})),
            tuple(sorted({value for item in items for value in
            (item.y, item.y + item.height / 2, item.y + item.height)})))

    def snap(self, moving_bounds, dx, dy, tolerance, *, smart=True, grid=None):
        left, top, right, bottom = moving_bounds
        def axis(anchors, delta, targets):
            best = None
            if smart:
                for anchor in anchors:
                    point = anchor + delta
                    position = bisect_left(targets, point)
                    for index in (position - 1, position):
                        if 0 <= index < len(targets):
                            correction = targets[index] - point
                            if abs(correction) <= tolerance and (best is None or abs(correction) < abs(best[0])):
                                best = correction, targets[index]
            if best is not None:
                return delta + best[0], best[1]
            if grid:
                point = anchors[0] + delta
                return delta + round(point / grid) * grid - point, None
            return delta, None
        dx, gx = axis((left, (left + right) / 2, right), dx, self.x)
        dy, gy = axis((top, (top + bottom) / 2, bottom), dy, self.y)
        return dx, dy, (gx, gy)

    def scale(self, items, dx, dy, tolerance):
        """Snap one uniform scale factor; never distort or move the fixed corner."""
        preview = scale_selection(items, dx, dy)
        left, top, right, bottom = bounds(items)
        width, height = right - left, bottom - top
        factor = preview[0].width / items[0].width
        low, high = scale_limits(items, left, top)
        best = None
        for origin, size, targets in ((left, width, self.x), (top, height, self.y)):
            for fraction in (.5, 1):
                point = origin + size * factor * fraction
                position = bisect_left(targets, point)
                for index in (position - 1, position):
                    if not 0 <= index < len(targets) or abs(targets[index] - point) > tolerance:
                        continue
                    candidate = (targets[index] - origin) / (size * fraction)
                    if not low <= candidate <= high:
                        continue
                    distance = abs(candidate - factor)
                    if best is None or distance < best[0]:
                        best = distance, candidate
        if best is None:
            return preview, (None, None)
        preview = scale_selection(items, 0, 0, factor=best[1])
        _, _, scaled_right, scaled_bottom = bounds(preview)
        def guide(start, end, targets):
            for point in (end, (start + end) / 2):
                index = bisect_left(targets, point - 1e-7)
                if index < len(targets) and abs(targets[index] - point) <= 1e-7:
                    return targets[index]
            return None
        return preview, (guide(left, scaled_right, self.x), guide(top, scaled_bottom, self.y))

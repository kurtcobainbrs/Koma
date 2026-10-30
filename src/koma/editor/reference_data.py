"""Timing metadata derived from the current immutable timeline, without media work."""
from decimal import Decimal, ROUND_HALF_UP
from koma.exports.video_export import duration_frame_counts
from koma.exports.reference_overlay import frame_references, reference_values


class ReferenceData:
    def __init__(self, player):
        self.player = player
        self.source = self.timing = None
        self.references = self.counts = self.starts = ()
        self.total = 0

    def sync(self):
        timeline = self.player.timeline
        if self.timing is timeline and self.source is not None and self.source[0] is self.player.view.board:
            return
        identifiers = tuple(frame.id for frame in timeline.frames)
        source = (self.player.view.board, identifiers)
        if self.source is None or self.source[0] is not source[0] or self.source[1] != identifiers:
            self.references = frame_references(timeline)
            self.source = source
        if self.timing is not timeline:
            fps = self.player.view.board.fps
            counts = duration_frame_counts((frame.duration for frame in timeline.frames), fps)
            total = int((Decimal(str(timeline.total)) * fps).quantize(Decimal(1), rounding=ROUND_HALF_UP))
            if counts:
                counts[-1] += max(0, total - sum(counts))
            starts, elapsed = [], 0
            for count in counts:
                starts.append(elapsed)
                elapsed += count
            self.starts, self.counts, self.total = tuple(starts), tuple(counts), elapsed
            self.timing = timeline

    def values(self, index, position=None):
        if not 0 <= index < len(self.counts):
            return {}
        fps = self.player.view.board.fps
        start, count = self.starts[index], self.counts[index]
        current = start + 1 if position is None else max(1, min(self.total, int(position * fps + 1e-7) + 1))
        local = max(1, min(count, current - start))
        return reference_values(self.player.timeline.frames[index], self.references[index],
            local_frame=local, count=count, current_frame=current, total_frames=self.total, fps=fps,
            size=self.player.view.board.frame_format.size,
            preferences=self.player.view.settings.configuration.values)

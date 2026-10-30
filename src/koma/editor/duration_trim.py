"""Pure duration constraints for a shared cut or a ripple edit."""
from dataclasses import dataclass
from koma.editor.models import MAX_DURATION
from koma.editor.timeline import snap_duration


@dataclass(frozen=True)
class DurationTrim:
    identifier: str
    duration: float
    following: str | None
    following_duration: float
    fps: int

    @classmethod
    def at(cls, timeline, index):
        frame = timeline.frames[index]
        following = timeline.frames[index + 1] if index + 1 < len(timeline.frames) else None
        return cls(frame.id, frame.duration, following.id if following else None,
            following.duration if following else 0, timeline.board.fps)

    @property
    def originals(self):
        values = {self.identifier: self.duration}
        if self.following is not None:
            values[self.following] = self.following_duration
        return values

    def resolve(self, seconds, *, ripple=False):
        if seconds == self.duration:
            return self.originals if not ripple else {self.identifier: self.duration}
        value = snap_duration(seconds, self.fps)
        if ripple or self.following is None:
            return {self.identifier: value}
        total = self.duration + self.following_duration
        minimum = max(1 / self.fps, total - MAX_DURATION)
        maximum = min(MAX_DURATION, total - 1 / self.fps)
        if minimum > maximum:
            return self.originals
        value = max(minimum, min(maximum, value))
        return {self.identifier: value, self.following: total - value}

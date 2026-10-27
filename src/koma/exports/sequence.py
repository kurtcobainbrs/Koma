"""Immutable export selection: scenes, complete project and frame ranges."""
from dataclasses import dataclass, replace
from itertools import accumulate
import math

from koma.editor.timeline import Timeline
from koma.editor.graph import ordered
from koma.editor.scenes import scene_frames
from types import SimpleNamespace


@dataclass(frozen=True)
class ExportAudio:
    asset: str
    start: float
    duration: float
    volume: float
    muted: bool = False
    source_offset: float = 0


@dataclass(frozen=True)
class ExportSequence:
    frames: tuple
    durations: tuple
    audio_tracks: tuple

    @property
    def starts(self):
        return tuple(accumulate((0, *self.durations)))[:-1]

    @property
    def total(self):
        return sum(self.durations)

    @classmethod
    def from_project(cls, board, roots=None):
        project = ordered(board)
        scenes = [frame for frame in project.frames if frame.node_type.starts_scene]
        if not scenes:
            return cls.from_timelines([Timeline(board)])
        chosen = [root for root in scenes if roots is None or root.id in roots]
        pieces = [Timeline(board, root.id) for root in chosen]
        if roots is None:
            assigned = {frame.id for root in scenes for frame in scene_frames(project, root)}
            orphans = tuple(frame for frame in project.frames if frame.node_type.timed and not frame.muted and frame.id not in assigned)
            if orphans:
                audio = tuple(track for track in board.audio_tracks if not track.scene_id)
                total = max(sum(frame.duration for frame in orphans), *(track.start + track.duration for track in audio), 0)
                pieces.append(SimpleNamespace(frames=orphans, audio_tracks=audio, total=total))
        return cls.from_timelines(pieces)

    @classmethod
    def from_timelines(cls, timelines):
        frames, durations, audio, offset = [], [], [], 0.0
        for timeline in timelines:
            if not timeline.frames:
                continue
            spans = [frame.duration for frame in timeline.frames]
            spans[-1] += timeline.total - sum(spans)
            frames.extend(timeline.frames)
            durations.extend(spans)
            audio.extend(ExportAudio(track.asset, offset + track.start, track.duration,
                track.volume, track.muted) for track in timeline.audio_tracks)
            offset += timeline.total
        return cls(tuple(frames), tuple(durations), tuple(audio))

    def window(self, start, end):
        if not all(math.isfinite(value) for value in (start, end)) or not 0 <= start < end <= self.total + 1e-6:
            raise ValueError('Escolha um intervalo válido dentro da sequência.')
        frames, durations, audio = [], [], []
        for frame, position, duration in zip(self.frames, self.starts, self.durations):
            overlap = min(end, position + duration) - max(start, position)
            if overlap > 1e-9:
                frames.append(frame)
                durations.append(overlap)
        for track in self.audio_tracks:
            overlap = min(end, track.start + track.duration) - max(start, track.start)
            if overlap > 1e-9:
                audio.append(replace(track, start=max(start, track.start) - start, duration=overlap,
                    source_offset=track.source_offset + max(0, start - track.start)))
        return ExportSequence(tuple(frames), tuple(durations), tuple(audio))

"""Immutable export selection: scenes, complete project and frame ranges."""
from dataclasses import dataclass, replace
from itertools import accumulate
import math

from koma.editor.timeline import Timeline
from koma.exports.reference_overlay import frame_references
from koma.editor.project_time import placed_audio, project_layout


@dataclass(frozen=True)
class ExportAudio:
    asset: str
    start: float
    duration: float
    volume: float
    muted: bool = False
    source_offset: float = 0


def coalesced_audio(tracks):
    """Join continuous source windows without opening the music once per scene."""
    result, tails = [], {}
    for track in tracks:
        key = track.asset, track.volume, track.muted
        index = tails.get(key)
        previous = result[index] if index is not None else None
        if previous and abs(previous.start + previous.duration - track.start) < 1e-8 and abs(
                previous.source_offset + previous.duration - track.source_offset) < 1e-8:
            result[index] = replace(previous, duration=previous.duration + track.duration)
        else:
            tails[key] = len(result)
            result.append(track)
    return tuple(result)


@dataclass(frozen=True)
class ExportSequence:
    frames: tuple
    durations: tuple
    audio_tracks: tuple
    source_offsets: tuple = ()
    references: tuple = ()

    @property
    def starts(self):
        return tuple(accumulate((0, *self.durations)))[:-1]

    @property
    def total(self):
        return sum(self.durations)

    @classmethod
    def from_project(cls, board, roots=None):
        from koma.exports.reference_overlay import FrameReference
        index, spans = project_layout(board)
        frames, durations, audio, references = [], [], [], []
        offset = 0.0
        for span in spans:
            if not span.frames or (roots is not None and span.root.id not in roots):
                continue
            length = span.end - span.start
            frames.extend(span.frames)
            durations.extend(frame.duration for frame in span.frames)
            references.extend(FrameReference(span.root, index.production.shots[frame.id], board,
                tuple(index.nodes[key] for key in reversed(index.ancestors(frame.id))),
                index.production.code(span.root.id), index.production.scenes[span.root.id]) for frame in span.frames)
            for track in board.audio_tracks:
                if track.scene_id == span.root.id:
                    placed = placed_audio(track, offset, offset + length)
                    if placed:
                        audio.append(ExportAudio(placed.asset, placed.start, placed.duration, placed.volume, placed.muted,
                            getattr(placed, 'source_offset', 0)))
                elif not track.scene_id:
                    first, end = max(span.start, track.start), min(span.end, track.start + track.duration)
                    if end > first:
                        audio.append(ExportAudio(track.asset, offset + first - span.start, end - first,
                            track.volume, track.muted, first - track.start))
            offset += length
        return cls(tuple(frames), tuple(durations), coalesced_audio(audio), references=tuple(references))

    @classmethod
    def from_timelines(cls, timelines):
        timelines = tuple(timelines)
        frames, durations, audio, references, offset = [], [], [], [], 0.0
        # Project music is sliced at the same absolute scene offsets as pictures.
        # Selected scenes and scene exports retain their exact source position.
        project_offsets = {}
        if timelines:
            board = timelines[0].board
            _, spans = project_layout(board)
            project_offsets = {span.root.id: span.start for span in spans}
        for timeline in timelines:
            if getattr(timeline, 'scene_offsets', None) is not None and timeline.root:
                # A player scene has absolute starts and a project-wide axis;
                # exports consume its local window, never duplicate its music.
                timeline = Timeline(timeline.board, timeline.root.id)
            if not timeline.frames:
                continue
            spans = [frame.duration for frame in timeline.frames]
            frames.extend(timeline.frames)
            references.extend(getattr(timeline, 'references', ()) or frame_references(timeline))
            durations.extend(spans)
            for track in timeline.audio_tracks:
                placed = placed_audio(track, offset, offset + timeline.picture_total)
                if placed:
                    audio.append(ExportAudio(placed.asset, placed.start, placed.duration, placed.volume, placed.muted,
                        getattr(placed, 'source_offset', 0)))
            absolute = project_offsets.get(timeline.root.id if timeline.root else '', 0)
            for track in timeline.board.audio_tracks:
                if track.scene_id:
                    continue
                first, end = max(absolute, track.start), min(absolute + timeline.picture_total, track.start + track.duration)
                if end > first:
                    # No-scene timelines already contain the project track.
                    if timeline.root is None:
                        continue
                    audio.append(ExportAudio(track.asset, offset + first - absolute, end - first,
                        track.volume, track.muted, first - track.start))
            offset += timeline.total
        return cls(tuple(frames), tuple(durations), coalesced_audio(audio), references=tuple(references))

    def window(self, start, end):
        if not all(math.isfinite(value) for value in (start, end)) or not 0 <= start < end <= self.total + 1e-6:
            raise ValueError('Escolha um intervalo válido dentro da sequência.')
        frames, durations, audio, offsets, references = [], [], [], [], []
        for index, (frame, position, duration) in enumerate(zip(self.frames, self.starts, self.durations)):
            overlap = min(end, position + duration) - max(start, position)
            if overlap > 1e-9:
                frames.append(frame)
                if self.references:
                    references.append(self.references[index])
                durations.append(overlap)
                offsets.append((self.source_offsets[index] if self.source_offsets else 0) + max(0, start - position))
        for track in self.audio_tracks:
            overlap = min(end, track.start + track.duration) - max(start, track.start)
            if overlap > 1e-9:
                audio.append(replace(track, start=max(start, track.start) - start, duration=overlap,
                    source_offset=track.source_offset + max(0, start - track.start)))
        return ExportSequence(tuple(frames), tuple(durations), tuple(audio), tuple(offsets), tuple(references))

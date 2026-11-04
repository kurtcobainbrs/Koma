"""Pure placement of optional scene audio on the project's absolute clock."""
from dataclasses import dataclass, fields, replace
from koma.editor.media_models import AudioTrack


@dataclass(frozen=True)
class AudioPlacement(AudioTrack):
    """Derived playback window only; the document keeps the original track."""
    source_offset: float = 0


@dataclass(frozen=True)
class SceneSpan:
    root: object
    frames: tuple
    start: float
    end: float


def project_layout(board):
    """One hierarchy traversal shared by playback, migration and export."""
    from koma.editor.sequences import SequenceIndex
    from koma.editor.scenes import scene_frames
    index = SequenceIndex(board)
    spans, position = [], 0.0
    for root in board.frames:
        if not root.node_type.starts_scene:
            continue
        frames = tuple(frame for frame in scene_frames(board, root, index=index)
            if frame.node_type.timed and not frame.muted and not root.muted)
        end = position + sum(frame.duration for frame in frames)
        spans.append(SceneSpan(root, frames, position, end))
        position = end
    return index, tuple(spans)


def placed_audio(track, offset=0, end=None):
    start = offset + track.start
    skipped = max(0, offset - start)
    start = max(offset, start)
    duration = track.duration - skipped
    if end is not None:
        duration = min(duration, end - start)
    if duration <= 0:
        return None
    if skipped:
        values = {field.name: getattr(track, field.name) for field in fields(AudioTrack)}
        return AudioPlacement(**(values | {'start': start, 'duration': duration}),
            source_offset=getattr(track, 'source_offset', 0) + skipped)
    return replace(track, start=start, duration=duration)


def project_audio_tracks(board, offsets, ends):
    tracks = []
    for track in board.audio_tracks:
        if track.scene_id and track.scene_id not in offsets:
            continue
        placed = placed_audio(track, offsets.get(track.scene_id, 0), ends.get(track.scene_id) if track.scene_id else None)
        if placed:
            tracks.append(placed)
    return tuple(tracks)

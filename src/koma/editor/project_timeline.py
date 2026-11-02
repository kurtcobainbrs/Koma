"""Whole-project playback projected from the existing export selection and nodes."""
from dataclasses import replace
from koma.editor.timeline import Timeline
from koma.exports.sequence import ExportSequence


class ProjectTimeline(Timeline):
    local_editing = False

    def __init__(self, board):
        sequence = ExportSequence.from_project(board)
        self.board, self.root = board, None
        self.frames, self.durations = sequence.frames, sequence.durations
        self.references, self.source_offsets = sequence.references, sequence.source_offsets
        self.starts = list(sequence.starts)
        self.total = self.picture_total = sequence.total
        self.scene_offsets = {}
        scene_ends = {}
        for reference, start, duration in zip(self.references, self.starts, self.durations):
            scope = reference.scene.id if reference.scene else ''
            self.scene_offsets.setdefault(scope, start)
            scene_ends[scope] = start + duration
        self.audio_tracks = tuple(replace(track, start=track.start + self.scene_offsets[track.scene_id])
            for track in board.audio_tracks if track.scene_id in self.scene_offsets)
        self.markers = tuple(sorted((replace(marker,
            position=marker.position + self.scene_offsets[marker.scene_id]) for marker in board.markers
            if marker.scene_id in self.scene_offsets and marker.position <= scene_ends[marker.scene_id] - self.scene_offsets[marker.scene_id]),
            key=lambda marker: (marker.position, marker.id)))

    def with_board(self, board):
        return self if board is self.board else ProjectTimeline(board)


def reordered_scenes(board, source, target, *, after=False):
    """Change only the scene order; graph, internal positions and node data stay intact."""
    scenes = [frame for frame in board.frames if frame.node_type.starts_scene]
    ids = [frame.id for frame in scenes]
    if source == target or source not in ids or target not in ids:
        return board
    nodes = {frame.id: frame for frame in scenes}
    ids.remove(source)
    ids.insert(ids.index(target) + int(after), source)
    reordered = iter(nodes[key] for key in ids)
    return replace(board, frames=tuple(next(reordered) if frame.node_type.starts_scene else frame for frame in board.frames))

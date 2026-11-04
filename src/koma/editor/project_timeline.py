"""Whole-project playback projected from the existing export selection and nodes."""
from dataclasses import replace
from koma.editor.timeline import Timeline
from koma.exports.sequence import ExportSequence
from koma.editor.project_time import project_audio_tracks


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
        self.scene_ends = scene_ends
        self.audio_tracks = project_audio_tracks(board, self.scene_offsets, scene_ends)
        self.markers = tuple(sorted((replace(marker,
            position=marker.position + self.scene_offsets.get(marker.scene_id, 0)) for marker in board.markers
            if not marker.scene_id or (marker.scene_id in self.scene_offsets and marker.position <= scene_ends[marker.scene_id] - self.scene_offsets[marker.scene_id])),
            key=lambda marker: (marker.position, marker.id)))

    def with_board(self, board):
        return self if board is self.board else ProjectTimeline(board)

    def with_durations(self, values):
        preview = super().with_durations(values)
        preview.durations = tuple(frame.duration for frame in preview.frames)
        shifts = tuple((start, values[frame.id] - frame.duration)
            for start, frame in zip(self.starts, self.frames) if frame.id in values)
        def shifted(position):
            return position + sum(delta for start, delta in shifts if start < position)
        preview.scene_offsets = {scope: shifted(start) for scope, start in self.scene_offsets.items()}
        preview.scene_ends = {scope: shifted(end) for scope, end in self.scene_ends.items()}
        preview.audio_tracks = project_audio_tracks(preview.board, preview.scene_offsets, preview.scene_ends)
        if self.root:
            preview.audio_tracks = tuple(track for track in preview.audio_tracks if not track.scene_id or track.scene_id == self.root.id)
        preview.markers = tuple(replace(marker, position=marker.position + preview.scene_offsets.get(marker.scene_id, 0))
            for marker in preview.board.markers if not marker.scene_id or
            (marker.scene_id in preview.scene_offsets and (self.root is None or marker.scene_id == self.root.id)))
        return preview


class SceneTimeline(ProjectTimeline):
    """A scene is a window on project time, never a second clock or soundtrack."""
    local_editing = True

    def __init__(self, board, identifier):
        super().__init__(board)
        from koma.editor.scenes import resolve_scene
        self.root = resolve_scene(board, identifier)
        if self.root is None:
            return
        indices = [i for i, reference in enumerate(self.references)
            if reference.scene and reference.scene.id == self.root.id]
        self.frames = tuple(self.frames[i] for i in indices)
        self.starts = [self.starts[i] for i in indices]
        self.durations = tuple(self.durations[i] for i in indices)
        self.references = tuple(self.references[i] for i in indices)
        self.audio_tracks = tuple(track for track in self.audio_tracks
            if not track.scene_id or track.scene_id == self.root.id)
        self.markers = tuple(marker for marker in self.markers
            if not marker.scene_id or marker.scene_id == self.root.id)

    @property
    def playback_start(self):
        return self.starts[0] if self.starts else 0.0

    @property
    def playback_end(self):
        return self.starts[-1] + self.frames[-1].duration if self.frames else self.playback_start

    def with_board(self, board):
        return self if board is self.board else SceneTimeline(board, self.root.id if self.root else None)


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

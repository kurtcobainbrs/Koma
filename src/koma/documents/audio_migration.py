"""Version 12: promote the first scene soundtrack without discarding other audio."""
from dataclasses import replace


def migrate_project_audio(board):
    if not board.audio_tracks or any(not track.scene_id for track in board.audio_tracks):
        return board
    from koma.editor.project_time import project_layout
    _, spans = project_layout(board)
    for span in spans:
        track = next((item for item in board.audio_tracks if item.scene_id == span.root.id), None)
        if track:
            promoted = replace(track, scene_id='', start=span.start + track.start)
            return replace(board, audio_tracks=tuple(promoted if item.id == track.id else item
                for item in board.audio_tracks))
    return board

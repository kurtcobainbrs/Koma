"""Audio offset drag: transient preview, captured target, one undoable commit."""
from dataclasses import replace
from koma.editor.timeline_navigation import frame_position
from koma.editor.models import MAX_CARDS, MAX_DURATION


class AudioDrag:
    def __init__(self, player):
        self.player = player
        self.snapshot = None
        self.start = None

    def begin(self, e):
        player = self.player
        track = player.media.track
        if not track or not player.view.editable() or player.editing or not player.strip.scale:
            return
        player.strip.duration_input.cancel()
        player.strip.audio_controls.blur()
        player.strip.marker_lane.cancel_rename()
        player.playing = False
        self.snapshot = (player.view.board, player.view.session, track, e.global_position.x, player.strip.scale)
        self.start = track.start
        player.render()
        player.focus_timeline()

    def move(self, e):
        if self.snapshot is None:
            return
        board, session, track, origin, scale = self.snapshot
        if self.player.view.board is not board or self.player.view.session is not session:
            self.cancel()
            return
        seconds = max(0, track.start + scale.seconds(e.global_position.x - origin))
        self.start = frame_position(seconds, MAX_CARDS * MAX_DURATION, board.fps)
        lane = self.player.strip.audio_lane
        lane.sync()
        self.player.view.page.update(lane.content)

    async def end(self, e=None):
        snapshot, start = self.snapshot, self.start
        self.snapshot = self.start = None
        if snapshot:
            board, session, track, _, _ = snapshot
            if self.player.view.board is board and self.player.view.session is session and self.player.opened:
                await self.player.media.change_track(start=start)
        if self.player.opened:
            self.player.render()
            self.player.focus_timeline()

    def cancel(self, e=None, *, update=True):
        self.snapshot = self.start = None
        if update and self.player.opened:
            self.player.render()

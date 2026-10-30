"""Audio gain gesture: native slider preview, single document/history commit."""
from koma.editor.media_models import MAX_AUDIO_VOLUME, finite_range


class AudioVolume:
    def __init__(self, player):
        self.player = player
        self.snapshot = None

    def begin(self, e=None):
        player = self.player
        track = player.media.track
        if not track or not player.view.editable() or player.editing:
            return
        player.playing = False
        self.snapshot = (player.view.board, player.view.session, track)

    async def finish(self, e):
        snapshot, self.snapshot = self.snapshot, None
        player = self.player
        if snapshot:
            board, session, track = snapshot
            value = e.control.value
            if (player.opened and player.view.board is board and player.view.session is session
                    and player.media.track == track and finite_range(value, 0, MAX_AUDIO_VOLUME)
                    and value != track.volume):
                await player.media.change_track(volume=value)
        self.cancel()

    def cancel(self, *, update=True):
        active = self.snapshot is not None
        self.snapshot = None
        if active and update and self.player.opened:
            self.player.render()
            return
        controls = self.player.strip.audio_controls
        controls.sync()
        if update and self.player.opened:
            self.player.view.page.update(controls.content)

"""Timeline keyframe gestures: local preview, one history commit and cancellation."""
from dataclasses import dataclass
from koma.editor.media_animation import key_time, retime_keyframe


@dataclass(frozen=True)
class KeyframeDrag:
    board: object
    session: object
    frame: object
    time: float
    pointer: float
    scale: object


class KeyframeEditor:
    def __init__(self, lane):
        self.lane, self.player = lane, lane.strip.player
        self.drag = None
        self.position = None
        self.selected = None

    def select(self, time):
        if self.player.editing:
            return
        self.selected = time
        self.player.strip.navigator.seek(self.player.timeline.starts[self.player.current] + time)
        self.lane.sync()
        self.player.view.page.update(self.lane.content)
        self.player.focus_timeline()

    def begin(self, time, pointer):
        frame = self.player.media_transform.frame()
        if self.player.editing or not frame or not frame.active_media or not self.player.view.editable():
            return
        self.drag = KeyframeDrag(self.player.view.board, self.player.view.session, frame, time, pointer, self.lane.strip.scale)
        self.position, self.selected = time, time
        self.player.pause_for_edit()
        self.player.set_gesture_locked(True)

    def move(self, pointer):
        drag = self.drag
        if drag is None:
            return
        if self.player.view.board is not drag.board or self.player.view.session is not drag.session or not self.player.presenting:
            self.cancel(update=False)
            return
        self.position = min(max(0, drag.frame.duration - 1 / drag.board.fps),
            key_time(drag.time + drag.scale.seconds(pointer - drag.pointer), drag.board.fps))
        self.lane.preview(drag.time, self.position)

    async def finish(self):
        drag, position = self.drag, self.position
        self.drag, self.position = None, None
        if drag is None:
            return
        view = self.player.view
        try:
            if view.board is not drag.board or view.session is not drag.session or not self.player.opened:
                return
            transform, time = retime_keyframe(drag.frame.active_media.transform, drag.time, position,
                drag.board.fps, drag.frame.duration)
            self.selected = time
            await self.player.media_transform.commit(drag.frame, transform, label='Mover keyframe')
        except ValueError as exc:
            view.notify(str(exc), 'warning')
        finally:
            if self.player.opened:
                self.player.set_gesture_locked(False)
                self.lane.sync()
                view.page.update(self.lane.content)

    def cancel(self, *, update=True):
        self.drag, self.position = None, None
        if update and self.player.opened:
            self.player.set_gesture_locked(False)
            self.lane.sync()
            self.player.view.page.update(self.lane.content)

    async def remove_selected(self):
        frame = self.player.media_transform.frame()
        if self.selected is None or not frame or not frame.active_media or self.player.editing:
            return
        time = self.selected
        self.selected = None
        await self.player.media_transform.remove_key(time)

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
    targets: object
    start: float


class KeyframeEditor:
    def __init__(self, lane):
        self.lane, self.player = lane, lane.strip.player
        self.drag = None
        self.position = None
        self.selected = None

    def clear_selection(self):
        selected, self.selected = self.selected, None
        return selected is not None

    def select(self, time):
        if self.player.editing:
            return
        self.player.edit_selection.claim(self)
        self.selected = time
        self.player.pause_for_edit()
        frame = self.lane.frame()
        # Selecting a preserved key must not switch its owner to the next shot.
        if frame and time < frame.duration:
            self.player.strip.navigator.seek(self.lane.start() + time)
        else:
            self.player.render_position()
        self.lane.sync()
        self.player.view.page.update(self.lane.content)
        self.player.focus_timeline()

    def begin(self, time, pointer):
        frame = self.lane.frame()
        if self.player.editing or not frame or not frame.active_media or not self.player.view.editable():
            return
        self.player.edit_selection.claim(self)
        targets = self.player.snapping.capture(self.player.timeline, exclude=(('key', frame.id, time),),
            playhead=self.player.position if abs(self.player.position - self.lane.start() - time) > 1e-8 else None,
            blocked=(self.lane.start() + key.time for key in frame.active_media.transform.keyframes
                if abs(key.time - time) > 1e-8))
        self.drag = KeyframeDrag(self.player.view.board, self.player.view.session, frame, time, pointer,
            self.lane.strip.scale, targets, self.lane.start())
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
        from koma.editor.media_animation import MAX_KEYFRAME_TIME
        seconds = self.player.snapping.resolve(drag.start + drag.time + drag.scale.seconds(pointer - drag.pointer),
            drag.scale, drag.targets, minimum=drag.start, maximum=drag.start + MAX_KEYFRAME_TIME)
        self.position = key_time(seconds - drag.start, drag.board.fps)
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
                drag.board.fps, drag.frame.duration, allow_outside=True)
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
        frame = self.lane.frame()
        if self.selected is None or not frame or not frame.active_media or self.player.editing:
            return
        time = self.selected
        self.selected = None
        await self.player.media_transform.remove_key(time, frame=frame)

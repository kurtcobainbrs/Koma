"""Staged per-media animation commands; native pointer movement never edits data."""
from dataclasses import dataclass, replace
from math import ceil
from koma.editor.media_animation import MediaPose, update_pose, key_time, remove_keyframe


@dataclass(frozen=True)
class TransformGesture:
    board: object
    session: object
    frame: object
    time: float
    generation: int


@dataclass(frozen=True)
class TemporaryMediaPose:
    owner: tuple
    pose: MediaPose


class MediaTransformEditor:
    def __init__(self, player):
        self.player, self.view = player, player.view
        self.enabled = False
        self.panel_open = False
        self.tool = 'move'
        self.drag = None
        self.committing = False
        self.last_time = 0
        self.playback_owner = None
        self.temporary = None
        options = self.view.settings.configuration.values['animatic']
        self.auto_key = options['media_auto_key']
        self.interpolation = options['media_interpolation']
        from koma.ui.media_transform_tools import MediaTransformTools
        self.ui = MediaTransformTools(self)

    def frame(self):
        player = self.player
        return player.timeline.frames[player.current] if player.timeline and 0 <= player.current < len(player.timeline.frames) else None

    def local_time(self):
        frame = self.frame()
        if frame is None:
            return 0
        return min(frame.duration, max(0, self.player.position - self.player.timeline.starts[self.player.current]))

    def time(self):
        frame = self.frame()
        if frame is None:
            return 0
        fps = self.view.board.fps
        last_frame = max(0, ceil(frame.duration * fps - 1e-8) - 1) / fps
        return min(last_frame, key_time(self.local_time(), fps))

    def owner(self):
        frame = self.frame()
        return (self.view.session, frame.id, frame.active_media.id, frame.active_media.transform.base_signature, self.time()) if frame and frame.active_media else None

    def effective_pose(self):
        if self.temporary and self.temporary.owner == self.owner():
            return self.temporary.pose
        self.temporary = None
        frame = self.frame()
        return frame.active_media.transform.at(self.local_time()) if frame and frame.active_media else MediaPose()

    async def apply_pose(self, pose, *, record=False):
        try:
            return await self._apply_pose(pose, record=record)
        except ValueError as exc:
            self.view.notify(str(exc), 'warning')
            self.cancel()
            return False

    async def _apply_pose(self, pose, *, record=False):
        pose.validate()
        frame = self.frame()
        if not frame or not frame.active_media or not self.view.editable():
            return
        if record or self.auto_key:
            transform = update_pose(frame.active_media.transform, pose, self.time(), self.view.board.fps,
                auto_key=True, interpolation=self.interpolation)
            self.temporary = None
            await self.commit(frame, transform, label='Gravar keyframe')
        else:
            self.player.preview.generation += 1
            self.player.set_gesture_locked(False)
            self.show_temporary(pose)

    def show_temporary(self, pose):
        pose.validate()
        self.temporary = TemporaryMediaPose(self.owner(), pose)
        self.player.preview.set_time(self.local_time(), pose=pose)
        self.ui.sync()
        native = self.player.preview.pose_control
        from koma.ui.retained_container import retain_children
        if native:
            native.generation = self.player.preview.generation
            native.set_pose(pose)
            with retain_children(native.content):
                self.view.page.update(native, *(scrub.text for scrub in self.ui.scrubs.values()), self.ui.temporary_hint)
        else:
            self.view.page.update(self.player.preview.image_host, *(scrub.text for scrub in self.ui.scrubs.values()), self.ui.temporary_hint)

    async def reset(self, channel):
        if self.player.editing:
            return
        values = {'move': {'x': 0, 'y': 0}, 'rotate': {'rotation': 0}, 'scale': {'scale': 1}}
        await self.apply_pose(replace(self.effective_pose(), **values[channel]))

    async def flip(self, axis):
        frame = self.frame()
        if frame:
            await self.view.node_media.flip(frame.id, axis)

    def seek_preview(self):
        native = self.player.preview.pose_control
        time = self.local_time()
        if self.player.playing and self.temporary:
            self.temporary = None
            self.player.preview.set_time(time)
        if native and self.player.playing:
            frame = self.frame()
            owner = (frame.id, frame.active_media_id) if frame else None
            reset = not native.playing or owner != self.playback_owner or time < self.last_time
            self.playback_owner = owner
            self.last_time = time
            if reset:
                native.seconds, native.playing = time, True
                native.playback_revision += 1
                self.ui.sync()
                return native
            return None
        stopped = native and native.playing
        if native:
            native.playing = False
        self.last_time = time
        control = self.player.preview.set_time(time, pose=self.effective_pose() if self.temporary else None) if self.frame() else None
        self.ui.sync()
        return control or (native if stopped else None)

    def sync(self):
        control = self.player.preview.pose_control
        if control:
            control.editing = self.enabled and self.view.editable() and not self.player.playing
            control.tool = self.tool
            control.on_begin, control.on_commit, control.on_cancel = self.begin, self.finish, self.cancel_event
            frame = self.frame()
            transform = frame.active_media.transform if frame and frame.active_media else None
            control.maximum_time = max(0, frame.duration - 1 / self.view.board.fps) if frame else 0
            control.keyframes = [{'time': key.time, 'x': key.pose.x, 'y': key.pose.y, 'scale': key.pose.scale,
                'rotation': key.pose.rotation, 'interpolation': key.interpolation} for key in transform.keyframes] if transform else []
        self.seek_preview()

    def activate(self, enabled=None):
        if self.player.editing or not self.player.opened or not self.view.editable():
            return
        previous = self.panel_open
        self.panel_open = not self.panel_open if enabled is None else enabled
        self.sync()
        self.player.drawing_surface.sync()
        if previous != self.panel_open:
            self.player.strip.sync()
            self.view.page.update(self.player.layout.timeline)
        self.view.page.update(self.ui.content, self.player.drawing_slot,
            self.player.drawing_surface.content, self.player.preview.stack, self.player.layout.body)
        self.player.focus_timeline()

    def choose_tool(self, tool):
        if self.player.editing or not self.player.opened or not self.view.editable():
            return
        self.tool = tool
        self.enabled = True
        self.player.pause_for_edit()
        self.player.drawing.clear_selection()
        self.activate(True)
        control = self.player.preview.pose_control
        if control:
            control.start_request += 1
            self.view.page.update(control)

    def use_drawing(self):
        """Change input ownership without moving or closing either tool panel."""
        if not self.enabled:
            return
        self.enabled = False
        self.sync()
        controls = [self.ui.panel]
        if self.player.preview.pose_control:
            controls.append(self.player.preview.pose_control)
        self.view.page.update(*controls)

    def begin(self, e):
        frame = self.frame()
        if not self.enabled or self.player.editing or not self.view.editable() or not frame or not frame.active_media:
            return
        if e.generation != self.player.preview.generation:
            return
        self.player.pause_for_edit()
        self.drag = TransformGesture(self.view.board, self.view.session, frame, self.time(), e.generation)
        self.player.set_gesture_locked(True)

    async def finish(self, e):
        drag = self.drag
        if drag is None:
            self.cancel(update=self.player.presenting)
            return
        if e.generation != drag.generation:
            return
        self.drag = None
        if self.view.board is not drag.board or self.view.session is not drag.session or not self.player.opened:
            self.cancel()
            return
        try:
            pose = MediaPose(e.x, e.y, e.scale, e.rotation)
            await self.apply_pose(pose)
        except ValueError as exc:
            self.view.notify(str(exc), 'warning')
            self.cancel()

    async def commit(self, frame, transform, *, label='Transformar mídia'):
        if not frame or not frame.active_media or not self.view.editable():
            return
        transform.validate()
        self.committing = True
        self.player.pause_for_edit()
        try:
            if transform != frame.active_media.transform:
                active = replace(frame.active_media, transform=transform)
                media = tuple(active if item.id == active.id else item for item in frame.media)
                await self.view.set_frame_properties(frame.id, media=media, label=label)
        finally:
            self.committing = False
            self.player.preview.generation += 1
            self.player.set_gesture_locked(False)
            if self.player.opened:
                self.player.rebuild_timeline()
                self.player.render()
                self.player.focus_timeline()

    def cancel_event(self, e):
        if self.drag and e.generation == self.drag.generation:
            self.cancel()

    def cancel(self, *, update=True):
        self.drag = None
        self.player.preview.generation += 1
        control = self.player.preview.pose_control
        if control:
            control.generation = self.player.preview.generation
        if update and self.player.opened:
            self.player.set_gesture_locked(False)
            self.sync()
            self.view.page.update(self.player.preview.stack, self.ui.panel)

    async def set_key(self, *, remove_only=False):
        try:
            await self._edit_key(remove_only=remove_only)
        except ValueError as exc:
            self.view.notify(str(exc), 'warning')

    async def remove_key(self, time, *, frame=None):
        frame = frame or self.frame()
        if self.player.editing or not frame or not frame.active_media or not self.view.editable():
            return
        transform = remove_keyframe(frame.active_media.transform, time)
        if transform == frame.active_media.transform:
            return
        # Keep the visible pose as an unrecorded preview. The saved base and
        # history contain only the key deletion, so Play still uses saved data.
        if frame is self.frame():
            pose = self.effective_pose()
            self.temporary = TemporaryMediaPose(self.owner(), pose)
        await self.commit(frame, transform, label='Remover keyframe')

    async def _edit_key(self, *, remove_only=False):
        frame = self.frame()
        if self.player.editing or not frame or not frame.active_media:
            return
        transform = frame.active_media.transform
        time = self.time()
        existing = next((key for key in transform.keyframes if abs(key.time - time) < 1e-8), None)
        if remove_only and not existing:
            return
        if remove_only and existing:
            await self.remove_key(time)
            return
        else:
            transform = update_pose(transform, self.effective_pose(), time, self.view.board.fps,
                auto_key=True, interpolation=self.interpolation)
        self.temporary = None
        await self.commit(frame, transform, label='Remover keyframe' if remove_only else 'Gravar keyframe')

    def adjacent_keyframe(self, direction, *, during_playback=False):
        frame = self.frame()
        if not frame or not frame.active_media:
            return None
        time = self.local_time()
        keys = frame.active_media.transform.keyframes
        ordered = keys if direction > 0 else reversed(keys)
        return next((key.time for key in ordered if 0 <= key.time < frame.duration
            and (during_playback or (key.time - time) * direction > 1e-8)), None)

    def jump(self, direction):
        if self.player.editing:
            return
        target = self.adjacent_keyframe(direction)
        if target is not None:
            self.player.strip.navigator.seek(self.player.timeline.starts[self.player.current] + target, exact=True)

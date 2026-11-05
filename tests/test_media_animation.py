"""Model, transaction and export integrations for owned media animation."""
from dataclasses import replace
from types import SimpleNamespace as Data
from unittest import TestCase
from unittest.mock import Mock, patch
from io import BytesIO
from PIL import Image
from koma.editor.media_animation import MediaPose, MediaKeyframe, update_pose, MAX_KEYFRAMES
from koma.editor.node_media import MediaTransform
from koma.documents.session import DocumentSession
from koma.documents.store import document, parse_document
from koma.editor.node_clipboard import capture_selection, NodeClipboard
from koma.editor.view import StoryboardView
from koma.exports.video_frames import StoryboardFrames
from koma.exports.video_export import FrameComposer
from koma.editor.media_geometry import image_geometry, inverse_affine
from tests import test_storyboard as fixtures
import json
from inspect import iscoroutinefunction
from uuid import uuid4


class MediaAnimationTests(TestCase):
    setUp = fixtures.StoryboardTests.setUp
    view = fixtures.StoryboardTests.view

    def editor(self):
        view = self.view()
        values = view.settings.configuration.editable()
        values['animatic']['initial_scope'] = 'Primeira cena'
        fixtures.finish(view.settings.configuration.commit(values))
        fixtures.finish(view.import_paths([self.source]))
        view.player.open()
        editor = view.player.media_transform
        editor.enabled = True
        return view, editor

    def test_button_handlers_await_record_overwrite_delete_and_flip_commands(self):
        view, editor = self.editor()
        flips = view.properties.media_list.flips
        for button in (editor.ui.key, editor.ui.delete_key, *flips.values()):
            self.assertTrue(iscoroutinefunction(button.on_click))
        before, count = view.board, len(view.history.past)
        fixtures.finish(editor.ui.key.on_click(None))
        self.assertEqual(len(editor.frame().active_media.transform.keyframes), 1)
        self.assertEqual(len(view.history.past), count + 1)
        editor.show_temporary(MediaPose(.2))
        fixtures.finish(editor.ui.key.on_click(None))
        keys = editor.frame().active_media.transform.keyframes
        self.assertEqual(len(keys), 1)
        self.assertEqual(keys[0].pose.x, .2)
        fixtures.finish(editor.ui.delete_key.on_click(None))
        self.assertEqual(editor.frame().active_media.transform.keyframes, ())
        fixtures.finish(view.graph.undo())
        self.assertEqual(editor.frame().active_media.transform.keyframes, keys)
        fixtures.finish(view.graph.redo())
        self.assertEqual(editor.frame().active_media.transform.keyframes, ())
        fixtures.finish(flips['horizontal'].on_click(None))
        self.assertTrue(editor.frame().active_media.transform.flip_x)
        self.assertEqual(before.frames[0].active_media.transform.keyframes, ())

    def test_flip_properties_target_selected_node_instead_of_playhead_and_update_native_view(self):
        with patch('koma.ui.drop_runtime.supports', side_effect=lambda capability: capability == 'media_pose_v1'):
            view = self.view()
            fixtures.finish(view.import_paths([self.source, self.source]))
            first, second = view.board.frames
            player = view.player
            player.open()
            player.select_node(first.id, seek=True)
            player.select_node(second.id)
            controls = view.properties.media_list
            self.assertEqual(controls.identifier, second.id)
            self.assertEqual(player.timeline.frames[player.current].id, first.id)
            before = view.board
            fixtures.finish(controls.flips['horizontal'].on_click(None))
            self.assertFalse(next(frame for frame in view.board.frames if frame.id == first.id).active_media.transform.flip_x)
            self.assertTrue(next(frame for frame in view.board.frames if frame.id == second.id).active_media.transform.flip_x)
            self.assertTrue(view.cards[second.id].viewport.pose_control.flip_x)
            self.assertFalse(player.preview.pose_control.flip_x)
            self.assertFalse(hasattr(player.media_transform.ui, 'flips'))
            fixtures.finish(view.graph.undo())
            self.assertEqual(view.board, before)
            fixtures.finish(view.graph.redo())
            self.assertTrue(view.cards[second.id].viewport.pose_control.flip_x)

    def test_keyframe_buttons_seek_exactly_in_a_shot_with_fractional_start_and_duration(self):
        view, editor = self.editor()
        fps = view.board.fps
        first = replace(view.board.frames[0], duration=2.6 / fps)
        key = MediaKeyframe(2 / fps, MediaPose(.25))
        media = first.active_media
        animated = replace(media, transform=replace(media.transform,
            keyframes=(MediaKeyframe(0, MediaPose()), key)))
        second = replace(first, id=uuid4().hex, media=(animated,))
        view.changed(replace(view.board, frames=(first, second)))
        view.refresh()
        player = view.player
        player.render()
        player.select_node(second.id, seek=True)
        self.assertFalse(editor.ui.next.disabled)
        fixtures.finish(editor.ui.next.on_click(None))
        self.assertAlmostEqual(player.position, first.duration + key.time)
        self.assertAlmostEqual(editor.effective_pose().x, .25)
        self.assertTrue(editor.ui.next.disabled)
        fixtures.finish(editor.ui.previous.on_click(None))
        self.assertAlmostEqual(player.position, first.duration)
        self.assertEqual(editor.frame().id, second.id)
        self.assertTrue(editor.ui.previous.disabled)

    def test_playback_clock_restarts_for_new_shot_with_same_image_but_not_periodic_updates(self):
        with patch('koma.ui.drop_runtime.supports', side_effect=lambda capability: capability == 'media_pose_v1'):
            view = self.view()
            fixtures.finish(view.import_paths([self.source]))
            first = replace(view.board.frames[0], duration=1 / view.board.fps)
            second = replace(first, id=uuid4().hex, duration=1)
            view.changed(replace(view.board, frames=(first, second)))
            view.refresh()
            player = view.player
            player.open()
            player.position = 0
            player.playing = True
            player.render()
            native = player.preview.pose_control
            revision = native.playback_revision
            player.position = first.duration + .01
            player.render_position()
            self.assertIs(player.preview.pose_control, native)
            self.assertEqual(native.playback_revision, revision + 1)
            self.assertAlmostEqual(native.seconds, .01)
            revision = native.playback_revision
            for seconds in (.02, .03, .04):
                player.position = first.duration + seconds
                player.render_position()
                self.assertEqual(native.playback_revision, revision)

    def test_clicking_blocks_immediately_publishes_their_keys_without_play_or_edit(self):
        view = self.view()
        fixtures.finish(view.import_paths([self.source, self.source, self.source]))
        first, second, empty = view.board.frames
        def animated(frame, end):
            transform = MediaTransform(keyframes=(MediaKeyframe(0, MediaPose()), MediaKeyframe(end, MediaPose(.2))))
            return replace(frame, media=(replace(frame.active_media, transform=transform),))
        first, second = animated(first, .5), animated(second, 1)
        view.changed(replace(view.board, frames=(first, second, empty)))
        view.refresh()
        player = view.player
        player.open()
        player.strip.resized(Data(width=800))
        before, count = view.board, len(view.history.past)
        with patch.object(view, 'refresh', side_effect=AssertionError('Full canvas rebuild')):
            for frame, expected in ((second, {0, 1}), (empty, set()), (first, {0, .5})):
                view.page.update.reset_mock()
                player.strip.blocks[frame.id].seek(None)
                lane = player.strip.keyframe_lane
                self.assertEqual(lane.owner, (frame.id, frame.active_media.id))
                self.assertEqual(set(lane.points) if lane.height else set(), expected)
                self.assertFalse(player.playing)
                published = [control for call in view.page.update.call_args_list for control in call.args]
                self.assertTrue(any(control is lane.content or control is player.layout.timeline for control in published))
                if not expected:
                    self.assertTrue(any(control is player.layout.timeline for control in published))
        self.assertIs(view.board, before)
        self.assertEqual(len(view.history.past), count)

    def test_animation_toolbar_groups_controls_and_keeps_subtitles_and_key_navigation(self):
        view, editor = self.editor()
        player = view.player
        fixtures.finish(editor.commit(editor.frame(), MediaTransform(keyframes=(
            MediaKeyframe(0, MediaPose()), MediaKeyframe(1, MediaPose(.2))))))
        player.strip.resized(Data(width=800))
        self.assertIn(editor.ui.animation, player.toolbar.playback.controls)
        self.assertNotIn(editor.ui.animation, editor.ui.detail.controls)
        self.assertNotIn(editor.ui.interpolation.content, editor.ui.detail.controls)
        self.assertIn(player.show_subtitles, player.toolbar.playback.controls)
        self.assertIn(player.loop, player.toolbar.playback.controls)
        transport = next(control for control in player.toolbar.playback.controls
            if hasattr(control, 'controls') and player.play in control.controls)
        self.assertIn(editor.ui.previous, transport.controls)
        self.assertIn(editor.ui.next, transport.controls)
        self.assertIsNotNone(player.show_subtitles.on_click)
        before, count = view.board, len(view.history.past)
        editor.ui.next.on_click(None)
        self.assertEqual(player.position, 1)
        editor.ui.previous.on_click(None)
        self.assertEqual(player.position, 0)
        view.page.update.reset_mock()
        editor.ui.toggle_auto()
        self.assertTrue(any(editor.ui.animation in call.args for call in view.page.update.call_args_list))
        self.assertIs(view.board, before)
        self.assertEqual(len(view.history.past), count)

    def test_normalized_interpolation_static_edits_and_limits(self):
        transform = update_pose(MediaTransform(), MediaPose(.1, -.1, 2, 90), 0, 24)
        self.assertFalse(transform.keyframes)
        transform = update_pose(transform, MediaPose(), 0, 24, auto_key=True)
        transform = update_pose(transform, MediaPose(1, 1, 3, 180), 1, 24, auto_key=True)
        self.assertEqual(transform.at(.5), MediaPose(.5, .5, 2, 90))
        self.assertEqual(transform.at(8), transform.keyframes[-1].pose)
        held = replace(transform, keyframes=(replace(transform.keyframes[0], interpolation='hold'), transform.keyframes[1]))
        self.assertEqual(held.at(.5), MediaPose())
        with self.assertRaises(ValueError):
            MediaPose(scale=0).validate()
        with self.assertRaises(ValueError):
            replace(transform, keyframes=(transform.keyframes[0],) * (MAX_KEYFRAMES + 1)).validate()

    def test_gesture_cancel_commit_history_persistence_and_copy_between_projects(self):
        view, editor = self.editor()
        before, count = view.board, len(view.history.past)
        event = Data(generation=view.player.preview.generation, x=.2, y=.1, scale=1.5, rotation=30)
        editor.begin(event)
        self.assertIs(view.board, before)
        editor.cancel()
        self.assertIs(view.board, before)
        event.generation = view.player.preview.generation
        editor.auto_key = True
        editor.begin(event)
        with patch.object(view, 'refresh', side_effect=AssertionError('Full canvas rebuild')):
            fixtures.finish(editor.finish(event))
        frame = view.board.frames[0]
        self.assertEqual(frame.active_media.transform.at(0), MediaPose(.2, .1, 1.5, 30))
        self.assertEqual(len(view.history.past), count + 1)
        changed = view.board
        fixtures.finish(view.graph.undo())
        self.assertEqual(view.board, before)
        fixtures.finish(view.graph.redo())
        self.assertEqual(view.board, changed)
        path = view.session.save(view.board, self.root / 'animated.koma')
        opened = DocumentSession.open(path, self.root / 'other')
        self.addCleanup(opened.close)
        self.assertEqual(opened.board, view.board)
        target_session = DocumentSession(self.root / 'target')
        self.addCleanup(target_session.close)
        target = StoryboardView(Mock(), target_session, view.settings)
        fixtures.finish(target.activate())
        payload = fixtures.finish(capture_selection(view.board, view.store, {frame.id}))
        fixtures.finish(NodeClipboard().insert(target, payload))
        self.assertEqual(target.board.frames[0].active_media.transform, frame.active_media.transform)

    def test_keys_are_owned_by_media_and_do_not_change_shot_duration(self):
        view, editor = self.editor()
        before = view.board.frames[0]
        fixtures.finish(editor.set_key())
        self.assertEqual(len(view.board.frames[0].active_media.transform.keyframes), 1)
        view.player.position = .5
        view.player.render_position()
        editor.ui.fields['x'].value = '10*2'
        fixtures.finish(editor.ui.apply())
        self.assertEqual(len(view.board.frames[0].active_media.transform.keyframes), 1)
        self.assertEqual(editor.effective_pose().x, .2)
        fixtures.finish(editor.set_key())
        frame = view.board.frames[0]
        self.assertEqual(frame.duration, before.duration)
        self.assertEqual(frame.active_media.transform.at(.5).x, .2)
        self.assertEqual(len(frame.active_media.transform.keyframes), 2)
        self.assertEqual(frame.media[0].transform, frame.active_media.transform)

    def test_autokey_off_keeps_temporary_pose_and_I_overwrites_without_deleting(self):
        view, editor = self.editor()
        before, count = view.board, len(view.history.past)
        pose = MediaPose(.25, -.15, 2, 45)
        fixtures.finish(editor.apply_pose(pose))
        self.assertIs(view.board, before)
        self.assertEqual(len(view.history.past), count)
        self.assertEqual(editor.effective_pose(), pose)
        fixtures.finish(editor.set_key())
        self.assertEqual(editor.frame().active_media.transform.at(0), pose)
        self.assertEqual(len(editor.frame().active_media.transform.keyframes), 1)
        saved = view.board
        fixtures.finish(editor.apply_pose(MediaPose(.7, 0, 1, 0)))
        self.assertIs(view.board, saved)
        view.player.playing = True
        editor.seek_preview()
        self.assertIsNone(editor.temporary)
        self.assertEqual(view.player.preview.pose, pose)
        view.player.playing = False
        fixtures.finish(editor.apply_pose(MediaPose(.5)))
        fixtures.finish(editor.set_key())
        self.assertEqual(len(editor.frame().active_media.transform.keyframes), 1)
        self.assertEqual(editor.frame().active_media.transform.at(0).x, .5)

    def test_resets_and_numeric_drag_are_temporary_until_key_is_recorded(self):
        view, editor = self.editor()
        before = view.board
        fixtures.finish(editor.apply_pose(MediaPose(.2, .3, 2, 45)))
        fixtures.finish(view.player.key_down(Data(key='G', alt=True, ctrl=False, meta=False, shift=False)))
        self.assertEqual(editor.effective_pose(), MediaPose(0, 0, 2, 45))
        fixtures.finish(view.player.key_down(Data(key='R', alt=True, ctrl=False, meta=False, shift=False)))
        fixtures.finish(view.player.key_down(Data(key='S', alt=True, ctrl=False, meta=False, shift=False)))
        self.assertEqual(editor.effective_pose(), MediaPose())
        self.assertIs(view.board, before)
        scrub = editor.ui.scrubs['x']
        scrub.press(Data(global_position=Data(x=100)))
        scrub.begin(Data(global_position=Data(x=100)))
        scrub.move(Data(global_position=Data(x=150)))
        self.assertIs(view.board, before)
        fixtures.finish(scrub.finish())
        self.assertAlmostEqual(editor.effective_pose().x, .05)
        fixtures.finish(editor.set_key())
        self.assertAlmostEqual(editor.frame().active_media.transform.at(0).x, .05)

    def test_transform_controls_live_in_an_independent_side_panel(self):
        view, editor = self.editor()
        self.assertIs(editor.ui.content, editor.ui.toggle)
        editor.activate(True)
        self.assertTrue(editor.ui.panel.visible)
        self.assertTrue(view.player.layout.media_splitter.content.visible)
        self.assertTrue(all(scrub.readout.visible for scrub in editor.ui.scrubs.values()))
        editor.activate(False)
        self.assertFalse(editor.ui.panel.visible)

    def test_panel_visibility_does_not_hide_tools_or_switch_input_owner(self):
        from koma.editor.drawing_geometry import PENCIL
        view, editor = self.editor()
        editor.enabled = False
        player = view.player
        before, count = view.board, len(view.history.past)
        header = tuple(player.header.controls)
        with patch.object(player, 'fit_preview', side_effect=AssertionError('Unexpected preview refit')):
            editor.activate(True)
            self.assertTrue(player.drawing_slot.visible)
            self.assertFalse(editor.enabled)
            self.assertFalse(player.drawing_surface.content.ignore_interactions)
            editor.choose_tool('move')
            self.assertTrue(editor.enabled)
            self.assertTrue(player.drawing_slot.visible)
            player.drawing_surface.choose_tool(PENCIL)
            self.assertFalse(editor.enabled)
            self.assertTrue(editor.panel_open)
            self.assertTrue(editor.ui.panel.visible)
            self.assertFalse(player.drawing_surface.content.ignore_interactions)
        self.assertEqual(tuple(player.header.controls), header)
        self.assertIs(view.board, before)
        self.assertEqual(len(view.history.past), count)

    def test_numeric_fields_have_only_one_visible_value_in_display_edit_and_cancel(self):
        view, editor = self.editor()
        self.assertNotIn(editor.ui.toggle, view.player.header.controls)
        self.assertIs(view.player.layout.media_reopen.content.controls[0], editor.ui.toggle)
        for scrub in editor.ui.scrubs.values():
            self.assertFalse(scrub.entry.visible)
            self.assertTrue(scrub.readout.visible)
            scrub.set_editing(True)
            self.assertTrue(scrub.entry.visible)
            self.assertFalse(scrub.readout.visible)
        editor.ui.cancel_fields()
        self.assertTrue(all(not scrub.entry.visible and scrub.readout.visible for scrub in editor.ui.scrubs.values()))

    def test_deleting_last_key_preserves_base_preview_history_and_saved_document(self):
        view, editor = self.editor()
        base = MediaPose(.12, .08, 1.2, 8)
        key_pose = MediaPose(.6, .4, 2, 40)
        preview = MediaPose(.3, -.1, 3, 33)
        transform = MediaTransform(pose=base, keyframes=(MediaKeyframe(0, key_pose),))
        fixtures.finish(editor.commit(editor.frame(), transform))
        fixtures.finish(editor.apply_pose(preview))
        before = view.board
        count = len(view.history.past)
        view.player.strip.keyframe_lane.editor.selected = 0
        with patch.object(view, 'refresh', side_effect=AssertionError('Full canvas rebuild')):
            fixtures.finish(view.player.strip.keyframe_lane.editor.remove_selected())
        current = editor.frame().active_media.transform
        self.assertEqual(current.pose, base)
        self.assertEqual(current.keyframes, ())
        self.assertEqual(editor.effective_pose(), preview)
        self.assertEqual(view.player.preview.pose, preview)
        self.assertEqual(len(view.history.past), count + 1)
        after = view.board
        fixtures.finish(view.graph.undo())
        self.assertEqual(view.board, before)
        self.assertEqual(editor.effective_pose(), preview)
        fixtures.finish(view.graph.redo())
        self.assertEqual(view.board, after)
        self.assertEqual(editor.effective_pose(), preview)
        self.assertEqual(view.store.load(), after)
        view.player.playing = True
        editor.seek_preview()
        self.assertEqual(view.player.preview.pose, base)

    def test_shortcut_delete_removes_only_keyframes_and_keeps_visible_pose(self):
        view, editor = self.editor()
        base = MediaPose(.1)
        keyed = MediaPose(.6)
        fixtures.finish(editor.commit(editor.frame(), MediaTransform(pose=base, keyframes=(MediaKeyframe(0, keyed),))))
        fixtures.finish(editor.set_key(remove_only=True))
        self.assertEqual(editor.frame().active_media.transform.pose, base)
        self.assertFalse(editor.frame().active_media.transform.keyframes)
        self.assertEqual(editor.effective_pose(), keyed)

    def test_rendering_geometry_and_image_animation_use_local_time(self):
        view, _ = self.editor()
        frame = view.board.frames[0]
        transform = MediaTransform(keyframes=(MediaKeyframe(0, MediaPose()), MediaKeyframe(1, MediaPose(.25, 0, 1, 90))))
        frame = replace(frame, media=(replace(frame.active_media, transform=transform),))
        base = Image.new('RGB', (100, 100), 'red')
        base.paste('blue', (0, 0, 50, 100))
        composer = FrameComposer(frame, (100, 100), include_subtitles=False)
        self.assertNotEqual(composer.compose(base, 0).tobytes(), composer.compose(base, 1).tobytes())
        geometry = image_geometry((100, 100), (100, 100), transform, 1)
        self.assertAlmostEqual(geometry[2], 25)
        affine = inverse_affine((100, 100), (100, 100), MediaTransform())
        self.assertEqual(affine, (1, 0, 0, 0, 1, 0))
        source = StoryboardFrames((frame,), view.store, (100, 100), (25,), offsets=(.25,))
        pictures = list(source.pictures((100, 100), 24, lambda: False))
        self.assertNotEqual(pictures[0].tobytes(), pictures[-1].tobytes())

    def test_previous_documents_receive_identity_transform(self):
        view, _ = self.editor()
        raw = json.loads(json.dumps(document(view.board, 'a' * 32)))
        raw['version'] = 10
        for frame in raw['frames']:
            for transform in [frame['image_defaults'], *(item['transform'] for item in frame['media'])]:
                transform.pop('pose')
                transform.pop('keyframes')
        restored, _ = parse_document(raw)
        self.assertEqual(restored.frames[0].active_media.transform.at(0), MediaPose())

    def test_timeline_keyframes_drag_cancel_delete_and_undo_use_the_same_media(self):
        view, editor = self.editor()
        transform = MediaTransform(keyframes=(MediaKeyframe(0, MediaPose()),
            MediaKeyframe(.5, MediaPose(.1)), MediaKeyframe(1, MediaPose(.2))))
        fixtures.finish(editor.commit(editor.frame(), transform))
        strip = view.player.strip
        strip.resized(Data(width=800))
        strip.sync()
        lane = strip.keyframe_lane
        self.assertEqual(set(lane.points), {0, .5, 1})
        before, count = view.board, len(view.history.past)
        lane.editor.begin(.5, 100)
        lane.editor.move(100 + strip.scale.pixels(.25))
        self.assertIs(view.board, before)
        lane.editor.cancel()
        self.assertIs(view.board, before)
        lane.editor.begin(.5, 100)
        lane.editor.move(100 + strip.scale.pixels(.25))
        with patch.object(view, 'refresh', side_effect=AssertionError('Full canvas rebuild')):
            fixtures.finish(lane.editor.finish())
        self.assertEqual([key.time for key in editor.frame().active_media.transform.keyframes], [0, .75, 1])
        self.assertEqual(len(view.history.past), count + 1)
        fixtures.finish(view.player.key_down(Data(key='Delete', ctrl=False, alt=False, shift=False, meta=False)))
        self.assertEqual([key.time for key in editor.frame().active_media.transform.keyframes], [0, 1])
        fixtures.finish(view.graph.undo())
        self.assertEqual([key.time for key in editor.frame().active_media.transform.keyframes], [0, .75, 1])

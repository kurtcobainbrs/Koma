"""Timeline editável: tempo, prévia transitória, commit único e integridade."""

from dataclasses import replace
from types import SimpleNamespace as Data
from unittest import TestCase
from unittest.mock import patch
import msgpack

from flet.controls.base_control import BaseControl
from flet.controls.object_patch import ObjectPatch
from flet.messaging.protocol import configure_encode_object_for_msgpack

from tests import test_storyboard as fixtures
from koma.editor.models import StoryFrame, Storyboard, MAX_CARDS, MAX_DURATION
from koma.editor.timeline import Timeline, TimeScale, snap_duration
from koma.editor.timeline_navigation import frame_position, ruler_ticks
from koma.exports.video_export import frame_counts


class TemporalModelTests(TestCase):
    def test_playhead_snaps_to_frame_and_clamps_to_sequence(self):
        for fps in (24, 25, 30, 60):
            self.assertEqual(frame_position(1.5 / fps, 10, fps), 2 / fps)
            self.assertEqual(frame_position(-1, 10, fps), 0)
            self.assertEqual(frame_position(100, 2.1, fps), 2.1)

    def test_ruler_generates_only_visible_marks_even_on_long_sequences(self):
        ticks = ruler_ticks(TimeScale(100), 100_000, 800, 1_000_000, 24, 100)
        self.assertLessEqual(len(ticks), 10)
        self.assertGreaterEqual(ticks[0][1], 99_900)
        self.assertLessEqual(ticks[-1][1], 100_800)

    def test_frame_snap_uses_project_fps_and_document_limits(self):
        for fps in (24, 25, 30, 60):
            self.assertEqual(snap_duration(-100, fps), 1 / fps)
            self.assertEqual(snap_duration(MAX_DURATION * 2, fps), MAX_DURATION)
            self.assertEqual(snap_duration(1.5 / fps, fps), 2 / fps)
        for value in (float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                snap_duration(value, 24)

    def test_scale_is_reversible_and_calculated_from_available_width(self):
        scale = TimeScale.fit(960, 12)
        self.assertEqual(scale.pixels(3), 240)
        self.assertEqual(scale.seconds(240), 3)
        for width, duration in ((0, 1), (100, 0), (-1, 2)):
            with self.assertRaises(ValueError):
                TimeScale.fit(width, duration)

    def test_maximum_document_sequence_needs_no_per_frame_special_cases(self):
        board = Storyboard(frames=tuple(StoryFrame(duration=(i % 5 + 1) / 24) for i in range(MAX_CARDS)))
        timeline = Timeline(board)
        self.assertEqual(len(timeline.frames), MAX_CARDS)
        self.assertAlmostEqual(timeline.starts[-1] + timeline.frames[-1].duration, timeline.total)
        self.assertEqual(timeline.index_at(timeline.total), MAX_CARDS - 1)


class TimelineEditingTests(TestCase):
    setUp = fixtures.StoryboardTests.setUp
    view = fixtures.StoryboardTests.view

    def test_playback_icon_toggles_update_state_and_subtitle_preference(self):
        view, player = self.editor()
        self.assertFalse(player.loop.selected)
        player.loop.on_click(None)
        self.assertTrue(player.loop.selected)
        player.loop.on_click(None)
        self.assertFalse(player.loop.selected)
        self.assertTrue(player.show_subtitles.selected)
        player.show_subtitles.on_click(None)
        self.assertFalse(player.show_subtitles.selected)
        self.assertFalse(view.preferences.options.show_subtitles)
        player.show_subtitles.on_click(None)
        self.assertTrue(player.show_subtitles.selected)
        self.assertTrue(view.preferences.options.show_subtitles)

    def editor(self):
        view = self.view()
        fixtures.finish(view.add_frame())
        fixtures.finish(view.add_frame())
        player = view.player
        player.open()
        player.strip.resized(Data(width=800))
        return view, player

    def test_wheel_zoom_preserves_time_under_cursor_and_f_fits_sequence(self):
        view, player = self.editor()
        strip = player.strip
        before = view.board
        history = len(view.history.past)
        event = Data(scroll_delta=Data(y=-120), local_position=Data(x=200))
        anchor_time = strip.scale.seconds(strip.offset + 200)
        strip.wheel_zoom(event)
        self.assertGreater(strip.scale.pixels_per_second, 200)
        self.assertAlmostEqual(strip.scale.seconds(strip.offset + 200), anchor_time)
        strip.wheel_zoom(Data(scroll_delta=Data(y=120), local_position=Data(x=200)))
        self.assertAlmostEqual(strip.scale.pixels_per_second, 200)
        strip.zoom(4)
        strip.scrolled(Data(pixels=600))
        fixtures.finish(player.key_down(Data(key='f')))
        self.assertEqual(strip.scale.pixels_per_second, 200)
        self.assertEqual(strip.offset, 0)
        self.assertTrue(strip.fit_requested)
        self.assertIs(view.board, before)
        self.assertEqual(len(view.history.past), history)

    def test_fit_and_wheel_do_not_interfere_with_duration_input(self):
        view, player = self.editor()
        strip = player.strip
        strip.zoom(2)
        scale = strip.scale
        strip.duration_input.focus()
        fixtures.finish(player.key_down(Data(key='f')))
        strip.wheel_zoom(Data(scroll_delta=Data(y=-120), local_position=Data(x=200)))
        self.assertEqual(strip.scale, scale)

    def test_active_duration_box_tracks_selection_and_discards_unsubmitted_expression(self):
        view, player = self.editor()
        first, second = view.board.frames
        fixtures.finish(view.set_frame_properties(second.id, duration=3))
        player.render()
        entry = player.strip.duration_input
        self.assertEqual(entry.field.value, '48')
        entry.focus()
        entry.field.value = '24*10'
        player.strip.blocks[second.id].seek(None)
        self.assertEqual(entry.field.value, '72')
        self.assertFalse(entry.focused)
        self.assertIsNone(entry.target)
        self.assertEqual(view.board.frames[0], first)
        entry.focus()
        entry.field.value = '100'
        fixtures.finish(player.key_down(Data(key='Escape')))
        self.assertEqual(entry.field.value, '72')
        self.assertEqual(view.board.frames[1].duration, 3)

    def test_duration_input_commits_expression_to_target_frame_and_undo_restores_it(self):
        view, player = self.editor()
        first, second = view.board.frames
        dialog = player.strip.duration_input
        history = len(view.history.past)
        player.strip.blocks[second.id].seek(None)
        dialog.focus()
        dialog.field.value = '(24+12)*2'
        fixtures.finish(dialog.field.on_submit(Data(control=dialog.field)))
        self.assertEqual(dialog.field.value, '72')
        self.assertFalse(dialog.focused)
        self.assertIsNone(dialog.target)
        dialog.cancel()
        self.assertEqual(view.board.frames[0], first)
        self.assertEqual(view.board.frames[1].duration, 3)
        self.assertEqual(player.timeline.total, 5)
        self.assertEqual(len(view.history.past), history + 1)
        self.assertEqual(view.store.load(), view.board)
        fixtures.finish(player.strip.undo_edit())
        self.assertEqual(view.board.frames[1], second)

    def test_duration_input_validation_and_cancel_leave_document_unchanged(self):
        view, player = self.editor()
        before = view.board
        history = len(view.history.past)
        dialog = player.strip.duration_input
        dialog.focus()
        dialog.field.value = '24/0'
        fixtures.finish(dialog.save())
        self.assertTrue(dialog.focused)
        self.assertIsNotNone(dialog.field.error_text)
        self.assertIs(view.board, before)
        dialog.cancel()
        self.assertEqual(len(view.history.past), history)
        self.assertFalse(dialog.focused)

    def test_duration_input_rejects_stale_document_and_does_not_route_shortcuts_to_canvas(self):
        view, player = self.editor()
        dialog = player.strip.duration_input
        dialog.focus()
        before = view.board
        fixtures.finish(player.key_down(Data(key='z', ctrl=True)))
        self.assertIs(view.board, before)
        fixtures.finish(view.set_frame_properties(before.frames[0].id, duration=1))
        changed = view.board
        dialog.field.value = '24*5'
        fixtures.finish(dialog.save())
        self.assertIs(view.board, changed)
        self.assertIsNotNone(dialog.field.error_text)

    def test_scrub_uses_captured_scale_without_changing_duration_history_or_file(self):
        view, player = self.editor()
        board = view.board
        stored = view.store.path.read_bytes()
        history = len(view.history.past)
        navigator = player.strip.navigator
        navigator.begin(200, TimeScale(100), 1)
        navigator.move(350)
        self.assertEqual(player.position, 2.5)
        self.assertEqual(player.current, 1)
        self.assertIs(view.board, board)
        self.assertEqual(len(view.history.past), history)
        self.assertEqual(view.store.path.read_bytes(), stored)
        navigator.move(-1000)
        self.assertEqual(player.position, 0)
        navigator.move(10000)
        self.assertEqual(player.position, player.timeline.total)
        navigator.end()
        navigator.move(200)
        self.assertEqual(player.position, player.timeline.total)

    def test_scrub_updates_only_cursor_and_transport_within_same_frame(self):
        view, player = self.editor()
        player.render()
        with patch.object(player.strip, 'sync', wraps=player.strip.sync) as sync:
            view.page.update.reset_mock()
            player.strip.navigator.seek(.5)
            sync.assert_not_called()
            updated = view.page.update.call_args.args
            self.assertNotIn(player.content, updated)
            self.assertNotIn(player.strip.content, updated)
            self.assertIn(player.strip.needle, updated)
            view.page.update.reset_mock()
            player.strip.navigator.seek(.5 + .001)
            view.page.update.assert_not_called()
            player.strip.navigator.begin(100, TimeScale(100))
            player.strip.navigator.end(Data(global_position=Data(x=150)))
            self.assertEqual(player.position, 1)
            self.assertIsNone(player.strip.navigator.gesture)
    def test_ruler_hit_test_uses_track_coordinates_and_zoom_keeps_center_time(self):
        view, player = self.editor()
        strip = player.strip
        strip.zoom(4)
        self.assertEqual(strip.scale.pixels_per_second, 800)
        strip.scrolled(Data(pixels=1200))
        strip.ruler_seek(Data(local_position=Data(x=1800)))
        self.assertEqual(player.position, 2.25)
        center = strip.scale.seconds(strip.offset + strip.width / 2)
        strip.zoom(2)
        self.assertEqual(strip.scale.seconds(strip.offset + strip.width / 2), center)

    def test_scrub_pauses_playback_and_is_blocked_during_duration_edit(self):
        view, player = self.editor()
        navigator = player.strip.navigator
        player.playing = True
        navigator.seek(1)
        self.assertFalse(player.playing)
        token = player.duration_editor.begin(view.board.frames[0].id, 0, TimeScale(100))
        position = player.position
        navigator.begin(0, TimeScale(100), 3)
        self.assertIsNone(navigator.gesture)
        self.assertEqual(player.position, position)
        player.duration_editor.cancel()
        navigator.begin(0, TimeScale(100))
        player.close()
        self.assertIsNone(navigator.gesture)

    def test_drag_updates_preview_and_card_without_mutating_or_saving_document_until_release(self):
        view, player = self.editor()
        before = view.board
        first, second = before.frames
        history = len(view.history.past)
        scale = TimeScale(100)
        with patch.object(view.store, 'save', wraps=view.store.save) as saved:
            token = player.duration_editor.begin(first.id, 200, scale)
            player.duration_editor.move(token, 250)
            self.assertIs(view.board, before)
            self.assertEqual(player.timeline.frames[0].duration, 2.5)
            self.assertEqual(player.timeline.starts[1], 2.5)
            self.assertEqual(player.timeline.total, 4.5)
            self.assertIn('60 f', view.cards[first.id].duration.value)
            self.assertIn('2.5 s', player.caption.tooltip)
            self.assertFalse(player.playing)
            saved.assert_not_called()
            player.duration_editor.move(token, 300)
            self.assertEqual(len(view.history.past), history)
            fixtures.finish(player.duration_editor.finish(token))
            saved.assert_called_once()
        self.assertEqual(view.board.frames[0].duration, 3)
        self.assertEqual(view.board.frames[1], second)
        self.assertEqual(len(view.history.past), history + 1)
        self.assertEqual(view.store.load(), view.board)
        self.assertEqual(frame_counts(view.board.frames, view.board.fps), [72, 48])

    def test_cancel_restores_preview_position_and_leaves_file_and_history_unchanged(self):
        view, player = self.editor()
        before = view.board
        saved = view.store.path.read_bytes()
        history = len(view.history.past)
        player.position = 1
        token = player.duration_editor.begin(before.frames[1].id, 100, TimeScale(100))
        player.duration_editor.move(token, 200)
        player.duration_editor.cancel()
        self.assertIs(view.board, before)
        self.assertEqual(player.timeline.frames, before.frames)
        self.assertEqual(player.position, 1)
        self.assertEqual(view.store.path.read_bytes(), saved)
        self.assertEqual(len(view.history.past), history)
        self.assertFalse(view.busy)

    def test_closing_preview_discards_active_drag(self):
        view, player = self.editor()
        before = view.board
        token = player.duration_editor.begin(before.frames[0].id, 100, TimeScale(100))
        player.duration_editor.move(token, 250)
        player.close()
        self.assertIs(view.board, before)
        self.assertFalse(view.busy)
        self.assertIsNone(player.duration_editor.drag)

    def test_undo_and_redo_inside_preview_keep_node_and_timeline_consistent(self):
        view, player = self.editor()
        first = view.board.frames[0]
        token = player.duration_editor.begin(first.id, 100, TimeScale(100))
        player.duration_editor.move(token, 200)
        fixtures.finish(player.duration_editor.finish(token))
        fixtures.finish(player.key_down(Data(key='z', ctrl=True)))
        self.assertEqual(view.board.frames[0].duration, 2)
        self.assertEqual(player.timeline.total, 4)
        fixtures.finish(player.key_down(Data(key='z', ctrl=True, shift=True)))
        self.assertEqual(view.board.frames[0].duration, 3)
        self.assertEqual(player.timeline.total, 5)

    def test_dragging_uses_fixed_scale_even_when_total_duration_changes(self):
        view, player = self.editor()
        first = view.board.frames[0]
        scale = player.strip.scale
        token = player.duration_editor.begin(first.id, 0, scale)
        player.duration_editor.move(token, scale.pixels(1))
        self.assertEqual(player.timeline.frames[0].duration, 3)
        self.assertIs(player.strip.scale, scale)
        player.duration_editor.cancel()

    def test_zero_motion_does_not_quantize_existing_subframe_duration_or_add_history(self):
        view, player = self.editor()
        identifier = view.board.frames[0].id
        fixtures.finish(view.set_frame_properties(identifier, duration=.1))
        player.render()
        history = len(view.history.past)
        token = player.duration_editor.begin(identifier, 100, TimeScale(100))
        player.duration_editor.move(token, 100)
        fixtures.finish(player.duration_editor.finish(token))
        self.assertEqual(view.board.frames[0].duration, .1)
        self.assertEqual(len(view.history.past), history)

    def test_scene_and_mute_filter_are_respected_without_affecting_other_scene(self):
        view = self.view()
        for action in (view.add_principal, view.add_frame, view.add_frame, view.add_principal, view.add_frame):
            fixtures.finish(action())
        main, first, muted, other_main, other = view.board.frames
        fixtures.finish(view.graph.connect(main.id, first.id))
        fixtures.finish(view.graph.connect(first.id, muted.id))
        fixtures.finish(view.graph.connect(other_main.id, other.id))
        fixtures.finish(view.toggle_muted({muted.id}))
        view.workspace.navigation.apply_selection({first.id}, first.id)
        player = view.player
        player.open()
        player.strip.resized(Data(width=600))
        self.assertEqual(tuple(player.strip.blocks), (first.id,))
        token = player.duration_editor.begin(first.id, 0, TimeScale(100))
        player.duration_editor.move(token, 50)
        fixtures.finish(player.duration_editor.finish(token))
        self.assertEqual(next(f for f in view.board.frames if f.id == other.id), other)
        self.assertEqual(next(f for f in view.board.frames if f.id == muted.id).duration, 2)

    def test_recovery_failure_preserves_saved_bundle_and_keeps_edit_undoable(self):
        view, player = self.editor()
        target = self.root / 'original.koma'
        view.session.save(view.board, target)
        original = target.read_bytes()
        token = player.duration_editor.begin(view.board.frames[0].id, 0, TimeScale(100))
        player.duration_editor.move(token, 100)
        with patch.object(view.session, 'recover', side_effect=OSError('Sem acesso')):
            fixtures.finish(player.duration_editor.finish(token))
        self.assertEqual(target.read_bytes(), original)
        self.assertTrue(view.dirty)
        self.assertTrue(view.retry_save.visible)
        fixtures.finish(player.strip.undo_edit())
        self.assertEqual(view.board.frames[0].duration, 2)

    def test_serialized_timeline_remains_mutable_during_resize_and_playhead_updates(self):
        view, player = self.editor()
        encoder = configure_encode_object_for_msgpack(BaseControl)
        patch_, _, _ = ObjectPatch.from_diff(None, player.popup, BaseControl)
        msgpack.packb(patch_.to_message(), default=encoder)
        token = player.duration_editor.begin(view.board.frames[0].id, 0, TimeScale(100))
        player.duration_editor.move(token, 100)
        patch_, _, _ = ObjectPatch.from_diff(player.popup, player.popup, BaseControl)
        msgpack.packb(patch_.to_message(), default=encoder)
        player.duration_editor.cancel()
